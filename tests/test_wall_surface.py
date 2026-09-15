from __future__ import annotations

from pathlib import Path

import pytest

from src.detection.wall_surface import (
    ANNOTATION_POLYGON,
    ANNOTATION_VISUAL_REFERENCE,
    REFERENCE_CATEGORY_HARD_NEGATIVE,
    REFERENCE_CATEGORY_POSITIVE,
    WallSurfaceModelConfig,
    WallSurfaceReference,
    is_wall_surface_class,
    validate_reference_image_path,
)


def test_default_model_config() -> None:
    config = WallSurfaceModelConfig()

    assert config.confidence_threshold == 0.25
    assert config.class_name == "wall_surface"
    assert config.prefer_polygon is True


def test_model_config_rejects_invalid_threshold() -> None:
    with pytest.raises(ValueError):
        WallSurfaceModelConfig(confidence_threshold=1.1)


def test_model_config_rejects_negative_threshold() -> None:
    with pytest.raises(ValueError):
        WallSurfaceModelConfig(confidence_threshold=-0.1)


def test_reference_requires_image_path() -> None:
    with pytest.raises(ValueError):
        WallSurfaceReference(
            image_path="",
            category=REFERENCE_CATEGORY_POSITIVE,
            annotation_status=ANNOTATION_VISUAL_REFERENCE,
            source="highrise_reference_set",
        )


def test_reference_accepts_visual_reference() -> None:
    reference = WallSurfaceReference(
        image_path="1.jpeg",
        category=REFERENCE_CATEGORY_POSITIVE,
        annotation_status=ANNOTATION_VISUAL_REFERENCE,
        source="highrise_reference_set",
        notes="Upper-floor advertising wall reference.",
    )

    assert reference.image_path == "1.jpeg"
    assert reference.category == REFERENCE_CATEGORY_POSITIVE
    assert reference.annotation_status == ANNOTATION_VISUAL_REFERENCE


def test_hard_negative_category_is_supported() -> None:
    reference = WallSurfaceReference(
        image_path="shopfront.jpeg",
        category=REFERENCE_CATEGORY_HARD_NEGATIVE,
        annotation_status=ANNOTATION_POLYGON,
        source="highrise_reference_set",
    )

    assert reference.category == REFERENCE_CATEGORY_HARD_NEGATIVE


def test_wall_surface_class_matching() -> None:
    assert is_wall_surface_class("wall_surface")
    assert is_wall_surface_class(" WALL_SURFACE ")
    assert not is_wall_surface_class("building")
    assert not is_wall_surface_class("facade")


def test_reference_image_path_validation(tmp_path: Path) -> None:
    image_path = tmp_path / "reference.jpeg"
    image_path.write_bytes(b"placeholder")

    result = validate_reference_image_path(image_path)

    assert result == image_path


def test_reference_image_path_rejects_missing_file(
    tmp_path: Path,
) -> None:
    with pytest.raises(FileNotFoundError):
        validate_reference_image_path(
            tmp_path / "missing.jpeg"
        )


def test_reference_image_path_rejects_non_image(
    tmp_path: Path,
) -> None:
    text_path = tmp_path / "reference.txt"
    text_path.write_text("not an image")

    with pytest.raises(ValueError):
        validate_reference_image_path(text_path)
