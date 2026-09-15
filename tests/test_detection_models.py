from __future__ import annotations

import pytest

from src.detection.fake import (
    FakeWallDetector,
    sample_wall_candidate,
)
from src.detection.models import (
    BoundingBox,
    DetectionCandidate,
    DetectionResult,
)
from src.detection.status import (
    DETECTION_NO_CANDIDATES,
    DETECTION_READY,
)
from src.streetview.models import CanonicalImageAsset


def make_asset() -> CanonicalImageAsset:
    return CanonicalImageAsset(
        asset_id="asset-001",
        status="READY",
        image_path="/tmp/asset-001.jpg",
        width=1200,
        height=800,
        format="JPEG",
        file_size_bytes=12345,
        sha256="abc123",
        provider="mapillary",
        image_id="image-001",
        source_latitude=14.669,
        source_longitude=79.574,
        image_latitude=14.6691,
        image_longitude=79.5741,
        requested_heading=90.0,
        actual_heading=88.0,
        side="left",
        capture_date="2026-01-01",
        metadata={},
    )


def test_bounding_box_calculates_geometry() -> None:
    box = BoundingBox(
        left=10,
        top=20,
        right=110,
        bottom=70,
    )

    assert box.width == 100
    assert box.height == 50
    assert box.area == 5000


def test_bounding_box_rejects_invalid_geometry() -> None:
    with pytest.raises(ValueError):
        BoundingBox(
            left=100,
            top=20,
            right=50,
            bottom=70,
        )


def test_detection_candidate_validates_confidence() -> None:
    with pytest.raises(ValueError):
        DetectionCandidate(
            class_name="wall_surface",
            confidence=1.5,
            bounding_box=BoundingBox(
                left=0,
                top=0,
                right=100,
                bottom=100,
            ),
        )


def test_detection_candidate_accepts_polygon() -> None:
    candidate = DetectionCandidate(
        class_name="wall_surface",
        confidence=0.9,
        bounding_box=BoundingBox(
            left=0,
            top=0,
            right=100,
            bottom=100,
        ),
        polygon=(
            (0, 0),
            (100, 0),
            (100, 100),
            (0, 100),
        ),
    )

    assert candidate.polygon is not None
    assert len(candidate.polygon) == 4


def test_detection_result_exposes_candidate_count() -> None:
    candidate = sample_wall_candidate()

    result = DetectionResult(
        asset_id="asset-001",
        detector_name="test-detector",
        detector_version="1.0",
        status=DETECTION_READY,
        image_width=1200,
        image_height=800,
        candidates=(candidate,),
        metadata={},
    )

    assert result.candidate_count == 1
    assert result.has_candidates is True


def test_detection_result_without_candidates() -> None:
    result = DetectionResult(
        asset_id="asset-001",
        detector_name="test-detector",
        detector_version="1.0",
        status=DETECTION_NO_CANDIDATES,
        image_width=1200,
        image_height=800,
        candidates=(),
        metadata={},
    )

    assert result.candidate_count == 0
    assert result.has_candidates is False


def test_fake_detector_preserves_asset_identity() -> None:
    asset = make_asset()

    detector = FakeWallDetector(
        candidates=(sample_wall_candidate(),)
    )

    result = detector.detect(asset)

    assert result.asset_id == asset.asset_id
    assert result.detector_name == "fake-wall-detector"
    assert result.detector_version == "1.0"
    assert result.status == DETECTION_READY
    assert result.candidate_count == 1


def test_fake_detector_can_return_no_candidates() -> None:
    asset = make_asset()

    detector = FakeWallDetector()

    result = detector.detect(asset)

    assert result.asset_id == asset.asset_id
    assert result.status == DETECTION_NO_CANDIDATES
    assert result.candidates == ()
