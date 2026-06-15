"""Focused tests for routing and fallback rules."""

from crop_detection.disease_logic import Detection, select_crop, select_disease


def detection(name: str, confidence: float) -> Detection:
    return Detection(name, confidence, (0.0, 0.0, 10.0, 10.0))


def test_corn_is_selected_even_when_grape_confidence_is_higher() -> None:
    result = select_crop(
        [detection("Corn", 0.61), detection("Grape", 0.98)]
    )
    assert result.name == "Corn"
    assert result.confidence == 0.61
    assert not result.was_assumed


def test_grape_is_assumed_when_corn_is_not_detected() -> None:
    result = select_crop([])
    assert result.name == "Grape"
    assert result.confidence == 0.0
    assert result.was_assumed


def test_non_corn_detection_is_ignored_by_single_class_crop_logic() -> None:
    result = select_crop([detection("Grape", 0.98)])
    assert result.name == "Grape"
    assert result.confidence == 0.0
    assert result.selected_detection is None
    assert result.was_assumed


def test_corn_uses_highest_confidence_disease() -> None:
    result = select_disease(
        "Corn",
        [detection("rust", 0.72), detection("gray_leaf", 0.43)],
    )
    assert result.name == "rust"
    assert result.confidence == 0.72
    assert not result.used_fallback


def test_corn_empty_prediction_falls_back_to_healthy() -> None:
    result = select_disease("Corn", [])
    assert result.name == "healthy"
    assert result.confidence == 0.0
    assert result.used_fallback


def test_low_confidence_grape_disease_falls_back_to_healthy() -> None:
    result = select_disease("Grape", [detection("Black Rot", 0.39)])
    assert result.name == "Healthy Grape Vine"
    assert result.confidence == 0.0
    assert result.used_fallback


def test_embedded_grape_checkpoint_labels_are_normalized() -> None:
    result = select_disease("Grape", [detection("Black Rot", 0.84)])
    assert result.name == "Black Rot Grape Vine"
    assert result.confidence == 0.84
    assert not result.used_fallback
