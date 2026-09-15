from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.detection.models import (
    BoundingBox,
    DetectionCandidate,
)
from src.detection.onnx_detector import (
    ONNXModelSpec,
    ONNXWallDetector,
)
from src.detection.status import (
    DETECTION_ERROR,
    DETECTION_INVALID_INPUT,
    DETECTION_NO_CANDIDATES,
    DETECTION_READY,
)
from src.streetview.models import CanonicalImageAsset


class FakeSession:
    def __init__(
        self,
        outputs: list[Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.outputs = (
            outputs
            if outputs is not None
            else []
        )
        self.error = error
        self.calls: list[
            tuple[
                Any,
                dict[str, Any],
            ]
        ] = []

    def run(
        self,
        output_names: Any,
        input_feed: dict[str, Any],
    ) -> list[Any]:
        self.calls.append(
            (
                output_names,
                input_feed,
            )
        )

        if self.error is not None:
            raise self.error

        return self.outputs


def make_asset(
    *,
    status: str = "READY",
    image_path: str | None = "/tmp/image.jpg",
    width: int | None = 1024,
    height: int | None = 768,
) -> CanonicalImageAsset:
    return CanonicalImageAsset(
        asset_id="asset-001",
        status=status,
        image_path=image_path,
        width=width,
        height=height,
        format="JPEG",
        file_size_bytes=1000,
        sha256="abc123",
        provider="test-provider",
        image_id="image-001",
        source_latitude=15.0,
        source_longitude=79.0,
        image_latitude=15.0,
        image_longitude=79.0,
        requested_heading=90.0,
        actual_heading=95.0,
        side="right",
        capture_date="2026-01-01",
        metadata={},
    )


def make_spec() -> ONNXModelSpec:
    return ONNXModelSpec(
        model_path="/tmp/model.onnx",
        detector_name="test-onnx-wall-detector",
        detector_version="1.0",
        input_name="images",
    )


def wall_candidate() -> DetectionCandidate:
    return DetectionCandidate(
        class_name="wall_surface",
        confidence=0.91,
        bounding_box=BoundingBox(
            left=100.0,
            top=80.0,
            right=800.0,
            bottom=500.0,
        ),
    )


def test_model_spec_requires_detector_name() -> None:
    with pytest.raises(ValueError):
        ONNXModelSpec(
            model_path="/tmp/model.onnx",
            detector_name="",
            detector_version="1.0",
            input_name="images",
        )


def test_model_spec_requires_provider() -> None:
    with pytest.raises(ValueError):
        ONNXModelSpec(
            model_path="/tmp/model.onnx",
            detector_name="detector",
            detector_version="1.0",
            input_name="images",
            providers=(),
        )


def test_detector_runs_inference() -> None:
    session = FakeSession(
        outputs=[
            "raw-output",
        ]
    )

    detector = ONNXWallDetector(
        make_spec(),
        input_builder=lambda asset: (
            "input-tensor"
        ),
        output_parser=lambda outputs, asset: (
            wall_candidate(),
        ),
        session=session,
    )

    result = detector.detect(
        make_asset()
    )

    assert result.status == DETECTION_READY
    assert result.candidate_count == 1

    assert len(session.calls) == 1

    _, input_feed = session.calls[0]

    assert input_feed == {
        "images": "input-tensor"
    }


def test_detector_passes_raw_output_to_parser() -> None:
    session = FakeSession(
        outputs=[
            "model-result",
        ]
    )

    received: dict[str, Any] = {}

    def parser(
        outputs: list[Any],
        asset: CanonicalImageAsset,
    ) -> tuple[DetectionCandidate, ...]:
        received["outputs"] = outputs
        received["asset"] = asset

        return (
            wall_candidate(),
        )

    asset = make_asset()

    detector = ONNXWallDetector(
        make_spec(),
        input_builder=lambda value: "tensor",
        output_parser=parser,
        session=session,
    )

    detector.detect(asset)

    assert received["outputs"] == [
        "model-result",
    ]

    assert received["asset"] is asset


def test_detector_returns_no_candidates() -> None:
    detector = ONNXWallDetector(
        make_spec(),
        input_builder=lambda asset: "tensor",
        output_parser=lambda outputs, asset: (),
        session=FakeSession(),
    )

    result = detector.detect(
        make_asset()
    )

    assert (
        result.status
        == DETECTION_NO_CANDIDATES
    )

    assert result.candidates == ()


def test_detector_rejects_non_ready_asset() -> None:
    detector = ONNXWallDetector(
        make_spec(),
        input_builder=lambda asset: "tensor",
        output_parser=lambda outputs, asset: (),
        session=FakeSession(),
    )

    result = detector.detect(
        make_asset(
            status="INVALID"
        )
    )

    assert (
        result.status
        == DETECTION_INVALID_INPUT
    )

    assert (
        result.error_type
        == "InvalidInput"
    )


def test_detector_rejects_missing_image_path() -> None:
    detector = ONNXWallDetector(
        make_spec(),
        input_builder=lambda asset: "tensor",
        output_parser=lambda outputs, asset: (),
        session=FakeSession(),
    )

    result = detector.detect(
        make_asset(
            image_path=None
        )
    )

    assert (
        result.status
        == DETECTION_INVALID_INPUT
    )


def test_detector_converts_session_failure_to_error() -> None:
    detector = ONNXWallDetector(
        make_spec(),
        input_builder=lambda asset: "tensor",
        output_parser=lambda outputs, asset: (),
        session=FakeSession(
            error=RuntimeError(
                "inference failed"
            )
        ),
    )

    result = detector.detect(
        make_asset()
    )

    assert result.status == DETECTION_ERROR
    assert result.error_type == "RuntimeError"
    assert (
        result.error_message
        == "inference failed"
    )


def test_detector_converts_input_builder_failure_to_error() -> None:
    def bad_builder(
        asset: CanonicalImageAsset,
    ) -> Any:
        raise ValueError(
            "preprocessing failed"
        )

    detector = ONNXWallDetector(
        make_spec(),
        input_builder=bad_builder,
        output_parser=lambda outputs, asset: (),
        session=FakeSession(),
    )

    result = detector.detect(
        make_asset()
    )

    assert result.status == DETECTION_ERROR
    assert result.error_type == "ValueError"


def test_detector_requires_tuple_from_parser() -> None:
    detector = ONNXWallDetector(
        make_spec(),
        input_builder=lambda asset: "tensor",
        output_parser=lambda outputs, asset: [
            wall_candidate()
        ],
        session=FakeSession(),
    )

    result = detector.detect(
        make_asset()
    )

    assert result.status == DETECTION_ERROR
    assert result.error_type == "TypeError"


def test_detector_rejects_invalid_candidate_from_parser() -> None:
    detector = ONNXWallDetector(
        make_spec(),
        input_builder=lambda asset: "tensor",
        output_parser=lambda outputs, asset: (
            "not-a-candidate",
        ),
        session=FakeSession(),
    )

    result = detector.detect(
        make_asset()
    )

    assert result.status == DETECTION_ERROR
    assert result.error_type == "TypeError"


def test_session_is_created_lazily_once() -> None:
    calls: list[
        tuple[
            str,
            tuple[str, ...],
        ]
    ] = []

    session = FakeSession()

    def factory(
        model_path: str,
        providers: tuple[str, ...],
    ) -> FakeSession:
        calls.append(
            (
                model_path,
                providers,
            )
        )

        return session

    detector = ONNXWallDetector(
        make_spec(),
        input_builder=lambda asset: "tensor",
        output_parser=lambda outputs, asset: (),
        session_factory=factory,
    )

    detector.detect(
        make_asset()
    )

    detector.detect(
        make_asset()
    )

    assert len(calls) == 1

    assert calls[0] == (
        "/tmp/model.onnx",
        (
            "CPUExecutionProvider",
        ),
    )


def test_metadata_preserves_runtime_identity() -> None:
    detector = ONNXWallDetector(
        make_spec(),
        input_builder=lambda asset: "tensor",
        output_parser=lambda outputs, asset: (),
        session=FakeSession(),
    )

    result = detector.detect(
        make_asset()
    )

    assert (
        result.metadata["runtime"]
        == "onnxruntime"
    )

    assert (
        result.metadata["model_path"]
        == "/tmp/model.onnx"
    )

    assert (
        result.metadata["input_name"]
        == "images"
    )

    assert (
        result.metadata["providers"]
        == [
            "CPUExecutionProvider"
        ]
    )
