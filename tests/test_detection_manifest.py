from __future__ import annotations

import json

import pytest

from src.detection.manifest import (
    DetectionManifest,
    DetectionManifestError,
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


def make_result(
    *,
    asset_id: str = "asset-001",
    candidates: tuple[DetectionCandidate, ...] = (),
) -> DetectionResult:
    return DetectionResult(
        asset_id=asset_id,
        detector_name="test-detector",
        detector_version="1.0",
        status=(
            DETECTION_READY
            if candidates
            else DETECTION_NO_CANDIDATES
        ),
        image_width=1200,
        image_height=800,
        candidates=candidates,
        metadata={
            "source_provider": "mapillary",
            "test": True,
        },
    )


def make_candidate() -> DetectionCandidate:
    return DetectionCandidate(
        class_name="wall_surface",
        confidence=0.93,
        bounding_box=BoundingBox(
            left=100,
            top=80,
            right=900,
            bottom=500,
        ),
        class_id=1,
        polygon=(
            (100, 80),
            (900, 80),
            (900, 500),
            (100, 500),
        ),
        metadata={
            "model_class": "wall_surface",
        },
    )


def test_manifest_save_and_load(
    tmp_path,
) -> None:
    path = tmp_path / "detections.json"

    manifest = DetectionManifest(path)

    result = make_result(
        candidates=(make_candidate(),)
    )

    manifest.save(result)

    loaded = manifest.get(
        "asset-001"
    )

    assert loaded is not None
    assert loaded.asset_id == "asset-001"
    assert loaded.detector_name == "test-detector"
    assert loaded.detector_version == "1.0"
    assert loaded.status == DETECTION_READY
    assert loaded.candidate_count == 1

    candidate = loaded.candidates[0]

    assert candidate.class_name == "wall_surface"
    assert candidate.confidence == 0.93
    assert candidate.class_id == 1
    assert candidate.bounding_box.left == 100
    assert candidate.bounding_box.right == 900
    assert candidate.polygon is not None
    assert len(candidate.polygon) == 4


def test_manifest_persists_across_instances(
    tmp_path,
) -> None:
    path = tmp_path / "detections.json"

    result = make_result(
        candidates=(make_candidate(),)
    )

    DetectionManifest(path).save(result)

    second = DetectionManifest(path)

    assert second.exists("asset-001")
    assert second.count() == 1
    assert second.get("asset-001") == result


def test_manifest_write_is_idempotent(
    tmp_path,
) -> None:
    path = tmp_path / "detections.json"

    result = make_result(
        candidates=(make_candidate(),)
    )

    manifest = DetectionManifest(path)
    manifest.save(result)

    first_payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    manifest.save(result)

    second_payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    assert (
        second_payload["detections"]
        == first_payload["detections"]
    )


def test_manifest_replaces_existing_asset(
    tmp_path,
) -> None:
    path = tmp_path / "detections.json"

    manifest = DetectionManifest(path)

    first = make_result()

    second = make_result(
        candidates=(make_candidate(),)
    )

    manifest.save(first)
    manifest.save(second)

    loaded = manifest.get(
        "asset-001"
    )

    assert loaded is not None
    assert loaded.status == DETECTION_READY
    assert loaded.candidate_count == 1
    assert manifest.count() == 1


def test_unknown_asset_returns_none(
    tmp_path,
) -> None:
    manifest = DetectionManifest(
        tmp_path / "detections.json"
    )

    assert manifest.get("missing") is None
    assert manifest.exists("missing") is False


def test_manifest_remove(
    tmp_path,
) -> None:
    path = tmp_path / "detections.json"

    manifest = DetectionManifest(path)

    manifest.save(make_result())

    assert manifest.remove("asset-001") is True
    assert manifest.exists("asset-001") is False
    assert manifest.count() == 0

    assert manifest.remove("asset-001") is False


def test_manifest_all_returns_results(
    tmp_path,
) -> None:
    manifest = DetectionManifest(
        tmp_path / "detections.json"
    )

    manifest.save(
        make_result(asset_id="asset-001")
    )
    manifest.save(
        make_result(asset_id="asset-002")
    )

    results = manifest.all()

    assert len(results) == 2
    assert {
        result.asset_id
        for result in results
    } == {
        "asset-001",
        "asset-002",
    }


def test_invalid_manifest_root_is_rejected(
    tmp_path,
) -> None:
    path = tmp_path / "detections.json"

    path.write_text(
        "[]",
        encoding="utf-8",
    )

    with pytest.raises(
        DetectionManifestError,
        match="root must be a JSON object",
    ):
        DetectionManifest(path)


def test_invalid_detections_section_is_rejected(
    tmp_path,
) -> None:
    path = tmp_path / "detections.json"

    path.write_text(
        json.dumps(
            {
                "version": 1,
                "detections": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        DetectionManifestError,
        match="detections.*JSON object",
    ):
        DetectionManifest(path)


def test_error_information_is_preserved(
    tmp_path,
) -> None:
    path = tmp_path / "detections.json"

    result = DetectionResult(
        asset_id="asset-error",
        detector_name="test-detector",
        detector_version="1.0",
        status="ERROR",
        image_width=1200,
        image_height=800,
        candidates=(),
        metadata={
            "source": "test",
        },
        error_type="InferenceError",
        error_message="Model inference failed.",
    )

    manifest = DetectionManifest(path)
    manifest.save(result)

    loaded = manifest.get(
        "asset-error"
    )

    assert loaded is not None
    assert loaded.status == "ERROR"
    assert loaded.error_type == "InferenceError"
    assert (
        loaded.error_message
        == "Model inference failed."
    )


def test_manifest_preserves_metadata(
    tmp_path,
) -> None:
    path = tmp_path / "detections.json"

    result = DetectionResult(
        asset_id="asset-meta",
        detector_name="domain-detector",
        detector_version="2026.1",
        status=DETECTION_READY,
        image_width=1920,
        image_height=1080,
        candidates=(make_candidate(),),
        metadata={
            "requested_heading": 90.0,
            "actual_heading": 87.5,
            "source_side": "left",
        },
    )

    manifest = DetectionManifest(path)
    manifest.save(result)

    loaded = manifest.get(
        "asset-meta"
    )

    assert loaded is not None
    assert loaded.metadata[
        "requested_heading"
    ] == 90.0
    assert loaded.metadata[
        "actual_heading"
    ] == 87.5
    assert loaded.metadata[
        "source_side"
    ] == "left"
