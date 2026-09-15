from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from src.detection.base import WallDetector
from src.detection.models import (
    DetectionCandidate,
    DetectionResult,
)
from src.detection.status import (
    DETECTION_ERROR,
    DETECTION_INVALID_INPUT,
    DETECTION_NO_CANDIDATES,
    DETECTION_READY,
)
from src.streetview.models import CanonicalImageAsset


class ONNXSession(Protocol):
    """
    Minimal session contract required by ONNXWallDetector.

    Real onnxruntime.InferenceSession instances satisfy this interface,
    while tests can provide lightweight fakes.
    """

    def run(
        self,
        output_names: Any,
        input_feed: dict[str, Any],
    ) -> list[Any]:
        ...


InputBuilder = Callable[
    [CanonicalImageAsset],
    Any,
]

OutputParser = Callable[
    [
        list[Any],
        CanonicalImageAsset,
    ],
    tuple[DetectionCandidate, ...],
]

SessionFactory = Callable[
    [
        str,
        tuple[str, ...],
    ],
    ONNXSession,
]


@dataclass(frozen=True)
class ONNXModelSpec:
    """
    Framework-neutral ONNX model configuration.

    This class describes runtime identity and model I/O only.

    It deliberately does NOT define:
    - wall classes,
    - YOLO output layout,
    - normalization,
    - confidence thresholds,
    - non-maximum suppression,
    - segmentation decoding.

    Those concerns belong to the model-specific adapter layer.
    """

    model_path: str | Path

    detector_name: str
    detector_version: str

    input_name: str

    providers: tuple[str, ...] = (
        "CPUExecutionProvider",
    )

    def __post_init__(self) -> None:
        if not str(self.model_path).strip():
            raise ValueError(
                "model_path is required"
            )

        if not self.detector_name.strip():
            raise ValueError(
                "detector_name is required"
            )

        if not self.detector_version.strip():
            raise ValueError(
                "detector_version is required"
            )

        if not self.input_name.strip():
            raise ValueError(
                "input_name is required"
            )

        if not self.providers:
            raise ValueError(
                "at least one ONNX execution provider is required"
            )


class ONNXWallDetector(WallDetector):
    """
    Production-safe ONNX inference adapter.

    Responsibilities:
    - validate canonical input,
    - load an ONNX Runtime session lazily,
    - execute inference,
    - invoke model-specific output parsing,
    - convert expected failures into DetectionResult.

    Model-specific preprocessing and output decoding are injected.
    This prevents the core detection layer from depending on one
    particular model architecture.
    """

    def __init__(
        self,
        spec: ONNXModelSpec,
        input_builder: InputBuilder,
        output_parser: OutputParser,
        *,
        session: ONNXSession | None = None,
        session_factory: SessionFactory | None = None,
    ) -> None:
        self.spec = spec
        self.input_builder = input_builder
        self.output_parser = output_parser

        self.name = spec.detector_name
        self.version = spec.detector_version

        self._session = session
        self._session_factory = (
            session_factory
            or _default_session_factory
        )

    def detect(
        self,
        asset: CanonicalImageAsset,
    ) -> DetectionResult:
        validation_error = self._validate_asset(
            asset
        )

        if validation_error is not None:
            return DetectionResult(
                asset_id=asset.asset_id,
                detector_name=self.name,
                detector_version=self.version,
                status=DETECTION_INVALID_INPUT,
                image_width=asset.width,
                image_height=asset.height,
                candidates=(),
                metadata={
                    "model_path": str(
                        self.spec.model_path
                    ),
                    "input_name": self.spec.input_name,
                    "providers": list(
                        self.spec.providers
                    ),
                },
                error_type="InvalidInput",
                error_message=validation_error,
            )

        try:
            input_tensor = self.input_builder(
                asset
            )

            session = self._get_session()

            raw_outputs = session.run(
                None,
                {
                    self.spec.input_name: (
                        input_tensor
                    ),
                },
            )

            candidates = self.output_parser(
                raw_outputs,
                asset,
            )

            if not isinstance(
                candidates,
                tuple,
            ):
                raise TypeError(
                    "output_parser must return "
                    "tuple[DetectionCandidate, ...]"
                )

            for candidate in candidates:
                if not isinstance(
                    candidate,
                    DetectionCandidate,
                ):
                    raise TypeError(
                        "output_parser returned a "
                        "non-DetectionCandidate value"
                    )

            status = (
                DETECTION_READY
                if candidates
                else DETECTION_NO_CANDIDATES
            )

            return DetectionResult(
                asset_id=asset.asset_id,
                detector_name=self.name,
                detector_version=self.version,
                status=status,
                image_width=asset.width,
                image_height=asset.height,
                candidates=candidates,
                metadata={
                    "runtime": "onnxruntime",
                    "model_path": str(
                        self.spec.model_path
                    ),
                    "input_name": self.spec.input_name,
                    "providers": list(
                        self.spec.providers
                    ),
                },
            )

        except Exception as exc:
            return DetectionResult(
                asset_id=asset.asset_id,
                detector_name=self.name,
                detector_version=self.version,
                status=DETECTION_ERROR,
                image_width=asset.width,
                image_height=asset.height,
                candidates=(),
                metadata={
                    "runtime": "onnxruntime",
                    "model_path": str(
                        self.spec.model_path
                    ),
                    "input_name": self.spec.input_name,
                    "providers": list(
                        self.spec.providers
                    ),
                },
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

    def _get_session(
        self,
    ) -> ONNXSession:
        if self._session is None:
            self._session = (
                self._session_factory(
                    str(self.spec.model_path),
                    self.spec.providers,
                )
            )

        return self._session

    @staticmethod
    def _validate_asset(
        asset: CanonicalImageAsset,
    ) -> str | None:
        if asset.status != "READY":
            return (
                "Canonical image asset must have "
                "status READY."
            )

        if not asset.image_path:
            return (
                "Canonical image asset does not "
                "have an image_path."
            )

        if asset.width is None:
            return (
                "Canonical image asset does not "
                "have a width."
            )

        if asset.height is None:
            return (
                "Canonical image asset does not "
                "have a height."
            )

        return None


def _default_session_factory(
    model_path: str,
    providers: tuple[str, ...],
) -> ONNXSession:
    """
    Lazily import ONNX Runtime.

    Keeping this import inside the factory means the rest of the
    detection package remains importable even when onnxruntime is not
    installed, which is useful for development and unit tests.
    """

    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise RuntimeError(
            "onnxruntime is not installed. "
            "Install the runtime before using "
            "ONNXWallDetector with a real model."
        ) from exc

    model = Path(model_path)

    if not model.is_file():
        raise FileNotFoundError(
            f"ONNX model file does not exist: {model}"
        )

    return ort.InferenceSession(
        str(model),
        providers=list(providers),
    )
