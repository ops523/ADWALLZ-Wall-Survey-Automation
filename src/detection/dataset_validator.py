from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .dataset import (
    CATEGORY_HARD_NEGATIVE,
    CATEGORY_NEGATIVE,
    CATEGORY_POSITIVE,
    DatasetManifest,
    calculate_sha256,
)


@dataclass(frozen=True)
class DatasetValidationResult:
    valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)


def validate_dataset_files(
    manifest: DatasetManifest,
    dataset_root: str | Path,
    *,
    verify_sha256: bool = True,
) -> DatasetValidationResult:
    root = Path(dataset_root)

    errors: list[str] = []
    warnings: list[str] = []

    if not root.exists():
        return DatasetValidationResult(
            valid=False,
            errors=(f"dataset root does not exist: {root}",),
            warnings=(),
        )

    if not root.is_dir():
        return DatasetValidationResult(
            valid=False,
            errors=(f"dataset root is not a directory: {root}",),
            warnings=(),
        )

    for image in manifest.images:
        image_path = root / image.relative_path

        if not image_path.is_file():
            errors.append(
                f"missing image: {image.relative_path}"
            )
            continue

        if verify_sha256:
            actual_sha256 = calculate_sha256(image_path)

            if actual_sha256 != image.sha256:
                errors.append(
                    f"sha256 mismatch: {image.relative_path}"
                )

        if image.category == CATEGORY_POSITIVE:
            if not image.annotations:
                errors.append(
                    f"positive image has no annotations: {image.image_id}"
                )

        elif image.category in {
            CATEGORY_NEGATIVE,
            CATEGORY_HARD_NEGATIVE,
        }:
            if image.annotations:
                errors.append(
                    f"negative image has annotations: {image.image_id}"
                )

        if image.split == "test" and image.category == CATEGORY_POSITIVE:
            if image.annotation_count == 0:
                errors.append(
                    f"positive test image has no annotation: {image.image_id}"
                )

    positive_count = sum(
        image.category == CATEGORY_POSITIVE
        for image in manifest.images
    )

    negative_count = sum(
        image.category == CATEGORY_NEGATIVE
        for image in manifest.images
    )

    hard_negative_count = sum(
        image.category == CATEGORY_HARD_NEGATIVE
        for image in manifest.images
    )

    if positive_count == 0:
        warnings.append("dataset contains no positive examples")

    if negative_count == 0:
        warnings.append("dataset contains no negative examples")

    if hard_negative_count == 0:
        warnings.append("dataset contains no hard-negative examples")

    return DatasetValidationResult(
        valid=not errors,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )
