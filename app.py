"""Streamlit entry point for the Crop Disease Detection chatbot."""

from __future__ import annotations

import io
import logging
import subprocess
import sys
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

PROJECT_ROOT = Path(__file__).resolve().parent
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
LOGGER = logging.getLogger(__name__)


def load_uploaded_image(uploaded_file) -> Image.Image:
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported file type. Upload a JPG, JPEG, PNG, or WEBP image.")
    image_bytes = uploaded_file.getvalue()
    if not image_bytes:
        raise ValueError("The uploaded file is empty.")
    if len(image_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError("The image is larger than the 15 MB upload limit.")
    try:
        with Image.open(io.BytesIO(image_bytes)) as candidate:
            candidate.verify()
        with Image.open(io.BytesIO(image_bytes)) as candidate:
            image = ImageOps.exif_transpose(candidate).convert("RGB")
            image.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("The uploaded file is not a valid readable image.") from exc
    if image.width < 16 or image.height < 16:
        raise ValueError("The image is too small. Use an image at least 16 x 16 pixels.")
    return image


def streamlit_main() -> None:
    import streamlit as st
    from streamlit_webrtc import VideoProcessorBase, WebRtcMode, webrtc_streamer

    from chatbot.state import (
        init_session_state,
        active_session,
        create_new_session,
        append_message,
        set_chat_mode,
    )
    from chatbot import handlers
    from chatbot.prompts import INCONCLUSIVE_RESPONSE
    from crop_detection.predictor import (
        ModelLoadError,
        ModelManager,
        analyze_image,
        create_grayscale_copy,
        run_inference,
    )
    from crop_detection.disease_logic import select_crop
    from tracking.tracker_ui import render_tracking_panel

    st.set_page_config(
        page_title="Crop Disease Detection",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    init_session_state()

    @st.cache_resource(show_spinner="Loading models...")
    def get_model_manager() -> ModelManager:
        return ModelManager.from_project_root(PROJECT_ROOT)

    # ------------------------------------------------------------------ #
    # Sidebar — session management                                         #
    # ------------------------------------------------------------------ #
    with st.sidebar:
        st.title("Crop Sessions")
        st.caption(
            "Each session tracks one crop field or plant. "
            "Chat history lives in the browser tab; medicine logs are saved permanently."
        )

        sessions: dict = st.session_state.crop_sessions
        session_names = {sid: s.display_name for sid, s in sessions.items()}

        if sessions:
            current_id = st.session_state.active_crop_session_id
            options = list(session_names.keys())
            labels = [session_names[sid] for sid in options]
            selected_index = options.index(current_id) if current_id in options else 0
            chosen = st.selectbox(
                "Active session",
                options=options,
                format_func=lambda sid: session_names[sid],
                index=selected_index,
                key="session_selector",
            )
            if chosen != st.session_state.active_crop_session_id:
                st.session_state.active_crop_session_id = chosen
                set_chat_mode("ONBOARDING" if not sessions[chosen].disease_name else "ACTIVE_TREATMENT")
                st.rerun()

        with st.expander("New Session", expanded=not sessions):
            new_name = st.text_input("Session name", placeholder="e.g. Corn Field A", key="new_session_name")
            if st.button("Create Session", type="primary", key="create_session_btn"):
                name = new_name.strip() or f"Session {len(sessions) + 1}"
                session = create_new_session(name)
                st.rerun()

        if sessions and st.session_state.active_crop_session_id:
            st.divider()
            sess = active_session()
            if sess:
                st.caption(f"Crop: {sess.crop_name or 'Not yet identified'}")
                st.caption(f"Disease: {sess.disease_name or 'Not yet identified'}")
                if st.button("Delete This Session", key="delete_session_btn"):
                    from tracking import persistence
                    persistence.delete_session(sess.session_id)
                    del st.session_state.crop_sessions[sess.session_id]
                    st.session_state.active_crop_session_id = (
                        next(iter(st.session_state.crop_sessions), None)
                    )
                    set_chat_mode("ONBOARDING")
                    st.rerun()

        st.divider()
        st.caption("Single-user mode. See docs/MULTI_USER_UPGRADE.md for future multi-user support.")

    # ------------------------------------------------------------------ #
    # Main area                                                            #
    # ------------------------------------------------------------------ #
    session = active_session()

    if session is None:
        st.title("Crop Disease Detection")
        st.info("Create a new session in the sidebar to get started.")
        return

    st.title(f"Crop Disease Detection — {session.display_name}")

    # Medicine tracking panel (persistent, always available after diagnosis)
    if session.disease_name:
        with st.expander("Medicine & Progress Tracker", expanded=st.session_state.show_medicine_panel):
            render_tracking_panel(session.session_id, session.disease_name)

    st.divider()

    # Render chat history
    for msg in session.chat_history:
        role = msg["role"]
        if role == "system":
            continue  # system/summary messages are context only — not shown
        with st.chat_message(role):
            st.markdown(msg["content"])

    mode: str = st.session_state.chat_mode

    # ------------------------------------------------------------------ #
    # ONBOARDING — three input mode buttons                                #
    # ------------------------------------------------------------------ #
    if mode == "ONBOARDING":
        st.subheader("How would you like to identify your crop's condition?")
        col1, col2, col3 = st.columns(3, gap="large")

        with col1:
            if st.button("Upload Image", use_container_width=True, type="primary"):
                set_chat_mode("AWAITING_UPLOAD")
                st.rerun()
            st.caption("Upload a photo of the affected leaf.")

        with col2:
            if st.button("Use Live Camera", use_container_width=True, type="primary"):
                set_chat_mode("AWAITING_CAPTURE")
                st.rerun()
            st.caption("Capture a frame from your device camera.")

        with col3:
            if st.button("Describe the Leaf", use_container_width=True, type="primary"):
                opening = (
                    "No image available? No problem. I'll ask you a series of questions "
                    "about your crop and its symptoms. Please answer as specifically as you can — "
                    "I will not make any assumptions and will only provide advice once I have enough information."
                )
                append_message(session, "assistant", opening)
                set_chat_mode("CLARIFYING")
                st.rerun()
            st.caption("Answer questions if you have no image.")

    # ------------------------------------------------------------------ #
    # AWAITING_UPLOAD — file uploader                                      #
    # ------------------------------------------------------------------ #
    elif mode == "AWAITING_UPLOAD":
        uploaded_file = st.file_uploader(
            "Upload a leaf image",
            type=["jpg", "jpeg", "png", "webp"],
            help="Supported formats: JPG, JPEG, PNG, WEBP. Maximum 15 MB.",
        )

        if uploaded_file is not None:
            try:
                image = load_uploaded_image(uploaded_file)
            except ValueError as exc:
                st.error(str(exc))
            else:
                col_img, col_action = st.columns([3, 2], gap="large")
                with col_img:
                    st.image(image, use_container_width=True)
                with col_action:
                    user_note = st.text_input(
                        "Add a note (optional)",
                        placeholder="e.g. This is my east field corn",
                        key="upload_note",
                    )
                    if st.button("Analyse Image", type="primary", use_container_width=True, key="upload_analyse"):
                        with st.spinner("Running detection models..."):
                            try:
                                result = analyze_image(image, get_model_manager())
                            except FileNotFoundError as exc:
                                st.error(str(exc))
                                st.stop()
                            except ModelLoadError as exc:
                                st.error(str(exc))
                                st.stop()
                            except Exception:
                                LOGGER.exception("Image analysis failed")
                                st.error("Analysis failed. Check the terminal for details.")
                                st.stop()

                        _show_analysis_result(st, result)

                        st.session_state.groq_thinking = True
                        try:
                            response_stream = handlers.handle_image_analysis(
                                result, user_note or "", session
                            )
                            if isinstance(response_stream, str):
                                # Inconclusive — string returned directly
                                with st.chat_message("assistant"):
                                    st.markdown(response_stream)
                            else:
                                with st.chat_message("assistant"):
                                    full_response = st.write_stream(response_stream)
                                append_message(session, "assistant", full_response)
                        except RuntimeError as exc:
                            st.error(str(exc))
                        finally:
                            st.session_state.groq_thinking = False

                        st.rerun()

        if st.button("Back", key="upload_back"):
            set_chat_mode("ONBOARDING")
            st.rerun()

    # ------------------------------------------------------------------ #
    # AWAITING_CAPTURE — WebRTC live camera                                #
    # ------------------------------------------------------------------ #
    elif mode == "AWAITING_CAPTURE":
        st.write("Start your camera, wait for the green leaf detection box, then capture a frame.")

        manager = get_model_manager()

        class VideoProcessor(VideoProcessorBase):
            def __init__(self) -> None:
                self.frame_count = 0
                self.font = ImageFont.load_default()
                self.latest_frame = None
                self.latest_detection = None

            def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
                image_array = frame.to_ndarray(format="rgb24")
                pil_image = Image.fromarray(image_array)
                self.latest_frame = pil_image.copy()
                self.frame_count += 1

                detection = self.latest_detection
                if self.frame_count % 5 == 0:
                    try:
                        gray_image = create_grayscale_copy(pil_image)
                        detections = run_inference(manager.crop_model(), gray_image)
                        crop = select_crop(detections)
                        if crop.selected_detection:
                            detection = {
                                "box": crop.selected_detection.box,
                                "confidence": crop.selected_detection.confidence,
                                "status": "Leaf Detected",
                            }
                        else:
                            detection = None
                        self.latest_detection = detection
                    except Exception:
                        LOGGER.exception("Live detection failed")

                annotated = pil_image.copy()
                draw = ImageDraw.Draw(annotated)
                if detection:
                    x1, y1, x2, y2 = detection["box"]
                    draw.rectangle((x1, y1, x2, y2), outline=(0, 255, 0), width=3)
                    draw.text(
                        (max(0, x1), max(0, y1 - 20)),
                        f"Leaf {detection['confidence'] * 100:.1f}%",
                        fill=(0, 255, 0),
                        font=self.font,
                    )
                else:
                    draw.text((20, 20), "Searching for leaf...", fill=(255, 0, 0), font=self.font)

                return av.VideoFrame.from_ndarray(np.array(annotated), format="rgb24")

        ctx = webrtc_streamer(
            key="live-camera",
            mode=WebRtcMode.SENDRECV,
            video_processor_factory=VideoProcessor,
            media_stream_constraints={"video": True, "audio": False},
            async_processing=True,
        )

        if ctx and ctx.video_processor:
            latest = getattr(ctx.video_processor, "latest_frame", None)
            if latest is not None:
                st.session_state.latest_frame = latest.copy()

        if st.button("Capture Frame", type="primary", use_container_width=True, key="capture_btn"):
            if st.session_state.latest_frame is None:
                st.warning("No frame available yet. Start the camera first.")
            else:
                st.session_state.captured_frame = st.session_state.latest_frame.copy()

        if st.session_state.captured_frame is not None:
            st.subheader("Captured Frame")
            st.image(st.session_state.captured_frame, use_container_width=True)

            user_note = st.text_input(
                "Add a note (optional)",
                placeholder="e.g. This leaf is from the north corner of my field",
                key="capture_note",
            )

            if st.button("Analyse Captured Frame", type="primary", use_container_width=True, key="capture_analyse"):
                with st.spinner("Running detection models..."):
                    try:
                        result = analyze_image(st.session_state.captured_frame, get_model_manager())
                    except FileNotFoundError as exc:
                        st.error(str(exc))
                        st.stop()
                    except ModelLoadError as exc:
                        st.error(str(exc))
                        st.stop()
                    except Exception:
                        LOGGER.exception("Camera frame analysis failed")
                        st.error("Analysis failed. Check the terminal for details.")
                        st.stop()

                _show_analysis_result(st, result)

                st.session_state.groq_thinking = True
                try:
                    response_stream = handlers.handle_camera_analysis(
                        result, user_note or "", session
                    )
                    if isinstance(response_stream, str):
                        with st.chat_message("assistant"):
                            st.markdown(response_stream)
                    else:
                        with st.chat_message("assistant"):
                            full_response = st.write_stream(response_stream)
                        append_message(session, "assistant", full_response)
                except RuntimeError as exc:
                    st.error(str(exc))
                finally:
                    st.session_state.groq_thinking = False

                st.session_state.captured_frame = None
                st.rerun()

        if st.button("Back", key="capture_back"):
            set_chat_mode("ONBOARDING")
            st.rerun()

    # ------------------------------------------------------------------ #
    # CLARIFYING or ACTIVE_TREATMENT — chat input                         #
    # ------------------------------------------------------------------ #
    elif mode in ("CLARIFYING", "ACTIVE_TREATMENT"):
        if mode == "CLARIFYING":
            st.caption("Answer my questions so I can identify your crop's condition.")
        else:
            st.caption(
                "Your treatment plan is active. Ask follow-up questions, "
                "report progress, or use the medicine tracker above."
            )

        user_input = st.chat_input(
            "Type your message...",
            disabled=st.session_state.groq_thinking,
        )

        if user_input:
            with st.chat_message("user"):
                st.markdown(user_input)

            st.session_state.groq_thinking = True
            try:
                result = handlers.handle_text_message(user_input, session)

                from chatbot.clarification import ClarificationResult
                if isinstance(result, ClarificationResult):
                    # Clarification loop returned a question
                    question = result.question or "Could you provide more details about the symptoms?"
                    with st.chat_message("assistant"):
                        st.markdown(question)
                else:
                    # Streaming treatment/follow-up response
                    with st.chat_message("assistant"):
                        full_response = st.write_stream(result)
                    append_message(session, "assistant", full_response)
            except RuntimeError as exc:
                st.error(str(exc))
            finally:
                st.session_state.groq_thinking = False

            st.rerun()

        if mode == "ACTIVE_TREATMENT":
            if st.button("Start Over (new analysis)", key="restart_btn"):
                session.chat_history.clear()
                session.analysis_result = None
                session.clarification_state = None
                set_chat_mode("ONBOARDING")
                st.rerun()


def _show_analysis_result(st, result) -> None:
    """Display the YOLO detection metrics inline before the Groq response."""
    with st.expander("Detection Details", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Crop", result.crop_name)
            st.metric("Crop Confidence", f"{result.crop_confidence:.1%}")
            if result.crop_was_assumed:
                st.caption("Grape was assumed — no Corn detection found.")
        with col2:
            st.metric("Disease", result.disease_name)
            st.metric("Disease Confidence", f"{result.disease_confidence:.1%}")
            if result.disease_was_fallback:
                st.caption("Healthy fallback — no qualifying disease detected.")

        if result.all_disease_detections:
            visible = [d for d in result.all_disease_detections if d.confidence > 0.05]
            if visible:
                st.caption("All class scores:")
                for d in sorted(visible, key=lambda x: x.confidence, reverse=True):
                    st.caption(f"  {d.class_name}: {d.confidence:.1%}")

        st.image(result.annotated_image, caption="Annotated image", use_container_width=True)

        buffer = io.BytesIO()
        result.annotated_image.save(buffer, format="JPEG", quality=92)
        st.download_button(
            "Download Annotated Image",
            data=buffer.getvalue(),
            file_name=result.output_path.name,
            mime="image/jpeg",
        )


def _is_streamlit_runtime() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx(suppress_warning=True) is not None
    except (ImportError, TypeError):
        return False


def launch() -> None:
    try:
        import streamlit  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "Streamlit is not installed. Run: pip install -r requirements.txt"
        ) from exc

    if _is_streamlit_runtime():
        streamlit_main()
        return

    command = [
        sys.executable, "-m", "streamlit", "run",
        str(Path(__file__).resolve()), *sys.argv[1:],
    ]
    raise SystemExit(subprocess.call(command))


if __name__ == "__main__":
    launch()
