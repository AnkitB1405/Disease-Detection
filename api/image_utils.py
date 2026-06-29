"""Upload validation — ported from app.load_uploaded_image(), Streamlit-free.

Same checks the Streamlit prototype performed, applied to raw bytes received
over multipart/form-data instead of a Streamlit UploadedFile.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_UPLOAD_BYTES = 15 * 1024 * 1024


class InvalidImageError(ValueError):
    """Raised when an uploaded file fails validation. Maps to HTTP 400."""


def load_image_from_bytes(image_bytes: bytes, filename: str) -> Image.Image:
    """Validate and decode an uploaded image into a loaded RGB PIL image."""
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise InvalidImageError(
            "Unsupported file type. Upload a JPG, JPEG, PNG, or WEBP image."
        )
    if not image_bytes:
        raise InvalidImageError("The uploaded file is empty.")
    if len(image_bytes) > MAX_UPLOAD_BYTES:
        raise InvalidImageError("The image is larger than the 15 MB upload limit.")
    try:
        with Image.open(io.BytesIO(image_bytes)) as candidate:
            candidate.verify()
        with Image.open(io.BytesIO(image_bytes)) as candidate:
            image = ImageOps.exif_transpose(candidate).convert("RGB")
            image.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise InvalidImageError("The uploaded file is not a valid readable image.") from exc
    if image.width < 16 or image.height < 16:
        raise InvalidImageError("The image is too small. Use an image at least 16 x 16 pixels.")
    return image
