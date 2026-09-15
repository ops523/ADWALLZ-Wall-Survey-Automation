from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .annotation_prep import (
    ANNOTATION_STATUS_ANNOTATED,
    ANNOTATION_STATUS_IN_PROGRESS,
    ANNOTATION_STATUS_NO_TARGET,
    ANNOTATION_STATUS_PENDING,
    ANNOTATION_STATUS_REVIEW_REQUIRED,
    SPLIT_UNASSIGNED,
)
from .dataset import PolygonPoint


ANNOTATION_TOOL_VERSION = "4.2C.1"
POLYGON_FORMAT_VERSION = "1.0"
WALL_SURFACE_CLASS = "wall_surface"

ANNOTATION_STATUS_APPROVED = "approved"

VALID_ANNOTATION_STATUSES = {
    ANNOTATION_STATUS_PENDING,
    ANNOTATION_STATUS_IN_PROGRESS,
    ANNOTATION_STATUS_ANNOTATED,
    ANNOTATION_STATUS_REVIEW_REQUIRED,
    ANNOTATION_STATUS_APPROVED,
    ANNOTATION_STATUS_NO_TARGET,
}

VALID_SPLITS = {SPLIT_UNASSIGNED}

POSITIVE_CATEGORIES = {"positive"}
NON_POSITIVE_CATEGORIES = {"negative", "hard_negative"}


