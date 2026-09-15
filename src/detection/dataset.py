from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DATASET_VERSION = "4.2.0"
ANNOTATION_VERSION = "1.0.0"

WALL_SURFACE_CLASS = "wall_surface"

CATEGORY_POSITIVE = "positive"
CATEGORY_NEGATIVE = "negative"
CATEGORY_HARD_NEGATIVE = "hard_negative"

VALID_CATEGORIES = {
    CATEGORY_POSITIVE,
    CATEGORY_NEGATIVE,
    CATEGORY_HARD_NEGATIVE,
}

SPLIT_TRAIN = "train"
SPLIT_VALIDATION = "validation"
SPLIT_TEST = "test"

VALID_SPLITS = {
    SPLIT_TRAIN,
    SPLIT_VALIDATION,
    SPLIT_TEST,
}

ANNOTATION_POLYGON = "polygon"
ANNOTATION_BBOX = "bbox"
ANNOTATION_NONE = "none"

VALID_ANNOTATION_TYPES = {
    ANNOTATION_POLYGON,
    ANNOTATION_BBOX,
    ANNOTATION_NONE,
}


def normalize_image_id(value: str) -> str:
    """
    Convert an arbitrary image identifier into a deterministic filesystem-
    friendly identifier.
    """
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9._-]+", "_", normalized)
    normalized = normalized.strip("._-")

    if not normalized:
        raise ValueError("image_id must contain at least one valid character")

    return normalized


def calculate_sha256(path: str | Path) -> str:
    file_path = Path(path)

    if not file_path.is_file():
        raise FileNotFoundError(str(file_path))

    digest = hashlib.sha256()

    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


@dataclass(frozen=True)
class PolygonPoint:
    x: float
    y: float

    def __post_init__(self) -> None:
        if not isinstance(self.x, (int, float)):
            raise ValueError("polygon x must be numeric")

        if not isinstance(self.y, (int, float)):
            raise ValueError("polygon y must be numeric")

        if not (-1e-9 <= self.x <= 1.0 + 1e-9):
            raise ValueError("polygon x must be normalized to [0, 1]")

        if not (-1e-9 <= self.y <= 1.0 + 1e-9):
            raise ValueError("polygon y must be normalized to [0, 1]")

    def as_dict(self) -> dict[str, float]:
        return {
            "x": float(self.x),
            "y": float(self.y),
        }


