from __future__ import annotations

from abc import ABC, abstractmethod

from src.detection.models import DetectionResult
from src.streetview.models import CanonicalImageAsset


class WallDetector(ABC):
    """
    Provider/model-neutral wall and facade detector.

    The detector consumes a CanonicalImageAsset and returns a stable
    DetectionResult contract.

    Framework-specific inference objects must remain inside concrete
    detector implementations.
    """

    name: str
    version: str

    @abstractmethod
    def detect(
        self,
        asset: CanonicalImageAsset,
    ) -> DetectionResult:
        """
        Detect candidate wall/facade surfaces in a canonical image.

        Implementations should return:
        - READY when inference completed successfully.
        - NO_CANDIDATES when inference completed but no candidate
          surfaces were detected.
        - INVALID_INPUT when the canonical asset cannot be processed.
        - ERROR when inference could not be completed.
        """
        raise NotImplementedError
