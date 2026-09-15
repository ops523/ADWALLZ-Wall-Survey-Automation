from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BoundingBox:
    """
    Pixel-space bounding box.

    Coordinates follow the conventional image coordinate system:
    x increases from left to right.
    y increases from top to bottom.

    The box uses half-open style semantics conceptually:
    left <= x < right
    top <= y < bottom
    """

    left: float
    top: float
    right: float
    bottom: float

    def __post_init__(self) -> None:
        if self.left < 0:
            raise ValueError("left must be non-negative")

        if self.top < 0:
            raise ValueError("top must be non-negative")

        if self.right <= self.left:
            raise ValueError("right must be greater than left")

        if self.bottom <= self.top:
            raise ValueError("bottom must be greater than top")

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top

    @property
    def area(self) -> float:
        return self.width * self.height

    def as_dict(self) -> dict[str, float]:
        return {
            "left": self.left,
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
        }


@dataclass(frozen=True)
class DetectionCandidate:
    """
    A single candidate surface detected in an image.

    This represents a visual candidate only.

    It does NOT mean that the surface:
    - is commercially usable,
    - satisfies the minimum wall area,
    - is unobstructed,
    - is legal,
    - is approved,
    - or is suitable for execution.

    Those decisions belong to downstream stages.
    """

    class_name: str
    confidence: float
    bounding_box: BoundingBox

    class_id: int | None = None
    polygon: tuple[tuple[float, float], ...] | None = None

    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.class_name.strip():
            raise ValueError("class_name is required")

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                "confidence must be between 0 and 1"
            )

        if self.polygon is not None:
            if len(self.polygon) < 3:
                raise ValueError(
                    "polygon must contain at least 3 points"
                )

        if self.metadata is None:
            object.__setattr__(
                self,
                "metadata",
                {},
            )


@dataclass(frozen=True)
class DetectionResult:
    """
    Complete detector output for one canonical image asset.

    Detector implementations should return this contract rather than
    exposing framework-specific result objects to downstream code.
    """

    asset_id: str

    detector_name: str
    detector_version: str

    status: str

    image_width: int | None
    image_height: int | None

    candidates: tuple[DetectionCandidate, ...]

    metadata: dict[str, Any]

    error_type: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if not self.asset_id.strip():
            raise ValueError("asset_id is required")

        if not self.detector_name.strip():
            raise ValueError("detector_name is required")

        if not self.detector_version.strip():
            raise ValueError("detector_version is required")

        if not self.status.strip():
            raise ValueError("status is required")

        if self.image_width is not None:
            if self.image_width <= 0:
                raise ValueError(
                    "image_width must be positive"
                )

        if self.image_height is not None:
            if self.image_height <= 0:
                raise ValueError(
                    "image_height must be positive"
                )

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)

    @property
    def has_candidates(self) -> bool:
        return bool(self.candidates)
