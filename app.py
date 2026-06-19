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


# ---------------------------------------------------------------------------
# CSS injection
# ---------------------------------------------------------------------------

_CUSTOM_CSS = """
<style>
/* Landing page option cards */
div[data-testid="stVerticalBlock"] .option-card-btn button {
    border-radius: 12px;
    padding: 28px 12px;
    font-size: 1.05rem;
    font-weight: 600;
    min-height: 110px;
    transition: box-shadow 0.2s;
}

/* Detection result banner */
.detection-banner {
    background: linear-gradient(90deg, #1b3a1b 0%, #243d22 100%);
    border-left: 4px solid #4caf50;
    border-radius: 8px;
    padding: 14px 20px;
    margin-bottom: 10px;
}
.detection-banner h4 {
    color: #a5d6a7;
    margin: 0 0 6px 0;
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
.detection-banner .crop-label {
    font-size: 1.1rem;
    font-weight: 700;
    color: #e8f5e9;
}
.detection-banner .conf-label {
    font-size: 0.82rem;
    color: #81c784;
    margin-left: 6px;
}
.detection-banner .flag-text {
    font-size: 0.78rem;
    color: #ffcc80;
    margin-top: 2px;
}

/* Past sessions card */
.session-card {
    border: 1px solid #2e4a2e;
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 10px;
    background: #0f1f0f;
}
</style>
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stream_to_str(raw) -> str:
    """Normalise st.write_stream output (list[Any] | str | None) to plain str."""
    if isinstance(raw, list):
        return "".join(str(chunk) for chunk in raw)
    return raw or ""


def _is_result_unreliable(result) -> bool:
    """Mirror the handlers.is_inconclusive check without importing to avoid circular deps."""
    from chatbot.handlers import is_inconclusive
    return is_inconclusive(result.all_disease_detections)


def _render_detection_section(st, result, *, key_suffix: str, expanded: bool = True) -> None:
    """Collapsible detection panel: annotated image + full results.

    Rendered from ``session.analysis_result`` so it persists across reruns and
    stays available for the whole session. The expander lets the user hide it.
    """
    label = f"🔬 Detection Result — {result.crop_name} / {result.disease_name}"
    with st.expander(label, expanded=expanded):
        if _is_result_unreliable(result):
            st.warning("⚠️ Low confidence — the top detection scores are close; treat as tentative.")

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
            key=f"download_annotated_{key_suffix}",
        )


def _run_analysis_and_stream(st, result, user_note, session, handlers, append_message):
    """Shared flow after inference: two-phase LLM → stream summary to chat."""
    from chatbot.prompts import INCONCLUSIVE_WARNING

    st.session_state.groq_thinking = True
    try:
        with st.spinner("Generating treatment plan from medication database..."):
            analysis_resp = handlers.handle_image_analysis(result, user_note or "", session)

        if analysis_resp.is_unreliable:
            st.warning(INCONCLUSIVE_WARNING)

        # Phase-1 result: medicine table already appended to history; display in current run
        if analysis_resp.medicine_table_markdown:
            with st.chat_message("assistant"):
                st.markdown(analysis_resp.medicine_table_markdown)
            if analysis_resp.auto_medicine_entries:
                st.info(
                    f"{len(analysis_resp.auto_medicine_entries)} medicine entr"
                    f"{'y' if len(analysis_resp.auto_medicine_entries) == 1 else 'ies'} "
                    "auto-added to your treatment table."
                )

        # Phase-2: stream crop condition summary
        with st.chat_message("assistant"):
            full_summary = _stream_to_str(st.write_stream(analysis_resp.summary_stream))
        append_message(session, "assistant", full_summary)

    except RuntimeError as exc:
        st.error(str(exc))
    finally:
        st.session_state.groq_thinking = False

    st.rerun()


# ---------------------------------------------------------------------------
# Main Streamlit app
# ---------------------------------------------------------------------------

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
    from crop_detection.predictor import (
        ModelLoadError,
        ModelManager,
        analyze_image,
        create_grayscale_copy,
        run_inference,
    )
    from crop_detection.disease_logic import select_crop
    from tracking.tracker_ui import render_tracking_panel
    from tracking import persistence

    st.set_page_config(
        page_title="Crop Disease Detection",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)

    init_session_state()

    @st.cache_resource(show_spinner="Loading models...")
    def get_model_manager() -> ModelManager:
        return ModelManager.from_project_root(PROJECT_ROOT)

    # ------------------------------------------------------------------ #
    # Sidebar — session management                                         #
    # ------------------------------------------------------------------ #
    with st.sidebar:
        st.title("Sessions")

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
                _s = st.session_state.crop_sessions.get(chosen)
                set_chat_mode("ONBOARDING" if not (_s and _s.disease_name) else "ACTIVE_TREATMENT")
                st.rerun()

        with st.expander("New Session", expanded=not sessions):
            new_name = st.text_input("Session name", placeholder="e.g. Corn Field A", key="new_session_name")
            if st.button("Create Session", type="primary", key="create_session_btn"):
                name = new_name.strip() or f"Session {len(sessions) + 1}"
                create_new_session(name)
                st.rerun()

        if sessions and st.session_state.active_crop_session_id:
            st.divider()
            sess = active_session()
            if sess:
                st.caption(f"Crop: {sess.crop_name or 'Not yet identified'}")
                st.caption(f"Disease: {sess.disease_name or 'Not yet identified'}")
                if st.button("Delete This Session", key="delete_session_btn"):
                    persistence.delete_session(sess.session_id)
                    del st.session_state.crop_sessions[sess.session_id]
                    st.session_state.active_crop_session_id = (
                        next(iter(st.session_state.crop_sessions), None)
                    )
                    set_chat_mode("ONBOARDING")
                    st.rerun()

        st.divider()
        st.caption("Single-user mode.")

    # ------------------------------------------------------------------ #
    # Main area                                                            #
    # ------------------------------------------------------------------ #
    session = active_session()

    if session is None:
        st.markdown("## Crop Disease Detection")
        st.info("Create a new session in the sidebar to get started.")
        return

    st.markdown(f"### {session.display_name}")

    # Persistent, collapsible detection section — shown whenever a result is stored
    if getattr(session, "analysis_result", None) is not None:
        _render_detection_section(
            st, session.analysis_result, key_suffix="persistent", expanded=True
        )

    # Medicine tracker expander (visible in ACTIVE_TREATMENT outside the dedicated page)
    mode: str = st.session_state.chat_mode
    if session.disease_name and mode not in ("MEDICINE_TABLE", "PAST_SESSIONS"):
        with st.expander("Medicine & Progress Tracker", expanded=st.session_state.show_medicine_panel):
            render_tracking_panel(session.session_id, session.disease_name)

    st.divider()

    # Render chat history
    for msg in session.chat_history:
        role = msg["role"]
        if role == "system":
            continue
        display_role = msg.get("display_role", role)
        with st.chat_message(display_role):
            st.markdown(msg["content"])

    # ------------------------------------------------------------------ #
    # ONBOARDING — 5-option landing page                                  #
    # ------------------------------------------------------------------ #
    if mode == "ONBOARDING":
        st.subheader("What would you like to do?")

        # Row 1: three analysis entry points
        col1, col2, col3 = st.columns(3, gap="medium")

        with col1:
            st.markdown('<div class="option-card-btn">', unsafe_allow_html=True)
            if st.button("📷  Upload Image", use_container_width=True, type="primary", key="ob_upload"):
                set_chat_mode("AWAITING_UPLOAD")
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
            st.caption("Analyse a photo of an affected leaf.")

        with col2:
            st.markdown('<div class="option-card-btn">', unsafe_allow_html=True)
            if st.button("🎥  Live Feed", use_container_width=True, type="primary", key="ob_live"):
                set_chat_mode("AWAITING_CAPTURE")
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
            st.caption("Use your device camera in real time.")

        with col3:
            st.markdown('<div class="option-card-btn">', unsafe_allow_html=True)
            if st.button("📝  Describe Leaf", use_container_width=True, type="primary", key="ob_describe"):
                opening = (
                    "No image available? No problem. I'll ask you a series of questions "
                    "about your crop and its symptoms. Please answer as specifically as you can — "
                    "I will not make any assumptions and will only provide advice once I have enough information."
                )
                append_message(session, "assistant", opening)
                set_chat_mode("CLARIFYING")
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
            st.caption("Answer questions if you have no image.")

        st.write("")

        # Row 2: two management views
        col4, col5 = st.columns(2, gap="medium")

        with col4:
            st.markdown('<div class="option-card-btn">', unsafe_allow_html=True)
            if st.button("📋  Past Sessions", use_container_width=True, key="ob_past"):
                set_chat_mode("PAST_SESSIONS")
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
            st.caption("Review and switch between previous sessions.")

        with col5:
            st.markdown('<div class="option-card-btn">', unsafe_allow_html=True)
            if st.button("💊  Medicine Table", use_container_width=True, key="ob_meds"):
                set_chat_mode("MEDICINE_TABLE")
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
            st.caption("View, edit, or delete treatment log entries.")

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

                        _run_analysis_and_stream(st, result, "", session, handlers, append_message)

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

                st.session_state.captured_frame = None
                _run_analysis_and_stream(st, result, user_note, session, handlers, append_message)

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
                    question = result.question or "Could you provide more details about the symptoms?"
                    with st.chat_message("assistant"):
                        st.markdown(question)
                else:
                    with st.chat_message("assistant"):
                        full_response = _stream_to_str(st.write_stream(result))
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

    # ------------------------------------------------------------------ #
    # PAST_SESSIONS — full session browser                                 #
    # ------------------------------------------------------------------ #
    elif mode == "PAST_SESSIONS":
        st.subheader("Past Sessions")

        all_sessions = st.session_state.crop_sessions
        if not all_sessions:
            st.info("No sessions yet. Create one from the sidebar.")
        else:
            for sid, sess in sorted(
                all_sessions.items(),
                key=lambda kv: kv[1].created_at,
                reverse=True,
            ):
                med_entries = persistence.load_medicine_entries(sid)
                is_active = (sid == st.session_state.active_crop_session_id)

                badge = " ✅ **Active**" if is_active else ""
                with st.container():
                    st.markdown(
                        f"""
