from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from src.detection.models import (
    BoundingBox,
    DetectionCandidate,
    DetectionResult,
)
from src.detection.wall_surface import WALL_SURFACE_CLASS_NAME


@dataclass(frozen=True)
class CandidateFilterConfig:
    """
    Detector-level wall candidate filtering.

    These thresholds are geometric / detector-quality safeguards only.
    They do NOT determine commercial suitability.
    """

    confidence_threshold: float = 0.25

    # Minimum fraction of the image covered by the candidate bbox.
    # This prevents tiny detections from reaching downstream stages.
    min_bbox_area_ratio: float = 0.005

    # Maximum number of wall candidates retained per image.
    max_candidates: int = 20

    # IoU above which two candidates are considered duplicates.
    duplicate_iou_threshold: float = 0.80

    # Minimum polygon area ratio when polygon geometry exists.
    min_polygon_area_ratio: float = 0.003

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError(
                "confidence_threshold must be between 0 and 1"
            )

        if not 0.0 < self.min_bbox_area_ratio <= 1.0:
            raise ValueError(
                "min_bbox_area_ratio must be greater than zero "
                "and at most one"
            )

        if not 0.0 < self.min_polygon_area_ratio <= 1.0:
            raise ValueError(
                "min_polygon_area_ratio must be greater than zero "
                "and at most one"
            )

        if self.max_candidates <= 0:
            raise ValueError("max_candidates must be greater than zero")

        if not 0.0 < self.duplicate_iou_threshold <= 1.0:
            raise ValueError(
                "duplicate_iou_threshold must be greater than zero "
                "and at most one"
            )


@dataclass(frozen=True)
class FilteredWallCandidates:
    """
    Result of wall candidate post-processing.

    Candidates are ordered deterministically by:
    1. confidence descending
    2. geometric area descending
    3. original candidate position
    """

    candidates: tuple[DetectionCandidate, ...]
    input_count: int
    rejected_count: int
    duplicate_count: int

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)


def _bbox_area_ratio(
    bbox: BoundingBox,
    image_width: int,
    image_height: int,
) -> float:
    image_area = image_width * image_height

    if image_area <= 0:
        return 0.0

    return bbox.area / image_area


def _polygon_area(
    polygon: tuple[tuple[float, float], ...],
) -> float:
    """
    Calculate polygon area using the shoelace formula.

    Coordinates are image-space coordinates.
    """

    if len(polygon) < 3:
        return 0.0

    area = 0.0

    for index, (x1, y1) in enumerate(polygon):
        x2, y2 = polygon[(index + 1) % len(polygon)]
        area += (x1 * y2) - (x2 * y1)

    return abs(area) / 2.0


def _polygon_area_ratio(
    polygon: tuple[tuple[float, float], ...],
    image_width: int,
    image_height: int,
) -> float:
    image_area = image_width * image_height

    if image_area <= 0:
        return 0.0

    return _polygon_area(polygon) / image_area


def _intersection_area(
    first: BoundingBox,
    second: BoundingBox,
) -> float:
    left = max(first.left, second.left)
    top = max(first.top, second.top)
    right = min(first.right, second.right)
    bottom = min(first.bottom, second.bottom)

    if right <= left or bottom <= top:
        return 0.0

    return (right - left) * (bottom - top)


def _iou(
    first: BoundingBox,
    second: BoundingBox,
) -> float:
    intersection = _intersection_area(first, second)

    if intersection <= 0:
        return 0.0

    union = first.area + second.area - intersection

    if union <= 0:
        return 0.0

    return intersection / union


def _has_valid_geometry(
    candidate: DetectionCandidate,
    image_width: int,
    image_height: int,
    config: CandidateFilterConfig,
) -> bool:
    bbox = candidate.bounding_box

    values = (
        bbox.left,
        bbox.top,
        bbox.right,
        bbox.bottom,
        bbox.width,
        bbox.height,
    )

    if not all(isfinite(value) for value in values):
        return False

    if bbox.right > image_width or bbox.bottom > image_height:
        return False

    if candidate.polygon is not None:
        if len(candidate.polygon) < 3:
            return False

        polygon_values = [
            value
            for point in candidate.polygon
            for value in point
        ]

        if not all(isfinite(value) for value in polygon_values):
            return False

        polygon_area_ratio = _polygon_area_ratio(
            candidate.polygon,
            image_width,
            image_height,
        )

        if polygon_area_ratio < config.min_polygon_area_ratio:
            return False

    return True


def _passes_basic_filter(
    candidate: DetectionCandidate,
    image_width: int,
    image_height: int,
    config: CandidateFilterConfig,
) -> bool:
    if (
        candidate.class_name.strip().casefold()
        != WALL_SURFACE_CLASS_NAME.casefold()
    ):
        return False

    if candidate.confidence < config.confidence_threshold:
        return False

    if not _has_valid_geometry(
        candidate,
        image_width,
        image_height,
        config,
    ):
        return False

    if (
        _bbox_area_ratio(
            candidate.bounding_box,
            image_width,
            image_height,
        )
        < config.min_bbox_area_ratio
    ):
        return False

    return True


def _deduplicate(
    candidates: list[DetectionCandidate],
    iou_threshold: float,
) -> tuple[tuple[DetectionCandidate, ...], int]:
    """
    Deterministic confidence-first duplicate suppression.

    This is intentionally bbox-based. Polygon intersection can be added
    later when training data demonstrates that bbox IoU is insufficient.
    """

    ordered = sorted(
        enumerate(candidates),
        key=lambda item: (
            -item[1].confidence,
            -item[1].bounding_box.area,
            item[0],
        ),
    )

    retained: list[DetectionCandidate] = []
    duplicate_count = 0

    for _, candidate in ordered:
        duplicate = any(
            _iou(
                candidate.bounding_box,
                existing.bounding_box,
            )
            >= iou_threshold
            for existing in retained
        )

        if duplicate:
            duplicate_count += 1
            continue

        retained.append(candidate)

    return tuple(retained), duplicate_count


def filter_wall_candidates(
    result: DetectionResult,
    config: CandidateFilterConfig | None = None,
) -> FilteredWallCandidates:
    """
    Filter raw detector candidates into downstream wall candidates.

    This function intentionally does NOT assess:
    - floor
    - square footage
    - obstruction
    - signage
    - commercial suitability
    - accessibility
    """

    config = config or CandidateFilterConfig()

    input_count = len(result.candidates)

    if (
        result.image_width is None
        or result.image_height is None
        or result.image_width <= 0
        or result.image_height <= 0
    ):
        return FilteredWallCandidates(
            candidates=(),
            input_count=input_count,
            rejected_count=input_count,
            duplicate_count=0,
        )

    basic_candidates = [
        candidate
        for candidate in result.candidates
        if _passes_basic_filter(
            candidate,
            result.image_width,
            result.image_height,
            config,
        )
    ]

    rejected_count = input_count - len(basic_candidates)

    deduplicated, duplicate_count = _deduplicate(
        basic_candidates,
        config.duplicate_iou_threshold,
    )

    final_candidates = deduplicated[: config.max_candidates]

    return FilteredWallCandidates(
        candidates=final_candidates,
        input_count=input_count,
        rejected_count=rejected_count,
        duplicate_count=duplicate_count,
    )
