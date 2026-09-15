from __future__ import annotations

import json

import pytest

from src.detection.dataset import (
    ANNOTATION_POLYGON,
    CATEGORY_HARD_NEGATIVE,
    CATEGORY_NEGATIVE,
    CATEGORY_POSITIVE,
    DatasetManifest,
    PolygonPoint,
    ReferenceImageRecord,
    WallSurfaceAnnotation,
    normalize_image_id,
    write_manifest,
)
from src.detection.dataset_validator import validate_dataset_files


SHA = "a" * 64


def polygon(annotation_id: str = "ann-001") -> WallSurfaceAnnotation:
    return WallSurfaceAnnotation(
        annotation_id=annotation_id,
        class_name="wall_surface",
        annotation_type=ANNOTATION_POLYGON,
        polygon=(
            PolygonPoint(0.1, 0.1),
            PolygonPoint(0.9, 0.1),
            PolygonPoint(0.9, 0.9),
            PolygonPoint(0.1, 0.9),
        ),
        annotator="ops523",
        source="manual_reference",
    )


def positive_image(
    *,
    image_id: str = "positive-001",
    split: str = "train",
    scene_group: str = "scene-001",
) -> ReferenceImageRecord:
    return ReferenceImageRecord(
        image_id=image_id,
        relative_path=f"images/positive/{image_id}.jpg",
        category=CATEGORY_POSITIVE,
        split=split,
        width=1920,
        height=1080,
        sha256=SHA,
        source="reference_upload",
        scene_group=scene_group,
        annotations=(polygon(),),
    )


def negative_image(
    *,
    image_id: str = "negative-001",
    category: str = CATEGORY_NEGATIVE,
    split: str = "train",
    scene_group: str = "scene-002",
) -> ReferenceImageRecord:
    return ReferenceImageRecord(
        image_id=image_id,
        relative_path=f"images/{category}/{image_id}.jpg",
        category=category,
        split=split,
        width=1920,
        height=1080,
        sha256=SHA,
        source="reference_upload",
        scene_group=scene_group,
    )


def test_image_id_is_normalized() -> None:
    assert normalize_image_id("Wall Image 01.JPG") == "wall_image_01.jpg"


def test_empty_image_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="valid character"):
        normalize_image_id("!!!")


def test_polygon_requires_three_points() -> None:
    with pytest.raises(ValueError, match="at least three"):
        WallSurfaceAnnotation(
            annotation_id="ann-001",
            class_name="wall_surface",
            annotation_type=ANNOTATION_POLYGON,
            polygon=(
                PolygonPoint(0.1, 0.1),
                PolygonPoint(0.9, 0.1),
            ),
            annotator="ops523",
            source="manual",
        )


def test_polygon_coordinates_are_normalized() -> None:
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        PolygonPoint(1.2, 0.5)


def test_positive_requires_annotation() -> None:
    with pytest.raises(ValueError, match="annotations"):
        ReferenceImageRecord(
            image_id="positive-001",
            relative_path="images/positive/positive-001.jpg",
            category=CATEGORY_POSITIVE,
            split="train",
            width=1920,
            height=1080,
            sha256=SHA,
            source="reference_upload",
            scene_group="scene-001",
        )


def test_negative_cannot_have_annotation() -> None:
    with pytest.raises(ValueError, match="must not contain"):
        ReferenceImageRecord(
            image_id="negative-001",
            relative_path="images/negative/negative-001.jpg",
            category=CATEGORY_NEGATIVE,
            split="train",
            width=1920,
            height=1080,
            sha256=SHA,
            source="reference_upload",
            scene_group="scene-002",
            annotations=(polygon(),),
        )


def test_hard_negative_cannot_have_annotation() -> None:
    with pytest.raises(ValueError, match="must not contain"):
        ReferenceImageRecord(
            image_id="hard-001",
            relative_path="images/hard_negative/hard-001.jpg",
            category=CATEGORY_HARD_NEGATIVE,
            split="train",
            width=1920,
            height=1080,
            sha256=SHA,
            source="reference_upload",
            scene_group="scene-003",
            annotations=(polygon(),),
        )


