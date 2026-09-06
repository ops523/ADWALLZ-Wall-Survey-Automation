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
