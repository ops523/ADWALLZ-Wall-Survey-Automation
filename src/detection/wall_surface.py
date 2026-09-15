from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


WALL_SURFACE_CLASS_NAME = "wall_surface"

# Detection is intentionally broader than commercial suitability.
#
# A wall_surface candidate may subsequently be rejected because of:
# - insufficient real-world area
# - wrong floor
# - obstruction
# - excessive windows/signage
# - poor visibility
# - unsuitable road-facing geometry
#
# Those decisions belong to downstream packs.
DETECTION_TASK = "wall_surface_detection"

# Polygon geometry is preferred whenever the model provides it.
GEOMETRY_BBOX = "bbox"
GEOMETRY_POLYGON = "polygon"


@dataclass(frozen=True)
class WallSurfaceModelConfig:
    """
    Model-independent configuration for wall-surface inference.

    This class deliberately contains no framework-specific objects.
    A concrete ONNX / segmentation / detector adapter can consume it.
    """

    confidence_threshold: float = 0.25
    class_name: str = WALL_SURFACE_CLASS_NAME
    prefer_polygon: bool = True

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError(
                "confidence_threshold must be between 0 and 1"
            )

        if not self.class_name.strip():
            raise ValueError("class_name is required")


@dataclass(frozen=True)
class WallSurfaceReference:
    """
    A reference image record for the wall-surface dataset.

    Reference images are not automatically treated as machine-learning
    annotations. An image can be used as a visual reference before
    polygon labels are created by a human annotator.
    """

    image_path: str
    category: str
    annotation_status: str
    source: str
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.image_path.strip():
            raise ValueError("image_path is required")

        if not self.category.strip():
            raise ValueError("category is required")

        if not self.annotation_status.strip():
            raise ValueError("annotation_status is required")

        if not self.source.strip():
            raise ValueError("source is required")


REFERENCE_CATEGORY_POSITIVE = "positive"
REFERENCE_CATEGORY_NEGATIVE = "negative"
REFERENCE_CATEGORY_HARD_NEGATIVE = "hard_negative"

ANNOTATION_VISUAL_REFERENCE = "visual_reference"
ANNOTATION_POLYGON = "polygon"
ANNOTATION_BBOX = "bbox"
ANNOTATION_UNANNOTATED = "unannotated"


def validate_reference_image_path(
    image_path: str | Path,
) -> Path:
    """
    Validate that a reference image exists and has an image extension.

    This function does not open or decode the image. Image decoding remains
    the responsibility of the imagery/preprocessing layer.
    """

    path = Path(image_path)

    if not path.exists():
        raise FileNotFoundError(
            f"reference image does not exist: {path}"
        )

    if not path.is_file():
        raise ValueError(
            f"reference image path is not a file: {path}"
        )

    if path.suffix.casefold() not in {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
    }:
        raise ValueError(
            f"unsupported reference image extension: {path.suffix}"
        )

    return path


def is_wall_surface_class(class_name: str) -> bool:
    """
    Return True only for the canonical wall-surface class.

    Model-specific class aliases must be mapped by the model adapter rather
    than spreading model labels through downstream application code.
    """

    return (
        class_name.strip().casefold()
        == WALL_SURFACE_CLASS_NAME.casefold()
    )
