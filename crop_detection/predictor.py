"""YOLOv5 model loading, inference, annotation, and result assembly."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFont

from crop_detection.disease_logic import (
    Detection,
    display_disease_name,
    select_crop,
    select_disease,
)
from crop_detection.solutions import get_recommendation

CROP_INFERENCE_THRESHOLD = 0.4
DISEASE_INFERENCE_THRESHOLD = 0.10
INFERENCE_IMAGE_SIZE = 640


class ModelLoadError(RuntimeError):
    """Raised when a YOLOv5 model cannot be initialized."""


@dataclass(frozen=True)
class AnalysisResult:
    crop_name: str
    crop_confidence: float
    crop_was_assumed: bool
    disease_name: str
    disease_confidence: float
    disease_was_fallback: bool
    recommendation: str | None
    annotated_image: Image.Image
    output_path: Path
    all_disease_detections: tuple[Detection, ...]  # raw post-threshold YOLO output before top-1 selection


class ModelManager:
    """Load each YOLOv5 model at most once and route by crop."""

    def __init__(
        self,
        crop_weights: Path,
        corn_weights: Path,
        grape_weights: Path,
        outputs_dir: Path,
        yolov5_repo: Path | None = None,
    ) -> None:
        self.crop_weights = crop_weights
        self.corn_weights = corn_weights
        self.grape_weights = grape_weights
        self.outputs_dir = outputs_dir
        self.yolov5_repo = yolov5_repo
        self._models: dict[str, Any] = {}

    @classmethod
    def from_project_root(cls, project_root: Path) -> "ModelManager":
        models_dir = project_root / "models"
        repo = _find_local_yolov5_repo(project_root)
        return cls(
            crop_weights=models_dir / "crop_detector.pt",
            corn_weights=models_dir / "corn_disease.pt",
            grape_weights=models_dir / "grape_disease.pt",
            outputs_dir=project_root / "outputs",
            yolov5_repo=repo,
        )

    def crop_model(self) -> Any:
        return self._get_or_load("crop", self.crop_weights, CROP_INFERENCE_THRESHOLD)

    def disease_model(self, crop_name: str) -> Any:
        if crop_name == "Corn":
            return self._get_or_load(
                "corn",
                self.corn_weights,
                DISEASE_INFERENCE_THRESHOLD,
            )
        return self._get_or_load(
            "grape",
            self.grape_weights,
            DISEASE_INFERENCE_THRESHOLD,
        )

    def _get_or_load(self, key: str, path: Path, confidence: float) -> Any:
        if key not in self._models:
            self._models[key] = load_yolov5_model(
                path,
                confidence=confidence,
                yolov5_repo=self.yolov5_repo,
            )
        return self._models[key]


def _find_local_yolov5_repo(project_root: Path) -> Path | None:
    configured = os.getenv("YOLOV5_REPO")
    candidates = [
        Path(configured).expanduser() if configured else None,
        project_root / "yolov5",
        project_root.parent / "yolov5",
    ]
    for candidate in candidates:
        if candidate and (candidate / "hubconf.py").is_file():
            return candidate.resolve()
    return None


def load_yolov5_model(
    weights_path: Path,
    confidence: float,
    yolov5_repo: Path | None = None,
) -> Any:
    """Load custom YOLOv5 weights from a local repository or Torch Hub."""
    weights_path = weights_path.resolve()
    if not weights_path.is_file():
        raise FileNotFoundError(
            f"Required model file is missing: {weights_path}. "
            "See README.md for model placement instructions."
        )

    try:
        import torch
    except ImportError as exc:
        raise ModelLoadError(
            "PyTorch is not installed. Run: pip install -r requirements.txt"
        ) from exc

    # These are user-supplied, trusted YOLOv5 checkpoints containing model objects.
    os.environ.setdefault("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", "1")

    try:
        if yolov5_repo:
            model = torch.hub.load(
                str(yolov5_repo),
                "custom",
                path=str(weights_path),
                source="local",
                verbose=False,
            )
        else:
            model = torch.hub.load(
                "ultralytics/yolov5",
                "custom",
                path=str(weights_path),
                trust_repo=True,
                verbose=False,
            )
    except Exception as exc:
        source_hint = (
            f"local YOLOv5 repository at {yolov5_repo}"
            if yolov5_repo
            else "the official ultralytics/yolov5 Torch Hub repository"
        )
        raise ModelLoadError(
            f"Could not load {weights_path.name} using {source_hint}. "
            "Verify the checkpoint, dependencies, and YOLOv5 repository setup. "
            f"Original error: {exc}"
        ) from exc

    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    model.to(device)
    model.eval()
    model.conf = confidence
    return model


def run_inference(model: Any, image: Image.Image) -> list[Detection]:
    """Run one model and convert its tensor output into plain detections."""
    try:
        results = model(image, size=INFERENCE_IMAGE_SIZE)
        predictions = results.xyxy[0].detach().cpu().tolist()
    except Exception as exc:
        raise RuntimeError(f"YOLOv5 inference failed: {exc}") from exc

    names = model.names
    detections: list[Detection] = []
    for x1, y1, x2, y2, confidence, class_id in predictions:
        index = int(class_id)
        class_name = names[index] if not isinstance(names, dict) else names[index]
        detections.append(
            Detection(
                class_name=str(class_name),
                confidence=float(confidence),
                box=(float(x1), float(y1), float(x2), float(y2)),
            )
        )
    return detections


def create_grayscale_copy(image: Image.Image) -> Image.Image:
    """Return an RGB grayscale copy without modifying the original image."""
    return image.convert("L").convert("RGB")


def analyze_image(image: Image.Image, manager: ModelManager) -> AnalysisResult:
    """Run crop detection, route disease inference, and annotate the result."""
    crop_input = create_grayscale_copy(image)
    crop_detections = run_inference(manager.crop_model(), crop_input)
    crop = select_crop(crop_detections)

    # Disease models were trained on color images, so retain the original input.
    disease_detections = run_inference(manager.disease_model(crop.name), image)
    disease = select_disease(crop.name, disease_detections)
    # Preserve full detection list before top-1 selection for LLM context.

    annotated = image.copy()
    if crop.selected_detection:
        _draw_detection(
            annotated,
            crop.selected_detection,
            crop.name,
            color=(34, 139, 34),
        )
    for detection in disease.selected_detections:
        _draw_detection(
            annotated,
            detection,
            display_disease_name(disease.name),
            color=(220, 53, 69),
        )

    manager.outputs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = manager.outputs_dir / f"analysis_{timestamp}_{uuid4().hex[:8]}.jpg"
    annotated.save(output_path, format="JPEG", quality=92)

    return AnalysisResult(
        crop_name=crop.name,
        crop_confidence=crop.confidence,
        crop_was_assumed=crop.was_assumed,
        disease_name=display_disease_name(disease.name),
        disease_confidence=disease.confidence,
        disease_was_fallback=disease.used_fallback,
        recommendation=get_recommendation(disease.name),
        annotated_image=annotated,
        output_path=output_path,
        all_disease_detections=tuple(disease_detections),
    )


def _draw_detection(
    image: Image.Image,
    detection: Detection,
    label: str,
    color: tuple[int, int, int],
) -> None:
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    x1, y1, x2, y2 = detection.box
    line_width = max(2, round(min(image.size) / 250))
    draw.rectangle((x1, y1, x2, y2), outline=color, width=line_width)

    text = f"{label} {detection.confidence:.1%}"
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    text_width = right - left
    text_height = bottom - top
    padding = max(3, line_width)
    text_x = max(0, x1)
    text_y = max(0, y1 - text_height - 2 * padding)
    draw.rectangle(
        (
            text_x,
            text_y,
            min(image.width, text_x + text_width + 2 * padding),
            text_y + text_height + 2 * padding,
        ),
        fill=color,
    )
    draw.text(
        (text_x + padding, text_y + padding),
        text,
        fill=(255, 255, 255),
        font=font,
    )
