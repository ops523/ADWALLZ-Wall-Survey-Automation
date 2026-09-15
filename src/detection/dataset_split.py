from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .annotation import (
    ANNOTATION_STATUS_ANNOTATED,
    ANNOTATION_STATUS_NO_TARGET,
    HumanAnnotationManifest,
    HumanAnnotationRecord,
)


SPLIT_POLICY_VERSION = "4.3.0"

SPLIT_TRAIN = "train"
SPLIT_VALIDATION = "validation"
SPLIT_TEST = "test"

SPLITS = (
    SPLIT_TRAIN,
    SPLIT_VALIDATION,
    SPLIT_TEST,
)

DEFAULT_TRAIN_RATIO = 0.70
DEFAULT_VALIDATION_RATIO = 0.15
DEFAULT_TEST_RATIO = 0.15

# This is deliberately conservative. The current 10 positive scenes
# must remain a reference/seed dataset rather than a production dataset.
MIN_PRODUCTION_POSITIVE_IMAGES = 100
MIN_PRODUCTION_NON_POSITIVE_IMAGES = 100


@dataclass(frozen=True)
class DatasetSplitPolicy:
    version: str = SPLIT_POLICY_VERSION
    train_ratio: float = DEFAULT_TRAIN_RATIO
    validation_ratio: float = DEFAULT_VALIDATION_RATIO
    test_ratio: float = DEFAULT_TEST_RATIO
    min_positive_images: int = MIN_PRODUCTION_POSITIVE_IMAGES
    min_non_positive_images: int = MIN_PRODUCTION_NON_POSITIVE_IMAGES

    def __post_init__(self) -> None:
        ratios = (
            self.train_ratio,
            self.validation_ratio,
            self.test_ratio,
        )

        if any(ratio <= 0 for ratio in ratios):
            raise ValueError("split ratios must be greater than zero")

        if abs(sum(ratios) - 1.0) > 1e-9:
            raise ValueError("split ratios must sum to 1.0")

        if self.min_positive_images <= 0:
            raise ValueError(
                "min_positive_images must be greater than zero"
            )

        if self.min_non_positive_images <= 0:
            raise ValueError(
                "min_non_positive_images must be greater than zero"
            )


@dataclass(frozen=True)
class DatasetReadinessReport:
    ready: bool
    image_count: int
    positive_count: int
    negative_count: int
    hard_negative_count: int
    annotated_positive_count: int
    no_target_count: int
    scene_group_count: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "ready": self.ready,
            "image_count": self.image_count,
            "positive_count": self.positive_count,
            "negative_count": self.negative_count,
            "hard_negative_count": self.hard_negative_count,
            "annotated_positive_count": self.annotated_positive_count,
            "no_target_count": self.no_target_count,
            "scene_group_count": self.scene_group_count,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class SplitAssignment:
    image_id: str
    scene_group: str
    category: str
    split: str

    def as_dict(self) -> dict[str, str]:
        return {
            "image_id": self.image_id,
            "scene_group": self.scene_group,
            "category": self.category,
            "split": self.split,
        }


@dataclass(frozen=True)
class DatasetSplitManifest:
    policy_version: str
    source_annotation_manifest: str
    dataset_name: str
    assignments: tuple[SplitAssignment, ...]
    description: str = ""

    def __post_init__(self) -> None:
        image_ids = [
            assignment.image_id
            for assignment in self.assignments
        ]

        if len(image_ids) != len(set(image_ids)):
            raise ValueError("duplicate image_id in split assignments")

        scene_to_split: dict[str, str] = {}

        for assignment in self.assignments:
            if assignment.split not in SPLITS:
                raise ValueError(
                    f"unsupported split: {assignment.split}"
                )

            existing = scene_to_split.get(assignment.scene_group)

            if existing is not None and existing != assignment.split:
                raise ValueError(
                    "scene_group appears in multiple splits: "
                    f"{assignment.scene_group}"
                )

            scene_to_split[assignment.scene_group] = assignment.split

    @property
    def image_count(self) -> int:
        return len(self.assignments)

    def split_counts(self) -> dict[str, int]:
        return {
            split: sum(
                assignment.split == split
                for assignment in self.assignments
            )
            for split in SPLITS
        }

    def category_counts(self) -> dict[str, int]:
        result: dict[str, int] = {}

        for assignment in self.assignments:
            key = f"{assignment.split}:{assignment.category}"
            result[key] = result.get(key, 0) + 1

        return result

    def as_dict(self) -> dict[str, object]:
        return {
            "policy_version": self.policy_version,
            "source_annotation_manifest": self.source_annotation_manifest,
            "dataset_name": self.dataset_name,
            "image_count": self.image_count,
            "split_counts": self.split_counts(),
            "category_counts": self.category_counts(),
            "description": self.description,
            "assignments": [
                assignment.as_dict()
                for assignment in self.assignments
            ],
        }


