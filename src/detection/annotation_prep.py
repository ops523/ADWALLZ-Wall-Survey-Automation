from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .dataset import (
    ANNOTATION_NONE,
    ANNOTATION_POLYGON,
    CATEGORY_HARD_NEGATIVE,
    CATEGORY_NEGATIVE,
    CATEGORY_POSITIVE,
    normalize_image_id,
)


ANNOTATION_STATUS_PENDING = "pending"
ANNOTATION_STATUS_NO_TARGET = "no_target"
ANNOTATION_STATUS_IN_PROGRESS = "in_progress"
ANNOTATION_STATUS_ANNOTATED = "annotated"
ANNOTATION_STATUS_REVIEW_REQUIRED = "review_required"

VALID_ANNOTATION_STATUSES = {
    ANNOTATION_STATUS_PENDING,
    ANNOTATION_STATUS_NO_TARGET,
    ANNOTATION_STATUS_IN_PROGRESS,
    ANNOTATION_STATUS_ANNOTATED,
    ANNOTATION_STATUS_REVIEW_REQUIRED,
}

SPLIT_UNASSIGNED = "unassigned"

PREP_VERSION = "4.2B.1"
POLYGON_FORMAT_VERSION = "1.0"


@dataclass(frozen=True)
class AnnotationTask:
    annotation_id: str
    image_id: str
    relative_path: str
    category: str
    scene_group: str
    split: str
    annotation_status: str
    expected_annotation_type: str
    allowed_annotation_types: tuple[str, ...]
    annotator: str | None
    source: str
    image_width: int
    image_height: int
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.annotation_id.strip():
            raise ValueError("annotation_id is required")

        if normalize_image_id(self.image_id) != self.image_id:
            raise ValueError("image_id must already be normalized")

        if not self.relative_path.strip():
            raise ValueError("relative_path is required")

        if self.category not in {
            CATEGORY_POSITIVE,
            CATEGORY_NEGATIVE,
            CATEGORY_HARD_NEGATIVE,
        }:
            raise ValueError(f"unsupported category: {self.category!r}")

        if not self.scene_group.strip():
            raise ValueError("scene_group is required")

        if not self.split.strip():
            raise ValueError("split is required")

        if self.annotation_status not in VALID_ANNOTATION_STATUSES:
            raise ValueError(
                f"unsupported annotation status: {self.annotation_status!r}"
            )

        if self.expected_annotation_type not in {
            ANNOTATION_POLYGON,
            ANNOTATION_NONE,
        }:
            raise ValueError("unsupported expected annotation type")

        if not self.allowed_annotation_types:
            raise ValueError("allowed_annotation_types is required")

        if self.expected_annotation_type not in self.allowed_annotation_types:
            raise ValueError(
                "expected annotation type must be allowed"
            )

        if self.category == CATEGORY_POSITIVE:
            if self.expected_annotation_type != ANNOTATION_POLYGON:
                raise ValueError("positive tasks require polygon annotation")
            if self.annotation_status == ANNOTATION_STATUS_NO_TARGET:
                raise ValueError("positive tasks cannot be marked no_target")
        else:
            if self.expected_annotation_type != ANNOTATION_NONE:
                raise ValueError(
                    "negative tasks must not require positive geometry"
                )
            if self.annotation_status != ANNOTATION_STATUS_NO_TARGET:
                raise ValueError(
                    "negative tasks must be marked no_target during preparation"
                )

        if self.image_width <= 0 or self.image_height <= 0:
            raise ValueError("image dimensions must be positive")

        if not self.source.strip():
            raise ValueError("source is required")

        if self.split != SPLIT_UNASSIGNED:
            raise ValueError(
                "annotation preparation must leave dataset splits unassigned"
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "annotation_id": self.annotation_id,
            "image_id": self.image_id,
            "relative_path": self.relative_path,
            "category": self.category,
            "scene_group": self.scene_group,
            "split": self.split,
            "annotation_status": self.annotation_status,
            "expected_annotation_type": self.expected_annotation_type,
            "allowed_annotation_types": list(self.allowed_annotation_types),
            "annotator": self.annotator,
            "source": self.source,
            "image_width": self.image_width,
            "image_height": self.image_height,
            "notes": self.notes,
            "polygon": None,
        }