def test_duplicate_image_ids_are_rejected() -> None:
    image = positive_image()

    with pytest.raises(ValueError, match="duplicate image_id"):
        DatasetManifest(
            dataset_version="4.2.0",
            annotation_version="1.0.0",
            name="highrise_wall",
            images=(image, image),
        )


def test_scene_group_cannot_cross_splits() -> None:
    train = positive_image(
        image_id="positive-train",
        split="train",
        scene_group="same-scene",
    )

    test = negative_image(
        image_id="negative-test",
        split="test",
        scene_group="same-scene",
    )

    with pytest.raises(ValueError, match="multiple dataset splits"):
        DatasetManifest(
            dataset_version="4.2.0",
            annotation_version="1.0.0",
            name="highrise_wall",
            images=(train, test),
        )


def test_manifest_counts() -> None:
    manifest = DatasetManifest(
        dataset_version="4.2.0",
        annotation_version="1.0.0",
        name="highrise_wall",
        images=(
            positive_image(),
            negative_image(),
            negative_image(
                image_id="hard-001",
                category=CATEGORY_HARD_NEGATIVE,
            ),
        ),
    )

    assert manifest.image_count == 3
    assert manifest.annotation_count == 1
    assert manifest.split_counts()["train"] == 3


def test_manifest_serialization(tmp_path) -> None:
    manifest = DatasetManifest(
        dataset_version="4.2.0",
        annotation_version="1.0.0",
        name="highrise_wall",
        images=(positive_image(),),
    )

    output = tmp_path / "manifest.json"

    write_manifest(manifest, output)

    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["dataset_version"] == "4.2.0"
    assert payload["annotation_version"] == "1.0.0"
    assert payload["image_count"] == 1
    assert payload["annotation_count"] == 1
    assert payload["images"][0]["annotations"][0]["class_name"] == (
        "wall_surface"
    )


def test_dataset_validator_reports_missing_file(tmp_path) -> None:
    manifest = DatasetManifest(
        dataset_version="4.2.0",
        annotation_version="1.0.0",
        name="highrise_wall",
        images=(positive_image(),),
    )

    result = validate_dataset_files(
        manifest,
        tmp_path,
        verify_sha256=False,
    )

    assert result.valid is False
    assert "missing image" in result.errors[0]


def test_dataset_validator_accepts_matching_file(tmp_path) -> None:
    relative = "images/positive/positive-001.jpg"
    image_path = tmp_path / relative
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"reference")

    import hashlib

    actual_sha = hashlib.sha256(b"reference").hexdigest()

    image = ReferenceImageRecord(
        image_id="positive-001",
        relative_path=relative,
        category=CATEGORY_POSITIVE,
        split="train",
        width=1920,
        height=1080,
        sha256=actual_sha,
        source="reference_upload",
        scene_group="scene-001",
        annotations=(polygon(),),
    )

    manifest = DatasetManifest(
        dataset_version="4.2.0",
        annotation_version="1.0.0",
        name="highrise_wall",
        images=(image,),
    )

    result = validate_dataset_files(
        manifest,
        tmp_path,
        verify_sha256=True,
    )

    assert result.valid is True
    assert result.errors == ()


def test_dataset_validator_detects_checksum_mismatch(tmp_path) -> None:
    relative = "images/positive/positive-001.jpg"
    image_path = tmp_path / relative
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"reference")

    image = positive_image()

    manifest = DatasetManifest(
        dataset_version="4.2.0",
        annotation_version="1.0.0",
        name="highrise_wall",
        images=(image,),
    )

    result = validate_dataset_files(
        manifest,
        tmp_path,
        verify_sha256=True,
    )

    assert result.valid is False
    assert any("sha256 mismatch" in error for error in result.errors)
