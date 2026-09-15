from __future__ import annotations

from src.detection.candidate_filter import (
    CandidateFilterConfig,
    filter_wall_candidates,
)
from src.detection.models import (
    BoundingBox,
    DetectionCandidate,
    DetectionResult,
)


def make_candidate(
    confidence: float = 0.90,
    class_name: str = "wall_surface",
    bbox: BoundingBox | None = None,
    polygon: tuple[tuple[float, float], ...] | None = None,
) -> DetectionCandidate:
    return DetectionCandidate(
        class_name=class_name,
        confidence=confidence,
        bounding_box=bbox
        or BoundingBox(
            left=100,
            top=100,
            right=600,
            bottom=500,
        ),
        polygon=polygon,
    )


def make_result(
    candidates: tuple[DetectionCandidate, ...],
    width: int = 1000,
    height: int = 800,
) -> DetectionResult:
    return DetectionResult(
        asset_id="asset-001",
        detector_name="test",
        detector_version="1.0",
        status="READY",
        image_width=width,
        image_height=height,
        candidates=candidates,
        metadata={},
    )


def test_default_config() -> None:
    config = CandidateFilterConfig()

    assert config.confidence_threshold == 0.25
    assert config.min_bbox_area_ratio == 0.005
    assert config.max_candidates == 20


def test_low_confidence_candidate_is_rejected() -> None:
    result = make_result(
        (make_candidate(confidence=0.20),)
    )

    filtered = filter_wall_candidates(result)

    assert filtered.candidate_count == 0
    assert filtered.rejected_count == 1


def test_wrong_class_is_rejected() -> None:
    result = make_result(
        (make_candidate(class_name="building"),)
    )

    filtered = filter_wall_candidates(result)

    assert filtered.candidate_count == 0
    assert filtered.rejected_count == 1


def test_tiny_candidate_is_rejected() -> None:
    result = make_result(
        (
            make_candidate(
                bbox=BoundingBox(
                    left=10,
                    top=10,
                    right=20,
                    bottom=20,
                )
            ),
        )
    )

    filtered = filter_wall_candidates(result)

    assert filtered.candidate_count == 0


def test_valid_candidate_is_retained() -> None:
    candidate = make_candidate()

    result = make_result((candidate,))

    filtered = filter_wall_candidates(result)

    assert filtered.candidate_count == 1
    assert filtered.candidates[0] == candidate


def test_polygon_geometry_is_supported() -> None:
    candidate = make_candidate(
        polygon=(
            (100, 100),
            (600, 100),
            (600, 500),
            (100, 500),
        )
    )

    result = make_result((candidate,))

    filtered = filter_wall_candidates(result)

    assert filtered.candidate_count == 1
    assert filtered.candidates[0].polygon == candidate.polygon


def test_tiny_polygon_is_rejected() -> None:
    candidate = make_candidate(
        polygon=(
            (100, 100),
            (110, 100),
            (110, 110),
        )
    )

    result = make_result((candidate,))

    filtered = filter_wall_candidates(result)

    assert filtered.candidate_count == 0


def test_overlapping_duplicates_are_suppressed() -> None:
    first = make_candidate(
        confidence=0.95,
        bbox=BoundingBox(
            left=100,
            top=100,
            right=600,
            bottom=500,
        ),
    )

    second = make_candidate(
        confidence=0.80,
        bbox=BoundingBox(
            left=110,
            top=105,
            right=595,
            bottom=495,
        ),
    )

    result = make_result((first, second))

    filtered = filter_wall_candidates(result)

    assert filtered.candidate_count == 1
    assert filtered.candidates[0] == first
    assert filtered.duplicate_count == 1


def test_separate_walls_are_retained() -> None:
    first = make_candidate(
        bbox=BoundingBox(
            left=50,
            top=100,
            right=400,
            bottom=500,
        )
    )

    second = make_candidate(
        bbox=BoundingBox(
            left=550,
            top=100,
            right=950,
            bottom=500,
        )
    )

    result = make_result((first, second))

    filtered = filter_wall_candidates(result)

    assert filtered.candidate_count == 2


def test_higher_confidence_candidate_wins_duplicate() -> None:
    low = make_candidate(
        confidence=0.60,
        bbox=BoundingBox(
            left=100,
            top=100,
            right=600,
            bottom=500,
        ),
    )

    high = make_candidate(
        confidence=0.95,
        bbox=BoundingBox(
            left=105,
            top=105,
            right=595,
            bottom=495,
        ),
    )

    result = make_result((low, high))

    filtered = filter_wall_candidates(result)

    assert filtered.candidate_count == 1
    assert filtered.candidates[0] == high


def test_candidates_are_limited() -> None:
    candidates = tuple(
        make_candidate(
            confidence=0.90 - (index * 0.01),
            bbox=BoundingBox(
                left=20 + index * 35,
                top=100,
                right=40 + index * 35,
                bottom=700,
            ),
        )
        for index in range(10)
    )

    result = make_result(candidates)

    filtered = filter_wall_candidates(
        result,
        CandidateFilterConfig(
            max_candidates=3,
            min_bbox_area_ratio=0.001,
        ),
    )

    assert filtered.candidate_count == 3


def test_missing_image_dimensions_reject_all_candidates() -> None:
    candidate = make_candidate()

    result = DetectionResult(
        asset_id="asset-001",
        detector_name="test",
        detector_version="1.0",
        status="READY",
        image_width=None,
        image_height=None,
        candidates=(candidate,),
        metadata={},
    )

    filtered = filter_wall_candidates(result)

    assert filtered.candidate_count == 0
    assert filtered.rejected_count == 1


def test_out_of_bounds_candidate_is_rejected() -> None:
    candidate = make_candidate(
        bbox=BoundingBox(
            left=900,
            top=100,
            right=1100,
            bottom=500,
        )
    )

    result = make_result((candidate,))

    filtered = filter_wall_candidates(result)

    assert filtered.candidate_count == 0