@dataclass(frozen=True)
class AnnotationPrepManifest:
    prep_version: str
    polygon_format_version: str
    dataset_version: str
    annotation_version: str
    name: str
    source_classification_manifest: str
    tasks: tuple[AnnotationTask, ...]
    description: str = ""

    def __post_init__(self) -> None:
        if not self.prep_version.strip():
            raise ValueError("prep_version is required")

        if not self.polygon_format_version.strip():
            raise ValueError("polygon_format_version is required")

        if not self.dataset_version.strip():
            raise ValueError("dataset_version is required")

        if not self.annotation_version.strip():
            raise ValueError("annotation_version is required")

        if not self.name.strip():
            raise ValueError("name is required")

        if not self.source_classification_manifest.strip():
            raise ValueError("source_classification_manifest is required")

        image_ids = [task.image_id for task in self.tasks]
        annotation_ids = [task.annotation_id for task in self.tasks]

        if len(image_ids) != len(set(image_ids)):
            raise ValueError("duplicate image_id detected")

        if len(annotation_ids) != len(set(annotation_ids)):
            raise ValueError("duplicate annotation_id detected")

        if any(
            task.split != SPLIT_UNASSIGNED
            for task in self.tasks
        ):
            raise ValueError(
                "all annotation-prep tasks must remain unassigned"
            )

    @property
    def image_count(self) -> int:
        return len(self.tasks)

    @property
    def positive_count(self) -> int:
        return sum(
            task.category == CATEGORY_POSITIVE
            for task in self.tasks
        )

    @property
    def negative_count(self) -> int:
        return sum(
            task.category == CATEGORY_NEGATIVE
            for task in self.tasks
        )

    @property
    def hard_negative_count(self) -> int:
        return sum(
            task.category == CATEGORY_HARD_NEGATIVE
            for task in self.tasks
        )

    @property
    def pending_polygon_count(self) -> int:
        return sum(
            task.expected_annotation_type == ANNOTATION_POLYGON
            and task.annotation_status == ANNOTATION_STATUS_PENDING
            for task in self.tasks
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "prep_version": self.prep_version,
            "polygon_format_version": self.polygon_format_version,
            "dataset_version": self.dataset_version,
            "annotation_version": self.annotation_version,
            "name": self.name,
            "source_classification_manifest": (
                self.source_classification_manifest
            ),
            "image_count": self.image_count,
            "counts": {
                "positive": self.positive_count,
                "negative": self.negative_count,
                "hard_negative": self.hard_negative_count,
                "pending_polygon": self.pending_polygon_count,
            },
            "split": SPLIT_UNASSIGNED,
            "description": self.description,
            "tasks": [
                task.as_dict()
                for task in self.tasks
            ],
        }


def stable_annotation_id(image_id: str) -> str:
    normalized = normalize_image_id(image_id)

    digest = hashlib.sha256(
        f"highrise-wall-polygon:{normalized}".encode("utf-8")
    ).hexdigest()[:16]

    return f"ann-{normalized}-{digest}"


