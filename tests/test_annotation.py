from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.detection.annotation import (
    ANNOTATION_STATUS_ANNOTATED,
    ANNOTATION_STATUS_NO_TARGET,
    ANNOTATION_STATUS_PENDING,
    ANNOTATION_TOOL_VERSION,
    HumanAnnotationManifest,
    HumanAnnotationRecord,
    HumanPolygonAnnotation,
    create_annotation_manifest_from_prep,
    load_annotation_manifest,
    write_annotation_manifest,
)
from src.detection.annotation_validator import (
    validate_annotation_manifest,
    validate_annotation_record,
    validate_polygon,
)
from src.detection.dataset import PolygonPoint


def polygon(*points: tuple[float, float]) -> tuple[PolygonPoint, ...]:
    return tuple(
        PolygonPoint(x=x, y=y)
        for x, y in points
    )


def test_valid_polygon():
    result = validate_polygon(
        polygon(
            (0.1, 0.1),
            (0.8, 0.1),
            (0.8, 0.8),
            (0.1, 0.8),
        )
    )

    assert result.valid
    assert result.errors == ()


def test_polygon_requires_three_points():
    result = validate_polygon(
        polygon(
            (0.1, 0.1),
            (0.8, 0.1),
        )
    )

    assert not result.valid


def test_polygon_point_rejects_out_of_bounds():
    with pytest.raises(ValueError, match="polygon x must be normalized"):
        PolygonPoint(x=-0.1, y=0.1)


def test_polygon_rejects_duplicate_closure():
    result = validate_polygon(
        polygon(
            (0.1, 0.1),
            (0.8, 0.1),
            (0.8, 0.8),
            (0.1, 0.1),
        )
    )

    assert not result.valid


def test_polygon_rejects_self_intersection():
    result = validate_polygon(
        polygon(
            (0.1, 0.1),
            (0.9, 0.9),
            (0.1, 0.9),
            (0.9, 0.1),
        )
    )

    assert not result.valid


def test_polygon_rejects_tiny_area():
    result = validate_polygon(
        polygon(
            (0.1, 0.1),
            (0.1001, 0.1),
            (0.1, 0.1001),
        )
    )

    assert not result.valid


def test_multiple_polygons_allowed():
    record = HumanAnnotationRecord(
        image_id="1",
        relative_path="images/positive/1.jpeg",
        category="positive",
        scene_group="scene-1",
        image_width=1600,
        image_height=1200,
        status=ANNOTATION_STATUS_ANNOTATED,
        annotator="ops",
        annotations=[
            HumanPolygonAnnotation(
                annotation_id="a1",
                class_name="wall_surface",
                polygon=polygon(
                    (0.1, 0.1),
                    (0.4, 0.1),
                    (0.4, 0.4),
                    (0.1, 0.4),
                ),
                annotator="ops",
            ),
            HumanPolygonAnnotation(
                annotation_id="a2",
                class_name="wall_surface",
                polygon=polygon(
                    (0.5, 0.5),
                    (0.9, 0.5),
                    (0.9, 0.9),
                    (0.5, 0.9),
                ),
                annotator="ops",
            ),
        ],
    )

    result = validate_annotation_record(record)

    assert result.valid
    assert len(record.annotations) == 2


def test_negative_is_no_target():
    record = HumanAnnotationRecord(
        image_id="7",
        relative_path="images/negative/7.jpeg",
        category="negative",
        scene_group="scene-7",
        image_width=1600,
        image_height=1200,
        status=ANNOTATION_STATUS_NO_TARGET,
        annotator="ops",
        annotations=[],
    )

    result = validate_annotation_record(record)

    assert result.valid


def test_negative_cannot_have_polygon():
    with pytest.raises(ValueError):
        HumanAnnotationRecord(
            image_id="7",
            relative_path="images/negative/7.jpeg",
            category="negative",
            scene_group="scene-7",
            image_width=1600,
            image_height=1200,
            status=ANNOTATION_STATUS_NO_TARGET,
            annotator="ops",
            annotations=[
                HumanPolygonAnnotation(
                    annotation_id="bad",
                    class_name="wall_surface",
                    polygon=polygon(
                        (0.1, 0.1),
                        (0.8, 0.1),
                        (0.8, 0.8),
                    ),
                    annotator="ops",
                )
            ],
        )


def test_pending_positive_is_allowed():
    record = HumanAnnotationRecord(
        image_id="1",
        relative_path="images/positive/1.jpeg",
        category="positive",
        scene_group="scene-1",
        image_width=1600,
        image_height=1200,
        status=ANNOTATION_STATUS_PENDING,
        annotator=None,
        annotations=[],
    )

    result = validate_annotation_record(record)

    assert result.valid
    assert result.warnings


def test_manifest_split_must_remain_unassigned(tmp_path: Path):
    manifest = HumanAnnotationManifest(
        annotation_tool_version=ANNOTATION_TOOL_VERSION,
        polygon_format_version="1.0",
        dataset_version="4.2.0",
        annotation_version="1.0.0",
        name="test",
        source_prep_manifest="prep.json",
        split="unassigned",
        images=[],
    )

    result = validate_annotation_manifest(manifest)

    assert result.valid

    payload = manifest.as_dict()

    assert payload["split"] == "unassigned"


def test_manifest_round_trip(tmp_path: Path):
    path = tmp_path / "annotations.json"

    manifest = HumanAnnotationManifest(
        annotation_tool_version=ANNOTATION_TOOL_VERSION,
        polygon_format_version="1.0",
        dataset_version="4.2.0",
        annotation_version="1.0.0",
        name="test",
        source_prep_manifest="prep.json",
        split="unassigned",
        images=[
            HumanAnnotationRecord(
                image_id="7",
                relative_path="images/negative/7.jpeg",
                category="negative",
                scene_group="scene-7",
                image_width=1600,
                image_height=1200,
                status=ANNOTATION_STATUS_NO_TARGET,
                annotator="ops",
                annotations=[],
            )
        ],
    )

    write_annotation_manifest(manifest, path)

    loaded = load_annotation_manifest(path)

    assert loaded.image_count == 1
    assert loaded.images[0].image_id == "7"
    assert loaded.images[0].status == ANNOTATION_STATUS_NO_TARGET


def test_create_manifest_from_prep(tmp_path: Path):
    prep = tmp_path / "annotation_prep_manifest.json"

    prep.write_text(
        json.dumps(
            {
                "dataset_version": "4.2.0",
                "annotation_version": "1.0.0",
                "tasks": [
                    {
                        "image_id": "1",
                        "relative_path": "images/positive/1.jpeg",
                        "category": "positive",
                        "scene_group": "scene-1",
                        "image_width": 1600,
                        "image_height": 1200,
                        "source": "reference",
                        "notes": "",
                    },
                    {
                        "image_id": "7",
                        "relative_path": "images/negative/7.jpeg",
                        "category": "negative",
                        "scene_group": "scene-7",
                        "image_width": 1600,
                        "image_height": 1200,
                        "source": "reference",
                        "notes": "",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    manifest = create_annotation_manifest_from_prep(prep)

    assert manifest.image_count == 2
    assert manifest.images[0].status == ANNOTATION_STATUS_PENDING
    assert manifest.images[1].status == ANNOTATION_STATUS_NO_TARGET
    assert manifest.split == "unassigned"
