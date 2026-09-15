from __future__ import annotations

from src.detection.base import WallDetector
from src.detection.models import DetectionResult
from src.detection.status import DETECTION_INVALID_INPUT
from src.streetview.models import CanonicalImageAsset


class DetectionService:
    """
    Orchestrates wall/facade detection against canonical imagery.

    The service deliberately knows nothing about the underlying ML
    framework. Concrete detector implementations are injected through
    WallDetector.
    """

    def __init__(
        self,
        detector: WallDetector,
    ) -> None:
        self.detector = detector

    def detect(
        self,
        asset: CanonicalImageAsset,
    ) -> DetectionResult:
        """
        Run detection for one canonical image asset.

        Only READY canonical assets are eligible for inference.
        Invalid canonical assets produce a structured result rather
        than reaching the detector.
        """

        if asset.status != "READY":
            return DetectionResult(
                asset_id=asset.asset_id,
                detector_name=self.detector.name,
                detector_version=self.detector.version,
                status=DETECTION_INVALID_INPUT,
                image_width=asset.width,
                image_height=asset.height,
                candidates=(),
                metadata={
                    "reason": "canonical_asset_not_ready",
                    "asset_status": asset.status,
                },
                error_type="InvalidInput",
                error_message=(
                    "Only canonical assets with status READY "
                    "can be sent to the detector."
                ),
            )

        return self.detector.detect(asset)
