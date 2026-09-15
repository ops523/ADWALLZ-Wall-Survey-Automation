from __future__ import annotations

import pytest

from src.detection.annotation import (
    ANNOTATION_STATUS_ANNOTATED,
    ANNOTATION_STATUS_NO_TARGET,
    ANNOTATION_TOOL_VERSION,
    HumanAnnotationManifest,
    HumanAnnotationRecord,
    HumanPolygonAnnotation,
)
from src.detection.dataset import PolygonPoint
from src.detection.dataset_split import (
    DatasetSplitManifest,
    DatasetSplitPolicy,
    SPLIT_TEST,
    SPLIT_TRAIN,
    SPLIT_VALIDATION,
    SplitAssignment,
    assess_dataset_readiness,
    build_split_manifest,
)


def polygon(
    *points: tuple[float, float],
) -> tuple[PolygonPoint, ...]:
    return tuple(
        PolygonPoint(x=x, y=y)
        for x, y in points
    )


def sample_polygon() -> tuple[PolygonPoint, ...]:
    return polygon(
        (0.10, 0.10),
        (0.30, 0.10),
        (0.30, 0.30),
        (0.10, 0.30),
    )


def record(
    image_id: str,
    category: str,
    scene_group: str,
    status: str,
) -> HumanAnnotationRecord:
    annotations = []

    if category == "positive" and status == ANNOTATION_STATUS_ANNOTATED:
        annotations = [
            HumanPolygonAnnotation(
                annotation_id=f"{image_id}-poly-1",
                class_name="wall_surface",
                polygon=sample_polygon(),
                annotator="ops",
            )
        ]

    return HumanAnnotationRecord(
        image_id=image_id,
        relative_path=f"images/{category}/{image_id}.jpeg",
        category=category,
        scene_group=scene_group,
        image_width=1600,
        image_height=1200,
        status=status,
        annotator="ops" if status != "pending" else None,
        annotations=annotations,
    )


def manifest(
    records: list[HumanAnnotationRecord],
) -> HumanAnnotationManifest:
    return HumanAnnotationManifest(
        annotation_tool_version=ANNOTATION_TOOL_VERSION,
        polygon_format_version="1.0",
        dataset_version="4.2.0",
        annotation_version="1.0.0",
        name="test",
        source_prep_manifest="prep.json",
        split="unassigned",
        images=records,
    )


def production_policy() -> DatasetSplitPolicy:
    return DatasetSplitPolicy(
        min_positive_images=3,
        min_non_positive_images=3,
    )


def test_current_seed_dataset_is_not_production_ready():
    records = [
        record(
            image_id=str(index),
            category="positive",
            scene_group=f"scene-{index}",
            status=ANNOTATION_STATUS_ANNOTATED,
        )
        for index in range(10)
    ]

    records.extend(
        record(
            image_id=f"n{index}",
            category="negative",
            scene_group=f"negative-scene-{index}",
            status=ANNOTATION_STATUS_NO_TARGET,
        )
        for index in range(12)
    )

    records.extend(
        record(
            image_id=f"h{index}",
            category="hard_negative",
            scene_group=f"hard-scene-{index}",
            status=ANNOTATION_STATUS_NO_TARGET,
        )
        for index in range(3)
    )

    result = assess_dataset_readiness(
        manifest(records)
    )

    assert not result.ready
    assert result.positive_count == 10
    assert result.negative_count == 12
    assert result.hard_negative_count == 3
    assert result.annotated_positive_count == 10
    assert result.no_target_count == 15
    assert result.warnings


def test_incomplete_positive_blocks_production_split():
    records = [
        record(
            image_id="1",
            category="positive",
            scene_group="scene-1",
            status=ANNOTATION_STATUS_ANNOTATED,
        ),
        record(
            image_id="2",
            category="positive",
            scene_group="scene-2",
            status="pending",
        ),
        record(
            image_id="n1",
            category="negative",
            scene_group="scene-n1",
            status=ANNOTATION_STATUS_NO_TARGET,
        ),
        record(
            image_id="n2",
            category="negative",
            scene_group="scene-n2",
            status=ANNOTATION_STATUS_NO_TARGET,
        ),
        record(
            image_id="n3",
            category="negative",
            scene_group="scene-n3",
            status=ANNOTATION_STATUS_NO_TARGET,
        ),
    ]

    result = assess_dataset_readiness(
        manifest(records),
        production_policy(),
    )

    assert not result.ready
    assert result.errors


def test_ready_dataset_can_be_split():
    records = []

    for index in range(6):
        records.append(
            record(
                image_id=f"p{index}",
                category="positive",
                scene_group=f"positive-scene-{index}",
                status=ANNOTATION_STATUS_ANNOTATED,
            )
        )

    for index in range(6):
        records.append(
            record(
                image_id=f"n{index}",
                category="negative",
                scene_group=f"negative-scene-{index}",
                status=ANNOTATION_STATUS_NO_TARGET,
            )
        )

    records.extend(
        [
            record(
                image_id="h0",
                category="hard_negative",
                scene_group="hard-scene-0",
                status=ANNOTATION_STATUS_NO_TARGET,
            ),
            record(
                image_id="h1",
                category="hard_negative",
                scene_group="hard-scene-1",
                status=ANNOTATION_STATUS_NO_TARGET,
            ),
        ]
    )

    source = manifest(records)
    policy = production_policy()

    readiness = assess_dataset_readiness(
        source,
        policy,
    )

    assert readiness.ready

    split_manifest = build_split_manifest(
        source,
        "manifests/highrise_wall_annotations.json",
        policy,
    )

    assert split_manifest.image_count == len(records)

    counts = split_manifest.split_counts()

    assert sum(counts.values()) == len(records)

    for assignment in split_manifest.assignments:
        assert assignment.split in {
            SPLIT_TRAIN,
            SPLIT_VALIDATION,
            SPLIT_TEST,
        }


def test_same_scene_cannot_cross_splits():
    records = []

    for index in range(6):
        records.append(
            record(
                image_id=f"p{index}",
                category="positive",
                scene_group=f"scene-{index}",
                status=ANNOTATION_STATUS_ANNOTATED,
            )
        )

    for index in range(6):
        records.append(
            record(
                image_id=f"n{index}",
                category="negative",
                scene_group=f"negative-{index}",
                status=ANNOTATION_STATUS_NO_TARGET,
            )
        )

    source = manifest(records)

    split_manifest = build_split_manifest(
        source,
        "annotations.json",
        production_policy(),
    )

    scene_splits = {}

    for assignment in split_manifest.assignments:
        existing = scene_splits.get(
            assignment.scene_group
        )

        if existing is not None:
            assert existing == assignment.split

        scene_splits[
            assignment.scene_group
        ] = assignment.split


def test_split_manifest_rejects_scene_leakage():
    with pytest.raises(
        ValueError,
        match="scene_group appears in multiple splits",
    ):
        DatasetSplitManifest(
            policy_version="4.3.0",
            source_annotation_manifest="annotations.json",
            dataset_name="test",
            assignments=(
                SplitAssignment(
                    image_id="1",
                    scene_group="scene-1",
                    category="positive",
                    split=SPLIT_TRAIN,
                ),
                SplitAssignment(
                    image_id="2",
                    scene_group="scene-1",
                    category="positive",
                    split=SPLIT_TEST,
                ),
            ),
        )
