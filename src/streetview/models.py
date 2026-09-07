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


@dataclass(frozen=True)
class CanonicalImageAsset:
    """
    Canonical, locally processed imagery asset.

    This is the stable image contract consumed by downstream AI stages.

    Provider-specific response data remains metadata/provenance; the
    canonical asset itself has deterministic format, dimensions and hash.
    """

    asset_id: str
    status: str

    image_path: str | None

    width: int | None
    height: int | None
    format: str | None
    file_size_bytes: int | None
    sha256: str | None

    provider: str
    image_id: str | None

    source_latitude: float
    source_longitude: float

    image_latitude: float | None
    image_longitude: float | None

    requested_heading: float | None
    actual_heading: float | None

    side: str | None
    capture_date: str | None

    metadata: dict[str, Any]

    error_type: str | None = None
    error_message: str | None = None
