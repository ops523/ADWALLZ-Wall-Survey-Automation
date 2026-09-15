from __future__ import annotations

import pytest

from src.detection.model_registry import (
    DetectionModelRegistry,
    DetectionModelSpec,
    ModelLicenseInfo,
    SUPPORTED_TASK,
    validate_model_artifact,
)


VALID_SHA256 = "a" * 64


def make_model(
    *,
    model_id: str = "wall-model",
    geometry: tuple[str, ...] = ("bbox", "polygon"),
    license_allowed: bool = True,
) -> DetectionModelSpec:
    return DetectionModelSpec(
        model_id=model_id,
        model_version="1.0.0",
        task=SUPPORTED_TASK,
        artifact_format="onnx",
        runtime="onnxruntime",
        artifact_path="models/wall-model.onnx",
        sha256=VALID_SHA256,
        license_info=ModelLicenseInfo(
            name="Example Commercial License",
            commercial_use_allowed=license_allowed,
        ),
        supported_geometry=geometry,
        cpu_supported=True,
        input_width=640,
        input_height=640,
    )


def test_valid_model_spec_is_production_ready() -> None:
    model = make_model()

    assert model.production_ready is True
    assert model.supports_bbox is True
    assert model.supports_polygon is True
    assert model.supports_mask is False


def test_sha256_is_normalized() -> None:
    model = make_model()

    assert model.sha256 == VALID_SHA256


def test_invalid_sha256_is_rejected() -> None:
    with pytest.raises(ValueError, match="64-character"):
        DetectionModelSpec(
            model_id="wall-model",
            model_version="1.0.0",
            task=SUPPORTED_TASK,
            artifact_format="onnx",
            runtime="onnxruntime",
            artifact_path="models/wall-model.onnx",
            sha256="abc",
            license_info=ModelLicenseInfo(
                name="Commercial",
                commercial_use_allowed=True,
            ),
        )


def test_non_commercial_model_is_rejected() -> None:
    with pytest.raises(ValueError, match="commercial use"):
        make_model(license_allowed=False)


def test_unsupported_task_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported model task"):
        DetectionModelSpec(
            model_id="wall-model",
            model_version="1.0.0",
            task="object_detection",
            artifact_format="onnx",
            runtime="onnxruntime",
            artifact_path="models/wall-model.onnx",
            sha256=VALID_SHA256,
            license_info=ModelLicenseInfo(
                name="Commercial",
                commercial_use_allowed=True,
            ),
        )


def test_unsupported_runtime_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported runtime"):
        DetectionModelSpec(
            model_id="wall-model",
            model_version="1.0.0",
            task=SUPPORTED_TASK,
            artifact_format="onnx",
            runtime="pytorch",
            artifact_path="models/wall-model.onnx",
            sha256=VALID_SHA256,
            license_info=ModelLicenseInfo(
                name="Commercial",
                commercial_use_allowed=True,
            ),
        )


def test_unsupported_artifact_format_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported artifact format"):
        DetectionModelSpec(
            model_id="wall-model",
            model_version="1.0.0",
            task=SUPPORTED_TASK,
            artifact_format="pt",
            runtime="onnxruntime",
            artifact_path="models/wall-model.onnx",
            sha256=VALID_SHA256,
            license_info=ModelLicenseInfo(
                name="Commercial",
                commercial_use_allowed=True,
            ),
        )


def test_unknown_geometry_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported geometry"):
        make_model(geometry=("bbox", "circle"))


def test_cpu_support_is_required_for_production_model() -> None:
    with pytest.raises(ValueError, match="cpu_supported"):
        DetectionModelSpec(
            model_id="wall-model",
            model_version="1.0.0",
            task=SUPPORTED_TASK,
            artifact_format="onnx",
            runtime="onnxruntime",
            artifact_path="models/wall-model.onnx",
            sha256=VALID_SHA256,
            license_info=ModelLicenseInfo(
                name="Commercial",
                commercial_use_allowed=True,
            ),
            cpu_supported="yes",  # type: ignore[arg-type]
        )


def test_registry_register_and_get() -> None:
    model = make_model()
    registry = DetectionModelRegistry()

    registry.register(model)

    assert registry.get("wall-model") == model
    assert registry.list_models() == (model,)


def test_duplicate_model_id_is_rejected() -> None:
    model = make_model()
    registry = DetectionModelRegistry((model,))

    with pytest.raises(ValueError, match="already registered"):
        registry.register(model)


def test_unknown_model_is_rejected() -> None:
    registry = DetectionModelRegistry()

    with pytest.raises(KeyError, match="unknown detection model"):
        registry.get("missing-model")


def test_production_models_only_returns_approved_models() -> None:
    model = make_model()
    registry = DetectionModelRegistry((model,))

    assert registry.production_models() == (model,)


def test_model_serialization_is_json_friendly() -> None:
    model = make_model()

    payload = model.as_dict()

    assert payload["model_id"] == "wall-model"
    assert payload["supported_geometry"] == ["bbox", "polygon"]
    assert payload["license"]["commercial_use_allowed"] is True
    assert payload["production_ready"] is True


def test_validate_model_artifact_accepts_onnx_path() -> None:
    model = make_model()

    validate_model_artifact(model)


def test_validate_model_artifact_rejects_non_onnx_path() -> None:
    model = DetectionModelSpec(
        model_id="wall-model",
        model_version="1.0.0",
        task=SUPPORTED_TASK,
        artifact_format="onnx",
        runtime="onnxruntime",
        artifact_path="models/wall-model.bin",
        sha256=VALID_SHA256,
        license_info=ModelLicenseInfo(
            name="Commercial",
            commercial_use_allowed=True,
        ),
    )

    with pytest.raises(ValueError, match=r"\.onnx"):
        validate_model_artifact(model)
