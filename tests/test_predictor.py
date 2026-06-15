"""Focused tests for crop preprocessing and inference routing."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

import crop_detection.predictor as predictor


class FakeManager:
    outputs_dir = Path("/tmp/crop-detection-test-outputs")

    def crop_model(self) -> str:
        return "crop-model"

    def disease_model(self, crop_name: str) -> str:
        assert crop_name == "Grape"
        return "grape-disease-model"


def test_grayscale_copy_preserves_original() -> None:
    original = Image.new("RGB", (1, 1), (255, 0, 0))

    grayscale = predictor.create_grayscale_copy(original)

    assert grayscale is not original
    assert grayscale.mode == "RGB"
    assert grayscale.getpixel((0, 0))[0] == grayscale.getpixel((0, 0))[1]
    assert grayscale.getpixel((0, 0))[1] == grayscale.getpixel((0, 0))[2]
    assert original.getpixel((0, 0)) == (255, 0, 0)


def test_crop_uses_grayscale_but_disease_uses_original(
    monkeypatch,
    tmp_path: Path,
) -> None:
    original = Image.new("RGB", (16, 16), (255, 0, 0))
    seen_images: list[Image.Image] = []
    manager = FakeManager()
    manager.outputs_dir = tmp_path

    def fake_inference(model: str, image: Image.Image):
        seen_images.append(image)
        return []

    monkeypatch.setattr(predictor, "run_inference", fake_inference)
    predictor.analyze_image(original, manager)

    crop_pixel = seen_images[0].getpixel((0, 0))
    assert crop_pixel[0] == crop_pixel[1] == crop_pixel[2]
    assert seen_images[1] is original
    assert original.getpixel((0, 0)) == (255, 0, 0)