def assess_dataset_readiness(
    manifest: HumanAnnotationManifest,
    policy: DatasetSplitPolicy | None = None,
) -> DatasetReadinessReport:
    policy = policy or DatasetSplitPolicy()

    errors: list[str] = []
    warnings: list[str] = []

    positive_count = sum(
        record.category == "positive"
        for record in manifest.images
    )

    negative_count = sum(
        record.category == "negative"
        for record in manifest.images
    )

    hard_negative_count = sum(
        record.category == "hard_negative"
        for record in manifest.images
    )

    annotated_positive_count = sum(
        record.category == "positive"
        and record.status == ANNOTATION_STATUS_ANNOTATED
        for record in manifest.images
    )

    no_target_count = sum(
        record.status == ANNOTATION_STATUS_NO_TARGET
        for record in manifest.images
    )

    scene_groups = {
        record.scene_group
        for record in manifest.images
    }

    pending_positive = [
        record.image_id
        for record in manifest.images
        if (
            record.category == "positive"
            and record.status != ANNOTATION_STATUS_ANNOTATED
        )
    ]

    if pending_positive:
        errors.append(
            "positive annotations are incomplete: "
            + ", ".join(sorted(pending_positive))
        )

    if manifest.split != "unassigned":
        errors.append(
            "human annotation manifest must remain unassigned"
        )

    for record in manifest.images:
        if record.split != "unassigned":
            errors.append(
                f"image {record.image_id} has assigned split"
            )

    non_positive_count = negative_count + hard_negative_count

    if positive_count < policy.min_positive_images:
        warnings.append(
            "positive image count is below production minimum: "
            f"{positive_count}/{policy.min_positive_images}"
        )

    if non_positive_count < policy.min_non_positive_images:
        warnings.append(
            "negative/hard-negative image count is below "
            "production minimum: "
            f"{non_positive_count}/{policy.min_non_positive_images}"
        )

    if len(scene_groups) < 3:
        warnings.append(
            "dataset has fewer than three scene groups"
        )

    ready = (
        not errors
        and positive_count >= policy.min_positive_images
        and non_positive_count >= policy.min_non_positive_images
        and annotated_positive_count == positive_count
        and no_target_count == non_positive_count
    )

    return DatasetReadinessReport(
        ready=ready,
        image_count=len(manifest.images),
        positive_count=positive_count,
        negative_count=negative_count,
        hard_negative_count=hard_negative_count,
        annotated_positive_count=annotated_positive_count,
        no_target_count=no_target_count,
        scene_group_count=len(scene_groups),
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def _stable_scene_key(scene_group: str) -> str:
    return hashlib.sha256(
        scene_group.encode("utf-8")
    ).hexdigest()


def _target_counts(
    total: int,
    policy: DatasetSplitPolicy,
) -> dict[str, int]:
    raw = {
        SPLIT_TRAIN: total * policy.train_ratio,
        SPLIT_VALIDATION: total * policy.validation_ratio,
        SPLIT_TEST: total * policy.test_ratio,
    }

    counts = {
        split: int(raw[split])
        for split in SPLITS
    }

    remainder = total - sum(counts.values())

    ordered = sorted(
        SPLITS,
        key=lambda split: (
            -(raw[split] - counts[split]),
            split,
        ),
    )

    for split in ordered[:remainder]:
        counts[split] += 1

    return counts


def _assign_scene_groups(
    records: list[HumanAnnotationRecord],
    policy: DatasetSplitPolicy,
) -> dict[str, str]:
    scene_groups: dict[str, list[HumanAnnotationRecord]] = {}

    for record in records:
        scene_groups.setdefault(
            record.scene_group,
            [],
        ).append(record)

    ordered_groups = sorted(
        scene_groups.items(),
        key=lambda item: _stable_scene_key(item[0]),
    )

    target_counts = _target_counts(
        len(records),
        policy,
    )

    assignments: dict[str, str] = {}
    split_counts = {
        split: 0
        for split in SPLITS
    }

    for scene_group, group_records in ordered_groups:
        group_size = len(group_records)

        candidates = sorted(
            SPLITS,
            key=lambda split: (
                split_counts[split] >= target_counts[split],
                split_counts[split],
                split,
            ),
        )

        selected = candidates[0]

        assignments[scene_group] = selected
        split_counts[selected] += group_size

    return assignments


def build_split_manifest(
    manifest: HumanAnnotationManifest,
    source_annotation_manifest: str,
    policy: DatasetSplitPolicy | None = None,
) -> DatasetSplitManifest:
    policy = policy or DatasetSplitPolicy()

    readiness = assess_dataset_readiness(
        manifest,
        policy,
    )

    if not readiness.ready:
        raise ValueError(
            "dataset is not production-ready for splitting"
        )

    scene_assignments = _assign_scene_groups(
        manifest.images,
        policy,
    )

    assignments = tuple(
        SplitAssignment(
            image_id=record.image_id,
            scene_group=record.scene_group,
            category=record.category,
            split=scene_assignments[record.scene_group],
        )
        for record in sorted(
            manifest.images,
            key=lambda record: record.image_id,
        )
    )

    return DatasetSplitManifest(
        policy_version=policy.version,
        source_annotation_manifest=source_annotation_manifest,
        dataset_name="highrise_wall_production_split",
        assignments=assignments,
        description=(
            "Deterministic scene-group-aware dataset split. "
            "The same physical scene must never occur in more than "
            "one split. Human annotation manifests remain immutable "
            "and unassigned; this manifest records only split "
            "assignments after production-readiness approval."
        ),
    )


def write_split_manifest(
    manifest: DatasetSplitManifest,
    path: str | Path,
) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(
        manifest.as_dict(),
        indent=2,
        sort_keys=True,
    ) + "\n"

    temporary = destination.with_suffix(
        destination.suffix + ".tmp"
    )

    temporary.write_text(
        payload,
        encoding="utf-8",
    )

    os.replace(
        temporary,
        destination,
    )


def load_split_manifest(
    path: str | Path,
) -> DatasetSplitManifest:
    data = json.loads(
        Path(path).read_text(encoding="utf-8")
    )

    assignments = tuple(
        SplitAssignment(
            image_id=str(item["image_id"]),
            scene_group=str(item["scene_group"]),
            category=str(item["category"]),
            split=str(item["split"]),
        )
        for item in data.get("assignments", [])
    )

    return DatasetSplitManifest(
        policy_version=str(data["policy_version"]),
        source_annotation_manifest=str(
            data["source_annotation_manifest"]
        ),
        dataset_name=str(data["dataset_name"]),
        assignments=assignments,
        description=str(data.get("description", "")),
    )
