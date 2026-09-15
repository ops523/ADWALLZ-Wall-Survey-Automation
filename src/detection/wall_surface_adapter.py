from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.detection.models import DetectionCandidate
from src.detection.wall_surface import WallSurfaceModelConfig
from src.streetview.models import CanonicalImageAsset


class WallSurfaceOutputAdapter(ABC):
    """
    Model-specific translation boundary for wall-surface detection.

    Concrete implementations may consume YOLO, ONNX, TensorRT, OpenVINO,
    Detectron2, or another inference output.

    The rest of ADWALLZ must never depend on the model's native output format.
    """

    name: str
    version: str

    def __init__(
        self,
        config: WallSurfaceModelConfig | None = None,
    ) -> None:
        self.config = config or WallSurfaceModelConfig()

    @abstractmethod
    def build_input(
        self,
        asset: CanonicalImageAsset,
    ) -> Any:
        """
        Convert a canonical image asset into model input.

        The implementation owns:
        - resize
        - letterboxing
        - normalization
        - channel ordering
        - tensor conversion
        """
        raise NotImplementedError

    @abstractmethod
    def parse_output(
        self,
        raw_output: list[Any],
        asset: CanonicalImageAsset,
    ) -> tuple[DetectionCandidate, ...]:
        """
        Convert native model output into DetectionCandidate objects.

        Returned candidates must use image-space coordinates corresponding
        to the canonical image dimensions.

        If the model provides segmentation masks, polygon geometry should
        be retained.
        """
        raise NotImplementedError

    def filter_candidates(
        self,
        candidates: tuple[DetectionCandidate, ...],
    ) -> tuple[DetectionCandidate, ...]:
        """
        Apply only detector-level confidence/class filtering.

        Commercial suitability decisions are intentionally excluded.
        """

        return tuple(
            candidate
            for candidate in candidates
            if candidate.confidence
            >= self.config.confidence_threshold
            and candidate.class_name.strip().casefold()
            == self.config.class_name.casefold()
        )