def _classification_tasks(
    records: Iterable[dict[str, Any]],
) -> list[AnnotationTask]:
    tasks: list[AnnotationTask] = []

    for record in records:
        image_id = normalize_image_id(
            str(record["image_id"])
        )
        category = str(record["category"])

        if category == CATEGORY_POSITIVE:
            status = ANNOTATION_STATUS_PENDING
            expected_type = ANNOTATION_POLYGON
            allowed_types = (ANNOTATION_POLYGON,)
        else:
            status = ANNOTATION_STATUS_NO_TARGET
            expected_type = ANNOTATION_NONE
            allowed_types = (ANNOTATION_NONE,)

        tasks.append(
            AnnotationTask(
                annotation_id=stable_annotation_id(image_id),
                image_id=image_id,
                relative_path=str(record["relative_path"]),
                category=category,
                scene_group=str(record["scene_group"]),
                split=SPLIT_UNASSIGNED,
                annotation_status=status,
                expected_annotation_type=expected_type,
                allowed_annotation_types=allowed_types,
                annotator=None,
                source=str(record["source"]),
                image_width=int(record["width"]),
                image_height=int(record["height"]),
                notes=(
                    "Human-clean polygon required; do not copy "
                    "hand-drawn reference outline."
                    if category == CATEGORY_POSITIVE
                    else (
                        "No wall_surface target annotation is "
                        "created in preparation."
                    )
                ),
            )
        )

    return sorted(
        tasks,
        key=lambda task: task.image_id,
    )


def build_annotation_prep_manifest(
    classification_manifest: dict[str, Any],
) -> AnnotationPrepManifest:
    records = classification_manifest.get("images")

    if not isinstance(records, list):
        raise ValueError(
            "classification manifest images must be a list"
        )

    return AnnotationPrepManifest(
        prep_version=PREP_VERSION,
        polygon_format_version=POLYGON_FORMAT_VERSION,
        dataset_version=str(
            classification_manifest.get(
                "dataset_version",
                "4.2.0",
            )
        ),
        annotation_version="1.0.0",
        name="highrise_wall_reference_annotation_prep",
        source_classification_manifest=(
            "manifests/classification_manifest.json"
        ),
        tasks=tuple(
            _classification_tasks(records)
        ),
        description=(
            "Human annotation preparation for High-Rise "
            "first-floor-and-above wall_surface detection. "
            "Positive images receive stable polygon tasks. "
            "Negative and hard-negative images receive explicit "
            "no-target tasks. No polygon coordinates are generated "
            "during preparation. Dataset splits remain unassigned "
            "until annotation and scene relationships are reviewed."
        ),
    )


def validate_annotation_prep_manifest(
    manifest: AnnotationPrepManifest,
) -> list[str]:
    errors: list[str] = []

    if manifest.image_count != 25:
        errors.append(
            f"expected 25 reference images, "
            f"found {manifest.image_count}"
        )

    if manifest.positive_count != 10:
        errors.append(
            f"expected 10 positives, "
            f"found {manifest.positive_count}"
        )

    if manifest.negative_count != 12:
        errors.append(
            f"expected 12 negatives, "
            f"found {manifest.negative_count}"
        )

    if manifest.hard_negative_count != 3:
        errors.append(
            f"expected 3 hard negatives, "
            f"found {manifest.hard_negative_count}"
        )

    if manifest.pending_polygon_count != 10:
        errors.append(
            "all 10 positive images must be pending "
            "polygon annotation"
        )

    for task in manifest.tasks:
        if task.split != SPLIT_UNASSIGNED:
            errors.append(
                f"task {task.image_id} has an assigned split"
            )

        if task.as_dict()["polygon"] is not None:
            errors.append(
                f"task {task.image_id} contains "
                "a generated polygon"
            )

    return errors


def write_annotation_prep_manifest(
    manifest: AnnotationPrepManifest,
    path: str | Path,
) -> None:
    errors = validate_annotation_prep_manifest(manifest)

    if errors:
        raise ValueError(
            "invalid annotation-prep manifest: "
            + "; ".join(errors)
        )

    destination = Path(path)
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = destination.with_suffix(
        destination.suffix + ".tmp"
    )

    with temporary.open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(
            manifest.as_dict(),
            handle,
            indent=2,
            sort_keys=True,
        )
        handle.write("\n")

    temporary.replace(destination)