@dataclass(frozen=True)
class HumanPolygonAnnotation:
    annotation_id: str
    class_name: str
    polygon: tuple[PolygonPoint, ...]
    annotator: str
    source: str = "human_reference"
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.annotation_id.strip():
            raise ValueError("annotation_id is required")

        if self.class_name != WALL_SURFACE_CLASS:
            raise ValueError(
                f"class_name must be {WALL_SURFACE_CLASS!r}"
            )

        if len(self.polygon) < 3:
            raise ValueError("polygon requires at least 3 points")

        if not self.annotator.strip():
            raise ValueError("annotator is required")

        if not self.source.strip():
            raise ValueError("source is required")

    def as_dict(self) -> dict[str, Any]:
        return {
            "annotation_id": self.annotation_id,
            "class_name": self.class_name,
            "annotation_type": "polygon",
            "polygon": [
                {"x": point.x, "y": point.y}
                for point in self.polygon
            ],
            "annotator": self.annotator,
            "source": self.source,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HumanPolygonAnnotation":
        polygon = tuple(
            PolygonPoint(
                x=float(point["x"]),
                y=float(point["y"]),
            )
            for point in data["polygon"]
        )

        return cls(
            annotation_id=str(data["annotation_id"]),
            class_name=str(data.get("class_name", WALL_SURFACE_CLASS)),
            polygon=polygon,
            annotator=str(data["annotator"]),
            source=str(data.get("source", "human_reference")),
            notes=str(data.get("notes", "")),
        )


@dataclass
class HumanAnnotationRecord:
    image_id: str
    relative_path: str
    category: str
    scene_group: str
    image_width: int
    image_height: int
    status: str
    annotator: str | None
    annotations: list[HumanPolygonAnnotation] = field(default_factory=list)
    split: str = SPLIT_UNASSIGNED
    source: str = "highrise_wall_reference_v1"
    updated_at: str | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.image_id.strip():
            raise ValueError("image_id is required")

        if self.category not in POSITIVE_CATEGORIES | NON_POSITIVE_CATEGORIES:
            raise ValueError(f"Unsupported category: {self.category}")

        if self.status not in VALID_ANNOTATION_STATUSES:
            raise ValueError(f"Unsupported annotation status: {self.status}")

        if self.split not in VALID_SPLITS:
            raise ValueError(f"Unsupported split: {self.split}")

        if self.image_width <= 0 or self.image_height <= 0:
            raise ValueError("image dimensions must be positive")

        if self.category in NON_POSITIVE_CATEGORIES and self.annotations:
            raise ValueError(
                "negative and hard-negative records cannot contain polygons"
            )

        if self.category == "positive" and self.status == ANNOTATION_STATUS_NO_TARGET:
            raise ValueError("positive record cannot have no_target status")

        if (
            self.category in NON_POSITIVE_CATEGORIES
            and self.status != ANNOTATION_STATUS_NO_TARGET
        ):
            raise ValueError(
                "negative and hard-negative records must use no_target status"
            )

        if self.status in {
            ANNOTATION_STATUS_ANNOTATED,
            ANNOTATION_STATUS_REVIEW_REQUIRED,
            ANNOTATION_STATUS_APPROVED,
        } and not self.annotations:
            raise ValueError(
                "annotated/review/approved records require polygons"
            )

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def as_dict(self) -> dict[str, Any]:
        return {
            "image_id": self.image_id,
            "relative_path": self.relative_path,
            "category": self.category,
            "scene_group": self.scene_group,
            "image_width": self.image_width,
            "image_height": self.image_height,
            "status": self.status,
            "annotator": self.annotator,
            "annotations": [
                annotation.as_dict()
                for annotation in self.annotations
            ],
            "split": self.split,
            "source": self.source,
            "updated_at": self.updated_at,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HumanAnnotationRecord":
        return cls(
            image_id=str(data["image_id"]),
            relative_path=str(data["relative_path"]),
            category=str(data["category"]),
            scene_group=str(data.get("scene_group", "")),
            image_width=int(data["image_width"]),
            image_height=int(data["image_height"]),
            status=str(data["status"]),
            annotator=data.get("annotator"),
            annotations=[
                HumanPolygonAnnotation.from_dict(item)
                for item in data.get("annotations", [])
            ],
            split=str(data.get("split", SPLIT_UNASSIGNED)),
            source=str(
                data.get("source", "highrise_wall_reference_v1")
            ),
            updated_at=data.get("updated_at"),
            notes=str(data.get("notes", "")),
        )


@dataclass
class HumanAnnotationManifest:
    annotation_tool_version: str
    polygon_format_version: str
    dataset_version: str
    annotation_version: str
    name: str
    source_prep_manifest: str
    split: str
    images: list[HumanAnnotationRecord]
    description: str = ""

    def __post_init__(self) -> None:
        if self.split != SPLIT_UNASSIGNED:
            raise ValueError("dataset split must remain unassigned")

        if self.annotation_tool_version != ANNOTATION_TOOL_VERSION:
            raise ValueError(
                f"unsupported annotation tool version: "
                f"{self.annotation_tool_version}"
            )

        image_ids = [record.image_id for record in self.images]
        if len(image_ids) != len(set(image_ids)):
            raise ValueError("duplicate image_id detected")

        for record in self.images:
            if record.split != SPLIT_UNASSIGNED:
                raise ValueError("all annotation splits must remain unassigned")

    @property
    def image_count(self) -> int:
        return len(self.images)

    def counts(self) -> dict[str, int]:
        result: dict[str, int] = {}

        for record in self.images:
            result[record.status] = result.get(record.status, 0) + 1

        return result

    def as_dict(self) -> dict[str, Any]:
        return {
            "annotation_tool_version": self.annotation_tool_version,
            "polygon_format_version": self.polygon_format_version,
            "dataset_version": self.dataset_version,
            "annotation_version": self.annotation_version,
            "name": self.name,
            "source_prep_manifest": self.source_prep_manifest,
            "split": self.split,
            "image_count": self.image_count,
            "counts": self.counts(),
            "description": self.description,
            "images": [
                record.as_dict()
                for record in self.images
            ],
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "HumanAnnotationManifest":
        return cls(
            annotation_tool_version=str(
                data["annotation_tool_version"]
            ),
            polygon_format_version=str(
                data["polygon_format_version"]
            ),
            dataset_version=str(data["dataset_version"]),
            annotation_version=str(data["annotation_version"]),
            name=str(data["name"]),
            source_prep_manifest=str(data["source_prep_manifest"]),
            split=str(data.get("split", SPLIT_UNASSIGNED)),
            images=[
                HumanAnnotationRecord.from_dict(item)
                for item in data.get("images", [])
            ],
            description=str(data.get("description", "")),
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_annotation_manifest_from_prep(
    prep_manifest_path: Path,
) -> HumanAnnotationManifest:
    data = json.loads(
        prep_manifest_path.read_text(encoding="utf-8")
    )

    images: list[HumanAnnotationRecord] = []

    for task in data["tasks"]:
        category = task["category"]

        if category in NON_POSITIVE_CATEGORIES:
            status = ANNOTATION_STATUS_NO_TARGET
        else:
            status = ANNOTATION_STATUS_PENDING

        images.append(
            HumanAnnotationRecord(
                image_id=str(task["image_id"]),
                relative_path=str(task["relative_path"]),
                category=category,
                scene_group=str(task["scene_group"]),
                image_width=int(task["image_width"]),
                image_height=int(task["image_height"]),
                status=status,
                annotator=None,
                annotations=[],
                split=SPLIT_UNASSIGNED,
                source=str(task.get("source", "highrise_wall_reference_v1")),
                updated_at=None,
                notes=str(task.get("notes", "")),
            )
        )

    return HumanAnnotationManifest(
        annotation_tool_version=ANNOTATION_TOOL_VERSION,
        polygon_format_version=POLYGON_FORMAT_VERSION,
        dataset_version=str(data["dataset_version"]),
        annotation_version=str(data["annotation_version"]),
        name="highrise_wall_reference_annotations",
        source_prep_manifest=(
            "manifests/annotation_prep_manifest.json"
        ),
        split=SPLIT_UNASSIGNED,
        images=images,
        description=(
            "Human polygon annotations for High-Rise first-floor-and-above "
            "wall_surface detection. Positive images require clean human "
            "polygons. Negative and hard-negative images are explicit "
            "no-target records. No polygons are generated automatically. "
            "Dataset splits remain unassigned until annotation and scene "
            "relationships are reviewed."
        ),
    )


def load_annotation_manifest(
    path: Path,
) -> HumanAnnotationManifest:
    data = json.loads(path.read_text(encoding="utf-8"))
    return HumanAnnotationManifest.from_dict(data)


def write_annotation_manifest(
    manifest: HumanAnnotationManifest,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(
        manifest.as_dict(),
        indent=2,
        ensure_ascii=False,
    ) + "\n"

    temporary = path.with_suffix(path.suffix + ".tmp")

    temporary.write_text(
        payload,
        encoding="utf-8",
    )

    os.replace(temporary, path)


def get_record(
    manifest: HumanAnnotationManifest,
    image_id: str,
) -> HumanAnnotationRecord:
    for record in manifest.images:
        if record.image_id == image_id:
            return record

    raise KeyError(f"Unknown image_id: {image_id}")


def upsert_record(
    manifest: HumanAnnotationManifest,
    record: HumanAnnotationRecord,
) -> None:
    for index, existing in enumerate(manifest.images):
        if existing.image_id == record.image_id:
            manifest.images[index] = record
            return

    raise KeyError(
        f"Cannot insert unknown preparation image_id: {record.image_id}"
    )


def annotation_counts(
    manifest: HumanAnnotationManifest,
) -> dict[str, int]:
    return manifest.counts()
