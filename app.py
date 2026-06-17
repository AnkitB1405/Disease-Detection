"""Streamlit entry point for the Crop Disease Detection Prototype."""

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
    """Validate an uploaded file and return a normalized RGB image."""
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
    """Render and run the Streamlit application."""
    import streamlit as st
    from streamlit_webrtc import VideoProcessorBase, WebRtcMode, webrtc_streamer

    from crop_detection.disease_logic import select_crop
    from crop_detection.predictor import (
        ModelLoadError,
        ModelManager,
        analyze_image,
        create_grayscale_copy,
        run_inference,
    )

    st.set_page_config(
        page_title="Crop Disease Detection System",
        layout="wide",
    )

    st.title("Crop Disease Detection System")

    @st.cache_resource(show_spinner="Loading YOLOv5 models...")
    def get_model_manager() -> ModelManager:
        return ModelManager.from_project_root(PROJECT_ROOT)

    if "latest_frame" not in st.session_state:
        st.session_state.latest_frame = None

    if "captured_frame" not in st.session_state:
        st.session_state.captured_frame = None

    if "latest_detection" not in st.session_state:
        st.session_state.latest_detection = None

    tabs = st.tabs(["Upload Image", "Live Camera"])

    with tabs[0]:
        st.write(
            "Upload a clear image of a corn or grape leaf to identify the crop "
            "and screen it for supported diseases."
        )

        uploaded_file = st.file_uploader(
            "Upload a leaf image",
            type=["jpg", "jpeg", "png", "webp"],
            help="Supported formats: JPG, JPEG, PNG, and WEBP. Maximum size: 15 MB.",
        )

        if uploaded_file is not None:
            try:
                image = load_uploaded_image(uploaded_file)
            except ValueError as exc:
                st.error(str(exc))
            else:
                preview_column, action_column = st.columns([3, 2], gap="large")

                with preview_column:
                    st.subheader("Uploaded Image")
                    st.image(image, use_container_width=True)

                with action_column:
                    st.subheader("Analysis")
                    st.write(
                        "A grayscale copy is checked for Corn first. When Corn is not "
                        "detected, the original image is intentionally routed to the "
                        "Grape disease model."
                    )
                    analyze_clicked = st.button(
                        "Analyze Image",
                        type="primary",
                        use_container_width=True,
                        key="upload_analyze_button",
                    )

                if analyze_clicked:
                    try:
                        with st.spinner("Analyzing the leaf..."):
                            result = analyze_image(image, get_model_manager())
                    except FileNotFoundError as exc:
                        st.error(str(exc))
                        st.caption(
                            "Place all required `.pt` files in the models directory, then "
                            "restart the application."
                        )
                    except ModelLoadError as exc:
                        st.error(str(exc))
                    except Exception:
                        LOGGER.exception("Unexpected image-analysis failure")
                        st.error(
                            "Analysis could not be completed. Check the terminal log for "
                            "details and verify that the model files are valid YOLOv5 weights."
                        )
                    else:
                        _display_analysis_result(st, result)

    with tabs[1]:
        st.write(
            "Live crop detection preview. Disease analysis only runs after capturing a frame."
        )

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
                        detections = run_inference(
                            manager.crop_model(),
                            gray_image,
                        )
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

                    draw.rectangle(
                        (x1, y1, x2, y2),
                        outline=(0, 255, 0),
                        width=3,
                    )

                    label = (
                        f"Leaf Detected "
                        f"{detection['confidence'] * 100:.1f}%"
                    )

                    draw.text(
                        (max(0, x1), max(0, y1 - 20)),
                        label,
                        fill=(0, 255, 0),
                        font=self.font,
                    )
                else:
                    draw.text(
                        (20, 20),
                        "Searching for leaf...",
                        fill=(255, 0, 0),
                        font=self.font,
                    )

                return av.VideoFrame.from_ndarray(
                    np.array(annotated),
                    format="rgb24",
                )

        ctx = webrtc_streamer(
            key="live-camera",
            mode=WebRtcMode.SENDRECV,
            video_processor_factory=VideoProcessor,
            media_stream_constraints={"video": True, "audio": False},
            async_processing=True,
        )

        if ctx and ctx.video_processor:

            latest_frame = getattr(
                ctx.video_processor,
                "latest_frame",
                None,
            )

            if latest_frame is not None:
                st.session_state.latest_frame = latest_frame.copy()

        if st.button(
            "Capture Frame",
            type="primary",
            use_container_width=True,
            key="capture_frame_button",
        ):
            if st.session_state.latest_frame is None:
                st.warning("No frame available yet.")
            else:
                st.session_state.captured_frame = (
                    st.session_state.latest_frame.copy()
                )

        if st.session_state.captured_frame is not None:
            st.subheader("Captured Frame")
            st.image(
                st.session_state.captured_frame,
                use_container_width=True,
            )

            if st.button(
                "Analyze Captured Frame",
                type="primary",
                use_container_width=True,
                key="analyze_captured_frame",
            ):
                try:
                    with st.spinner("Analyzing captured frame..."):
                        result = analyze_image(
                            st.session_state.captured_frame,
                            get_model_manager(),
                        )
                except FileNotFoundError as exc:
                    st.error(str(exc))
                except ModelLoadError as exc:
                    st.error(str(exc))
                except Exception:
                    LOGGER.exception("Captured-frame analysis failed")
                    st.error(
                        "Analysis could not be completed. Check the terminal log for details."
                    )
                else:
                    _display_analysis_result(st, result)


def _display_analysis_result(st, result) -> None:
    st.divider()
    st.subheader("Detection Result")

    crop_column, disease_column = st.columns(2, gap="large")

    with crop_column:
        st.metric("Crop", result.crop_name)
        st.metric("Crop Confidence", f"{result.crop_confidence:.1%}")

        if result.crop_was_assumed:
            st.caption(
                "Grape was assumed because no Corn detection was found."
            )

    with disease_column:
        st.metric("Disease", result.disease_name)
        st.metric("Disease Confidence", f"{result.disease_confidence:.1%}")

        if result.disease_was_fallback:
            st.caption(
                "Healthy fallback applied because no qualifying disease was found."
            )

    if result.recommendation:
        st.warning(f"**Recommended Action:**\n\n{result.recommendation}")
        st.caption(
            "Use this result as a screening aid. Confirm disease and pesticide "
            "choices with a local agricultural extension professional."
        )
    else:
        st.success(
            "No disease treatment recommendation is needed for this result."
        )

    st.subheader("Annotated Image")
    st.image(
        result.annotated_image,
        caption="Selected crop and disease detections",
        use_container_width=True,
    )

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
    """Run the UI directly or launch Streamlit when invoked with Python."""
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
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(Path(__file__).resolve()),
        *sys.argv[1:],
    ]
    raise SystemExit(subprocess.call(command))


if __name__ == "__main__":
    launch()
