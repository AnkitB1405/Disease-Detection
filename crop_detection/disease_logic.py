"""Pure decision logic for crop routing and disease fallbacks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

GRAPE_CONF_THRESHOLD = 0.40


@dataclass(frozen=True)
class Detection:
    """One normalized YOLO detection."""

    class_name: str
    confidence: float
    box: tuple[float, float, float, float]


@dataclass(frozen=True)
class CropDecision:
    name: str
    confidence: float
    selected_detection: Detection | None
    was_assumed: bool


@dataclass(frozen=True)
class DiseaseDecision:
    name: str
    confidence: float
    selected_detections: tuple[Detection, ...]
    used_fallback: bool


def _label_key(label: str) -> str:
    return " ".join(label.replace("_", " ").replace("-", " ").lower().split())


CROP_ALIASES = {
    "corn": "Corn",
    "maize": "Corn",
}

CORN_DISEASE_ALIASES = {
    "healthy": "healthy",
    "gray leaf": "gray_leaf",
    "gray leaf spot": "gray_leaf",
    "grey leaf": "gray_leaf",
    "grey leaf spot": "gray_leaf",
    "blight": "blight",
    "rust": "rust",
}

GRAPE_DISEASE_ALIASES = {
    "healthy": "Healthy Grape Vine",
    "healthy grape": "Healthy Grape Vine",
    "healthy grape vine": "Healthy Grape Vine",
    "black rot": "Black Rot Grape Vine",
    "black rot grape": "Black Rot Grape Vine",
    "black rot grape vine": "Black Rot Grape Vine",
    "blight": "Blight Grape Vine",
    "blight grape": "Blight Grape Vine",
    "blight grape vine": "Blight Grape Vine",
}

DISPLAY_DISEASE_NAMES = {
    "healthy": "Healthy",
    "gray_leaf": "Gray Leaf Spot",
    "blight": "Blight",
    "rust": "Rust",
    "Healthy Grape Vine": "Healthy Grape Vine",
    "Black Rot Grape Vine": "Black Rot Grape Vine",
    "Blight Grape Vine": "Blight Grape Vine",
}

HEALTHY_DISEASES = {"healthy", "Healthy Grape Vine"}


def select_crop(detections: Iterable[Detection]) -> CropDecision:
    """Select Corn from the single-class detector; otherwise assume Grape."""
    normalized = [
        (CROP_ALIASES.get(_label_key(item.class_name)), item) for item in detections
    ]
    corn_detections = [item for name, item in normalized if name == "Corn"]
    if corn_detections:
        selected = max(corn_detections, key=lambda item: item.confidence)
        return CropDecision("Corn", selected.confidence, selected, False)

    return CropDecision(
        name="Grape",
        confidence=0.0,
        selected_detection=None,
        was_assumed=True,
    )


def select_disease(
    crop_name: str,
    detections: Iterable[Detection],
) -> DiseaseDecision:
    """Apply the crop-specific highest-confidence and fallback rules."""
    aliases = (
        CORN_DISEASE_ALIASES if crop_name == "Corn" else GRAPE_DISEASE_ALIASES
    )
    canonical = [
        (aliases.get(_label_key(item.class_name)), item) for item in detections
    ]
    valid = [(name, item) for name, item in canonical if name is not None]

    if crop_name == "Corn":
        if not valid:
            return DiseaseDecision("healthy", 0.0, (), True)
        disease_name, selected = max(valid, key=lambda pair: pair[1].confidence)
        same_class = tuple(
            item for name, item in valid if name == disease_name
        )
        return DiseaseDecision(
            disease_name,
            selected.confidence,
            same_class,
            False,
        )

    if not valid:
        return DiseaseDecision("Healthy Grape Vine", 0.0, (), True)

    disease_name, selected = max(valid, key=lambda pair: pair[1].confidence)
    if selected.confidence < GRAPE_CONF_THRESHOLD:
        return DiseaseDecision("Healthy Grape Vine", 0.0, (), True)

    same_class = tuple(item for name, item in valid if name == disease_name)
    return DiseaseDecision(
        disease_name,
        selected.confidence,
        same_class,
        False,
    )


def display_disease_name(canonical_name: str) -> str:
    return DISPLAY_DISEASE_NAMES.get(canonical_name, canonical_name)


def is_healthy(canonical_name: str) -> bool:
    return canonical_name in HEALTHY_DISEASES
