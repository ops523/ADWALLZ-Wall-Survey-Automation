from __future__ import annotations

from src.detection.models import BoundingBox, DetectionCandidate
from src.detection.wall_surface import WallSurfaceModelConfig
from src.detection.wall_surface_adapter import WallSurfaceOutputAdapter


class FakeWallSurfaceAdapter(WallSurfaceOutputAdapter):
    name = "fake-wall-surface"
    version = "1.0"

    def build_input(self, asset):
        return {"asset_id": asset.asset_id}

    def parse_output(self, raw_output, asset):
        return tuple(raw_output)


def candidate(
    class_name: str,
    confidence: float,
) -> DetectionCandidate:
    return DetectionCandidate(
        class_name=class_name,
        confidence=confidence,
        bounding_box=BoundingBox(
            left=10,
            top=10,
            right=100,
            bottom=100,
        ),
    )


def test_adapter_default_config() -> None:
    adapter = FakeWallSurfaceAdapter()

    assert adapter.config.class_name == "wall_surface"
    assert adapter.config.prefer_polygon is True


def test_adapter_filters_wrong_class() -> None:
    adapter = FakeWallSurfaceAdapter()

    candidates = (
        candidate("wall_surface", 0.90),
        candidate("building", 0.99),
    )

    result = adapter.filter_candidates(candidates)

    assert len(result) == 1
    assert result[0].class_name == "wall_surface"


def test_adapter_filters_low_confidence() -> None:
    adapter = FakeWallSurfaceAdapter(
        WallSurfaceModelConfig(
            confidence_threshold=0.50,
        )
    )

    candidates = (
        candidate("wall_surface", 0.49),
        candidate("wall_surface", 0.80),
    )

    result = adapter.filter_candidates(candidates)

    assert len(result) == 1
    assert result[0].confidence == 0.80


def test_adapter_keeps_valid_wall_candidates() -> None:
    adapter = FakeWallSurfaceAdapter()

    candidates = (
        candidate("wall_surface", 0.90),
        candidate("wall_surface", 0.70),
    )

    result = adapter.filter_candidates(candidates)

    assert result == candidates
