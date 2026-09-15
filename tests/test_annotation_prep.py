from __future__ import annotations

from src.detection.annotation_prep import (
    ANNOTATION_STATUS_NO_TARGET,
    ANNOTATION_STATUS_PENDING,
    PREP_VERSION,
    SPLIT_UNASSIGNED,
    build_annotation_prep_manifest,
    stable_annotation_id,
    validate_annotation_prep_manifest,
)


def make_record(
    image_id: str,
    category: str,
) -> dict[str, object]:
    return {
        "image_id": image_id,
        "relative_path": f"images/{category}/{image_id}.jpeg",
        "category": category,
        "scene_group": f"scene-{image_id}",
        "width": 1600,
        "height": 1200,
        "source": "highrise_wall_reference_v1",
    }


def make_full_manifest() -> dict[str, object]:
    records = []

    for image_id in (
        "1", "2", "3", "4", "5",
        "9", "10", "11", "19", "23",
    ):
        records.append(
            make_record(image_id, "positive")
        )

    for image_id in ("6", "12", "14"):
        records.append(
            make_record(image_id, "hard_negative")
        )

    for image_id in (
        "7", "8", "10a", "13", "15", "16",
        "17", "18", "20", "21", "22", "24",
    ):
        records.append(
            make_record(image_id, "negative")
        )

    return {
        "dataset_version": "4.2.0",
        "images": records,
    }


def test_stable_annotation_id_is_deterministic() -> None:
    first = stable_annotation_id("10a")
    second = stable_annotation_id("10a")

    assert first == second
    assert first.startswith("ann-10a-")


def test_builds_exact_25_annotation_tasks() -> None:
    manifest = build_annotation_prep_manifest(
        make_full_manifest()
    )

    assert manifest.prep_version == PREP_VERSION
    assert manifest.image_count == 25
    assert manifest.positive_count == 10
    assert manifest.negative_count == 12
    assert manifest.hard_negative_count == 3


def test_positive_images_are_pending_polygon_tasks() -> None:
    manifest = build_annotation_prep_manifest(
        make_full_manifest()
    )

    positive = [
        task
        for task in manifest.tasks
        if task.category == "positive"
    ]

    assert len(positive) == 10

    for task in positive:
        assert task.annotation_status == (
            ANNOTATION_STATUS_PENDING
        )
        assert task.expected_annotation_type == "polygon"
        assert task.split == SPLIT_UNASSIGNED


def test_negative_images_have_no_target_tasks() -> None:
    manifest = build_annotation_prep_manifest(
        make_full_manifest()
    )

    non_positive = [
        task
        for task in manifest.tasks
        if task.category != "positive"
    ]

    assert len(non_positive) == 15

    for task in non_positive:
        assert task.annotation_status == (
            ANNOTATION_STATUS_NO_TARGET
        )
        assert task.expected_annotation_type == "none"
        assert task.split == SPLIT_UNASSIGNED


def test_no_polygons_are_generated() -> None:
    manifest = build_annotation_prep_manifest(
        make_full_manifest()
    )

    for task in manifest.tasks:
        assert task.as_dict()["polygon"] is None


def test_all_splits_remain_unassigned() -> None:
    manifest = build_annotation_prep_manifest(
        make_full_manifest()
    )

    assert all(
        task.split == SPLIT_UNASSIGNED
        for task in manifest.tasks
    )


def test_manifest_validation_passes() -> None:
    manifest = build_annotation_prep_manifest(
        make_full_manifest()
    )

    assert validate_annotation_prep_manifest(
        manifest
    ) == []


def test_source_provenance_is_preserved() -> None:
    manifest = build_annotation_prep_manifest(
        make_full_manifest()
    )

    assert all(
        task.source == "highrise_wall_reference_v1"
        for task in manifest.tasks
    )
