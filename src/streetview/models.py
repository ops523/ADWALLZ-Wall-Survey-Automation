from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ImageryResult:
    provider: str
    status: str
    image_id: str | None
    latitude: float | None
    longitude: float | None
    capture_date: str | None
    heading: float | None
    image_url: str | None
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ImageryQuery:
    latitude: float
    longitude: float
    radius_m: int = 50
    heading: float | None = None


@dataclass(frozen=True)
class DiscoveryResult:
    latitude: float
    longitude: float
    provider: str
    status: str
    image_id: str | None
    image_latitude: float | None
    image_longitude: float | None
    capture_date: str | None
    heading: float | None
    image_url: str | None
    metadata: dict[str, Any]


@dataclass(frozen=True)
class SideImageryResult:
    """
    Imagery discovery result for one physical side of a survey point.

    The side is explicit so left/right imagery cannot be accidentally
    mixed during downstream wall detection.
    """

    point_id: str
    side: str
    latitude: float
    longitude: float
    requested_heading: float
    provider: str
    status: str
    image_id: str | None
    image_latitude: float | None
    image_longitude: float | None
    capture_date: str | None
    image_heading: float | None
    image_url: str | None
    metadata: dict[str, Any]