@dataclass(frozen=True)
class WallSurfaceAnnotation:
    annotation_id: str
    class_name: str
    annotation_type: str
    polygon: tuple[PolygonPoint, ...]
    annotator: str
    source: str
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.annotation_id.strip():
            raise ValueError("annotation_id is required")

        if self.class_name != WALL_SURFACE_CLASS:
            raise ValueError(
                f"unsupported annotation class: {self.class_name!r}"
            )

        if self.annotation_type != ANNOTATION_POLYGON:
            raise ValueError(
                "wall surface annotations must currently use polygons"
            )

        if len(self.polygon) < 3:
            raise ValueError("polygon must contain at least three points")

        if not self.annotator.strip():
            raise ValueError("annotator is required")

        if not self.source.strip():
            raise ValueError("annotation source is required")

    def as_dict(self) -> dict[str, Any]:
        return {
            "annotation_id": self.annotation_id,
            "class_name": self.class_name,
            "annotation_type": self.annotation_type,
            "polygon": [point.as_dict() for point in self.polygon],
            "annotator": self.annotator,
            "source": self.source,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ReferenceImageRecord:
    image_id: str
    relative_path: str
    category: str
    split: str
    width: int
    height: int
    sha256: str
    source: str
    scene_group: str
    annotations: tuple[WallSurfaceAnnotation, ...] = ()
    notes: str = ""

    def __post_init__(self) -> None:
        normalized_id = normalize_image_id(self.image_id)

        if normalized_id != self.image_id:
            raise ValueError(
                "image_id must already be normalized"
            )

        if not self.relative_path.strip():
            raise ValueError("relative_path is required")

        if self.category not in VALID_CATEGORIES:
            raise ValueError(
                f"unsupported category: {self.category!r}"
            )

        if self.split not in VALID_SPLITS:
            raise ValueError(
                f"unsupported split: {self.split!r}"
            )

        if self.width <= 0:
            raise ValueError("width must be greater than zero")

        if self.height <= 0:
            raise ValueError("height must be greater than zero")

        if len(self.sha256) != 64:
            raise ValueError("sha256 must be a 64-character hexadecimal digest")

        if any(char not in "0123456789abcdef" for char in self.sha256.lower()):
            raise ValueError("sha256 must contain hexadecimal characters only")

        if not self.source.strip():
            raise ValueError("source is required")

        if not self.scene_group.strip():
            raise ValueError("scene_group is required")

        if self.category == CATEGORY_POSITIVE and not self.annotations:
            raise ValueError(
                "positive reference images require wall surface annotations"
            )

        if self.category != CATEGORY_POSITIVE and self.annotations:
            raise ValueError(
                "negative references must not contain wall surface annotations"
            )

    @property
    def annotation_count(self) -> int:
        return len(self.annotations)

    def as_dict(self) -> dict[str, Any]:
        return {
            "image_id": self.image_id,
            "relative_path": self.relative_path,
            "category": self.category,
            "split": self.split,
            "width": self.width,
            "height": self.height,
            "sha256": self.sha256,
            "source": self.source,
            "scene_group": self.scene_group,
            "annotations": [
                annotation.as_dict()
                for annotation in self.annotations
            ],
            "notes": self.notes,
        }


@dataclass(frozen=True)
class DatasetManifest:
    dataset_version: str
    annotation_version: str
    name: str
    images: tuple[ReferenceImageRecord, ...]
    description: str = ""

    def __post_init__(self) -> None:
        if not self.dataset_version.strip():
            raise ValueError("dataset_version is required")

        if not self.annotation_version.strip():
            raise ValueError("annotation_version is required")

        if not self.name.strip():
            raise ValueError("dataset name is required")

        image_ids = [image.image_id for image in self.images]

        if len(image_ids) != len(set(image_ids)):
            raise ValueError("duplicate image_id detected")

        scene_groups_by_split: dict[str, set[str]] = {}

        for image in self.images:
            scene_groups_by_split.setdefault(image.split, set()).add(
                image.scene_group
            )

        # The same physical scene must never appear in multiple splits.
        all_seen_groups: dict[str, str] = {}

        for image in self.images:
            existing_split = all_seen_groups.get(image.scene_group)

            if existing_split is not None and existing_split != image.split:
                raise ValueError(
                    "scene_group appears in multiple dataset splits: "
                    f"{image.scene_group}"
                )

            all_seen_groups[image.scene_group] = image.split

    @property
    def image_count(self) -> int:
        return len(self.images)

    @property
    def annotation_count(self) -> int:
        return sum(image.annotation_count for image in self.images)

    def split_counts(self) -> dict[str, int]:
        return {
            split: sum(
                image.split == split
                for image in self.images
            )
            for split in sorted(VALID_SPLITS)
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "dataset_version": self.dataset_version,
            "annotation_version": self.annotation_version,
            "name": self.name,
            "description": self.description,
            "image_count": self.image_count,
            "annotation_count": self.annotation_count,
            "split_counts": self.split_counts(),
            "images": [
                image.as_dict()
                for image in self.images
            ],
        }


def write_manifest(
    manifest: DatasetManifest,
    path: str | Path,
) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    temporary = destination.with_suffix(
        destination.suffix + ".tmp"
    )

    payload = manifest.as_dict()

    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(
            payload,
            handle,
            indent=2,
            sort_keys=True,
        )
        handle.write("\n")

    temporary.replace(destination)
