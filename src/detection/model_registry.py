from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SUPPORTED_TASK = "wall_surface_detection"
SUPPORTED_ARTIFACT_FORMAT = "onnx"
SUPPORTED_RUNTIME = "onnxruntime"

SUPPORTED_GEOMETRY = {
    "bbox",
    "polygon",
    "mask",
}


@dataclass(frozen=True)
class ModelLicenseInfo:
    name: str
    commercial_use_allowed: bool
    attribution_required: bool = False
    source_url: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("license name is required")

        if not isinstance(self.commercial_use_allowed, bool):
            raise ValueError("commercial_use_allowed must be a boolean")

        if not isinstance(self.attribution_required, bool):
            raise ValueError("attribution_required must be a boolean")


@dataclass(frozen=True)
class DetectionModelSpec:
    model_id: str
    model_version: str
    task: str
    artifact_format: str
    runtime: str
    artifact_path: str
    sha256: str
    license_info: ModelLicenseInfo
    supported_geometry: tuple[str, ...] = ("bbox",)
    cpu_supported: bool = True
    input_width: int | None = None
    input_height: int | None = None
    description: str = ""

    def __post_init__(self) -> None:
        if not self.model_id.strip():
            raise ValueError("model_id is required")

        if not self.model_version.strip():
            raise ValueError("model_version is required")

        if self.task != SUPPORTED_TASK:
            raise ValueError(
                f"unsupported model task: {self.task!r}; "
                f"expected {SUPPORTED_TASK!r}"
            )

        if self.artifact_format != SUPPORTED_ARTIFACT_FORMAT:
            raise ValueError(
                f"unsupported artifact format: {self.artifact_format!r}; "
                f"expected {SUPPORTED_ARTIFACT_FORMAT!r}"
            )

        if self.runtime != SUPPORTED_RUNTIME:
            raise ValueError(
                f"unsupported runtime: {self.runtime!r}; "
                f"expected {SUPPORTED_RUNTIME!r}"
            )

        if not self.artifact_path.strip():
            raise ValueError("artifact_path is required")

        normalized_sha256 = self.sha256.strip().lower()

        if len(normalized_sha256) != 64:
            raise ValueError("sha256 must be a 64-character hexadecimal digest")

        if any(char not in "0123456789abcdef" for char in normalized_sha256):
            raise ValueError("sha256 must contain hexadecimal characters only")

        if not self.license_info.commercial_use_allowed:
            raise ValueError(
                "production model must explicitly allow commercial use"
            )

        if not self.supported_geometry:
            raise ValueError("at least one geometry type is required")

        invalid_geometry = set(self.supported_geometry) - SUPPORTED_GEOMETRY
        if invalid_geometry:
            raise ValueError(
                f"unsupported geometry types: {sorted(invalid_geometry)}"
            )

        if not isinstance(self.cpu_supported, bool):
            raise ValueError("cpu_supported must be a boolean")

        if self.input_width is not None and self.input_width <= 0:
            raise ValueError("input_width must be greater than zero")

        if self.input_height is not None and self.input_height <= 0:
            raise ValueError("input_height must be greater than zero")

        object.__setattr__(self, "sha256", normalized_sha256)

    @property
    def supports_polygon(self) -> bool:
        return "polygon" in self.supported_geometry

    @property
    def supports_mask(self) -> bool:
        return "mask" in self.supported_geometry

    @property
    def supports_bbox(self) -> bool:
        return "bbox" in self.supported_geometry

    @property
    def production_ready(self) -> bool:
        return (
            self.task == SUPPORTED_TASK
            and self.artifact_format == SUPPORTED_ARTIFACT_FORMAT
            and self.runtime == SUPPORTED_RUNTIME
            and self.license_info.commercial_use_allowed
            and self.cpu_supported
            and bool(self.sha256)
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "task": self.task,
            "artifact_format": self.artifact_format,
            "runtime": self.runtime,
            "artifact_path": self.artifact_path,
            "sha256": self.sha256,
            "license": {
                "name": self.license_info.name,
                "commercial_use_allowed": (
                    self.license_info.commercial_use_allowed
                ),
                "attribution_required": (
                    self.license_info.attribution_required
                ),
                "source_url": self.license_info.source_url,
            },
            "supported_geometry": list(self.supported_geometry),
            "cpu_supported": self.cpu_supported,
            "input_width": self.input_width,
            "input_height": self.input_height,
            "description": self.description,
            "production_ready": self.production_ready,
        }


class DetectionModelRegistry:
    """
    Registry for approved wall-surface detection model specifications.

    The registry stores model metadata only. It does not download models,
    load inference runtimes, or make commercial-suitability decisions about
    individual wall candidates.
    """

    def __init__(
        self,
        models: tuple[DetectionModelSpec, ...] = (),
    ) -> None:
        self._models: dict[str, DetectionModelSpec] = {}

        for model in models:
            self.register(model)

    def register(self, model: DetectionModelSpec) -> None:
        if model.model_id in self._models:
            raise ValueError(
                f"model already registered: {model.model_id}"
            )

        self._models[model.model_id] = model

    def get(self, model_id: str) -> DetectionModelSpec:
        try:
            return self._models[model_id]
        except KeyError as exc:
            raise KeyError(f"unknown detection model: {model_id}") from exc

    def list_models(self) -> tuple[DetectionModelSpec, ...]:
        return tuple(self._models.values())

    def production_models(self) -> tuple[DetectionModelSpec, ...]:
        return tuple(
            model
            for model in self._models.values()
            if model.production_ready
        )


def validate_model_artifact(
    model: DetectionModelSpec,
) -> None:
    """
    Validate that the configured artifact path is structurally acceptable.

    This deliberately does not load the model. Actual artifact existence,
    checksum verification, and ONNX graph validation belong to the deployment
    / model-loading layer.
    """

    path = Path(model.artifact_path)

    if path.suffix.lower() != ".onnx":
        raise ValueError("model artifact must use the .onnx extension")

    if not model.production_ready:
        raise ValueError(
            f"model is not production-ready: {model.model_id}"
        )
