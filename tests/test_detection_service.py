from __future__ import annotations

from src.detection.fake import (
    FakeWallDetector,
    sample_wall_candidate,
)
from src.detection.models import DetectionResult
from src.detection.service import DetectionService
from src.detection.status import (
    DETECTION_INVALID_INPUT,
    DETECTION_NO_CANDIDATES,
    DETECTION_READY,
)
from src.streetview.models import CanonicalImageAsset


def make_asset(
    status: str = "READY",
) -> CanonicalImageAsset:
    return CanonicalImageAsset(
        asset_id="asset-001",
        status=status,
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


def test_service_delegates_ready_asset_to_detector() -> None:
    detector = FakeWallDetector(
        candidates=(sample_wall_candidate(),)
    )
    service = DetectionService(detector)

    result = service.detect(make_asset())

    assert result.asset_id == "asset-001"
    assert result.status == DETECTION_READY
    assert result.candidate_count == 1


def test_service_rejects_non_ready_asset() -> None:
    detector = FakeWallDetector(
        candidates=(sample_wall_candidate(),)
    )
    service = DetectionService(detector)

    result = service.detect(
        make_asset(status="INVALID")
    )

    assert result.status == DETECTION_INVALID_INPUT
    assert result.candidates == ()
    assert result.error_type == "InvalidInput"
    assert (
        result.metadata["reason"]
        == "canonical_asset_not_ready"
    )
    assert (
        result.metadata["asset_status"]
        == "INVALID"
    )


def test_service_rejects_missing_asset_path() -> None:
    detector = FakeWallDetector(
        candidates=(sample_wall_candidate(),)
    )
    service = DetectionService(detector)

    asset = make_asset()
    invalid_asset = CanonicalImageAsset(
        asset_id=asset.asset_id,
        status="INVALID",
        image_path=None,
        width=None,
        height=None,
        format=None,
        file_size_bytes=None,
        sha256=None,
        provider=asset.provider,
        image_id=asset.image_id,
        source_latitude=asset.source_latitude,
        source_longitude=asset.source_longitude,
        image_latitude=asset.image_latitude,
        image_longitude=asset.image_longitude,
        requested_heading=asset.requested_heading,
        actual_heading=asset.actual_heading,
        side=asset.side,
        capture_date=asset.capture_date,
        metadata=asset.metadata,
        error_type="ImageDecodeError",
        error_message="Invalid image.",
    )

    result = service.detect(invalid_asset)

    assert result.status == DETECTION_INVALID_INPUT
    assert result.error_type == "InvalidInput"


def test_service_preserves_detector_result() -> None:
    detector = FakeWallDetector()
    service = DetectionService(detector)

    result = service.detect(make_asset())

    assert isinstance(result, DetectionResult)
    assert result.status == DETECTION_NO_CANDIDATES
    assert result.detector_name == "fake-wall-detector"
    assert result.detector_version == "1.0"


def test_service_uses_injected_detector() -> None:
    first = FakeWallDetector()
    second = FakeWallDetector(
        candidates=(sample_wall_candidate(),)
    )

    first_result = DetectionService(first).detect(
        make_asset()
    )
    second_result = DetectionService(second).detect(
        make_asset()
    )

    assert first_result.candidate_count == 0
    assert second_result.candidate_count == 1
