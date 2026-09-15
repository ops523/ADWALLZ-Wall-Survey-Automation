from __future__ import annotations

from src.detection.base import WallDetector
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


class FakeWallDetector(WallDetector):
    """
    Deterministic detector used for contract and pipeline tests.

    This is deliberately not a real CV model.
    """

    name = "fake-wall-detector"
    version = "1.0"

    def __init__(
        self,
        candidates: tuple[DetectionCandidate, ...] = (),
    ) -> None:
        self._candidates = candidates

    def detect(
        self,
        asset: CanonicalImageAsset,
    ) -> DetectionResult:
        status = (
            DETECTION_READY
            if self._candidates
            else DETECTION_NO_CANDIDATES
        )

        return DetectionResult(
            asset_id=asset.asset_id,
            detector_name=self.name,
            detector_version=self.version,
            status=status,
            image_width=asset.width,
            image_height=asset.height,
            candidates=self._candidates,
            metadata={
                "source_provider": asset.provider,
                "source_image_id": asset.image_id,
            },
        )


def sample_wall_candidate() -> DetectionCandidate:
    return DetectionCandidate(
        class_name="wall_surface",
        confidence=0.95,
        bounding_box=BoundingBox(
            left=100.0,
            top=80.0,
            right=900.0,
            bottom=500.0,
        ),
    )