<div class="session-card">
  <strong>{sess.display_name}</strong>{badge}<br/>
  <span style="color:#81c784">Crop:</span> {sess.crop_name or '—'} &nbsp;|&nbsp;
  <span style="color:#81c784">Disease:</span> {sess.disease_name or '—'}<br/>
  <span style="font-size:0.8rem;color:#666">
    Created: {sess.created_at.strftime('%d %b %Y')} &nbsp;|&nbsp;
    {len(med_entries)} medicine entr{'y' if len(med_entries) == 1 else 'ies'}
  </span>
</div>
""",
                        unsafe_allow_html=True,
                    )
                    btn_col1, btn_col2, _ = st.columns([1, 1, 4])
                    with btn_col1:
                        if not is_active and st.button(
                            "Switch to this", key=f"switch_{sid}"
                        ):
                            st.session_state.active_crop_session_id = sid
                            set_chat_mode(
                                "ACTIVE_TREATMENT" if sess.disease_name else "ONBOARDING"
                            )
                            st.rerun()
                    with btn_col2:
                        if st.button("Delete", key=f"del_sess_{sid}"):
                            persistence.delete_session(sid)
                            del st.session_state.crop_sessions[sid]
                            if st.session_state.active_crop_session_id == sid:
                                st.session_state.active_crop_session_id = next(
                                    iter(st.session_state.crop_sessions), None
                                )
                            set_chat_mode("ONBOARDING")
                            st.rerun()
                    st.write("")

        if st.button("Back", key="past_sessions_back"):
            set_chat_mode("ONBOARDING")
            st.rerun()

    # ------------------------------------------------------------------ #
    # MEDICINE_TABLE — focused medicine tracking panel                    #
    # ------------------------------------------------------------------ #
    elif mode == "MEDICINE_TABLE":
        if not session.disease_name:
            st.info(
                "No diagnosis has been made for this session yet. "
                "Analyse a crop image first, then return here to manage your treatment log."
            )
        else:
            render_tracking_panel(session.session_id, session.disease_name)

        if st.button("Back", key="med_table_back"):
            set_chat_mode("ONBOARDING")
            st.rerun()


# ---------------------------------------------------------------------------
# Runtime helpers
# ---------------------------------------------------------------------------

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
