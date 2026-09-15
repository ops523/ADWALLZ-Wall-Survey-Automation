from __future__ import annotations

import math
from dataclasses import dataclass, field

from shapely.geometry import Polygon

from .annotation import (
    ANNOTATION_STATUS_ANNOTATED,
    ANNOTATION_STATUS_APPROVED,
    ANNOTATION_STATUS_IN_PROGRESS,
    ANNOTATION_STATUS_NO_TARGET,
    ANNOTATION_STATUS_PENDING,
    ANNOTATION_STATUS_REVIEW_REQUIRED,
    HumanAnnotationManifest,
    HumanAnnotationRecord,
)
from .dataset import PolygonPoint


DEFAULT_MIN_POLYGON_AREA = 0.0005


@dataclass(frozen=True)
class PolygonValidationResult:
    valid: bool
    errors: tuple[str, ...] = ()

    @property
    def error_count(self) -> int:
        return len(self.errors)


@dataclass
class AnnotationRecordValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class AnnotationManifestValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _finite(value: float) -> bool:
    return math.isfinite(float(value))


def polygon_area(points: tuple[PolygonPoint, ...]) -> float:
    if len(points) < 3:
        return 0.0

    coordinates = [(point.x, point.y) for point in points]

    return abs(
        sum(
            coordinates[index][0]
            * coordinates[(index + 1) % len(coordinates)][1]
            - coordinates[(index + 1) % len(coordinates)][0]
            * coordinates[index][1]
            for index in range(len(coordinates))
        )
    ) / 2.0


def validate_polygon(
    points: tuple[PolygonPoint, ...],
    *,
    min_area: float = DEFAULT_MIN_POLYGON_AREA,
) -> PolygonValidationResult:
    errors: list[str] = []

    if len(points) < 3:
        errors.append("polygon requires at least 3 points")
        return PolygonValidationResult(False, tuple(errors))

    for index, point in enumerate(points):
        if not _finite(point.x) or not _finite(point.y):
            errors.append(
                f"point {index} contains a non-finite coordinate"
            )
            continue

        if not 0.0 <= point.x <= 1.0:
            errors.append(
                f"point {index} x coordinate is outside [0, 1]"
            )

        if not 0.0 <= point.y <= 1.0:
            errors.append(
                f"point {index} y coordinate is outside [0, 1]"
            )

    for index in range(len(points) - 1):
        if (
            points[index].x == points[index + 1].x
            and points[index].y == points[index + 1].y
        ):
            errors.append(
                f"duplicate consecutive point at index {index}"
            )

    if (
        points[0].x == points[-1].x
        and points[0].y == points[-1].y
    ):
        errors.append(
            "polygon must not repeat the first point at the end"
        )

    coordinates = [(point.x, point.y) for point in points]

    polygon = Polygon(coordinates)

    if not polygon.is_valid:
        errors.append(
            "polygon geometry is invalid or self-intersecting"
        )

    area = polygon_area(points)

    if area < min_area:
        errors.append(
            f"polygon area {area:.8f} is below minimum {min_area:.8f}"
        )

    return PolygonValidationResult(
        valid=not errors,
        errors=tuple(errors),
    )


def validate_annotation_record(
    record: HumanAnnotationRecord,
    *,
    min_area: float = DEFAULT_MIN_POLYGON_AREA,
) -> AnnotationRecordValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    annotation_ids: set[str] = set()

    if record.split != "unassigned":
        errors.append("dataset split must remain unassigned")

    if record.category in {"negative", "hard_negative"}:
        if record.status != ANNOTATION_STATUS_NO_TARGET:
            errors.append(
                "negative and hard-negative records must be no_target"
            )

        if record.annotations:
            errors.append(
                "negative and hard-negative records cannot contain polygons"
            )

        return AnnotationRecordValidationResult(
            valid=not errors,
            errors=errors,
            warnings=warnings,
        )

    if record.category != "positive":
        errors.append(
            f"unsupported category: {record.category}"
        )

    if record.status == ANNOTATION_STATUS_NO_TARGET:
        errors.append(
            "positive record cannot be marked no_target"
        )

    if record.status in {
        ANNOTATION_STATUS_ANNOTATED,
        ANNOTATION_STATUS_REVIEW_REQUIRED,
        ANNOTATION_STATUS_APPROVED,
    } and not record.annotations:
        errors.append(
            "completed annotation status requires at least one polygon"
        )

    if record.status in {
        ANNOTATION_STATUS_PENDING,
        ANNOTATION_STATUS_IN_PROGRESS,
    } and not record.annotations:
        warnings.append("positive image still has no polygon")

    for annotation in record.annotations:
        if annotation.annotation_id in annotation_ids:
            errors.append(
                f"duplicate annotation_id: {annotation.annotation_id}"
            )

        annotation_ids.add(annotation.annotation_id)

        result = validate_polygon(
            annotation.polygon,
            min_area=min_area,
        )

        if not result.valid:
            errors.extend(
                f"{annotation.annotation_id}: {error}"
                for error in result.errors
            )

    return AnnotationRecordValidationResult(
        valid=not errors,
        errors=errors,
        warnings=warnings,
    )


def validate_annotation_manifest(
    manifest: HumanAnnotationManifest,
    *,
    min_area: float = DEFAULT_MIN_POLYGON_AREA,
) -> AnnotationManifestValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    if manifest.split != "unassigned":
        errors.append("manifest split must remain unassigned")

    seen: set[str] = set()

    for record in manifest.images:
        if record.image_id in seen:
            errors.append(
                f"duplicate image_id: {record.image_id}"
            )

        seen.add(record.image_id)

        result = validate_annotation_record(
            record,
            min_area=min_area,
        )

        errors.extend(
            f"{record.image_id}: {error}"
            for error in result.errors
        )

        warnings.extend(
            f"{record.image_id}: {warning}"
            for warning in result.warnings
        )

    return AnnotationManifestValidationResult(
        valid=not errors,
        errors=errors,
        warnings=warnings,
    )
