from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.streetview.cache import ImageryCache
from src.streetview.headings import normalize_heading
from src.streetview.models import (
    DiscoveryResult,
    ImageryQuery,
    SideImageryResult,
)
from src.streetview.providers.base import StreetImageryProvider


@dataclass(frozen=True)
class ProviderAttempt:
    """
    Record of one provider attempt during discovery.
    """

    provider: str
    status: str
    error_type: str | None = None
    error_message: str | None = None


class ImageryDiscovery:
    """
    Provider-neutral street imagery discovery orchestrator.

    Providers are attempted in the order supplied to the constructor.

    Fallback rules:
    - AVAILABLE -> return immediately.
    - NOT_AVAILABLE -> continue to next provider.
    - ERROR -> continue to next provider.
    - Provider exception -> record ERROR and continue.
    - No provider succeeds -> NOT_AVAILABLE.

    The caller never needs to know how an image was obtained.
    Provider provenance remains available in DiscoveryResult.metadata.
    """

    def __init__(
        self,
        providers: list[StreetImageryProvider],
        cache: ImageryCache | None = None,
    ) -> None:
        if not providers:
            raise ValueError(
                "At least one imagery provider is required."
            )

        self.providers = providers
        self.cache = cache

    def discover(
        self,
        latitude: float,
        longitude: float,
        radius_m: int = 50,
        heading: float | None = None,
    ) -> DiscoveryResult:
        requested_heading = (
            normalize_heading(heading)
            if heading is not None
            else None
        )

        query = ImageryQuery(
            latitude=latitude,
            longitude=longitude,
            radius_m=radius_m,
            heading=requested_heading,
        )

        if self.cache is not None:
            cached = self.cache.get(
                provider="discovery",
                latitude=latitude,
                longitude=longitude,
                radius_m=radius_m,
                heading=requested_heading,
            )

            if cached is not None:
                return self._result_from_cache(
                    latitude=latitude,
                    longitude=longitude,
                    cached=cached,
                )

        attempts: list[ProviderAttempt] = []

        for provider in self.providers:
            try:
                result = provider.find_nearby(query)

            except Exception as exc:
                attempts.append(
                    ProviderAttempt(
                        provider=provider.name,
                        status="ERROR",
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                    )
                )
                continue

            attempts.append(
                ProviderAttempt(
                    provider=provider.name,
                    status=result.status,
                )
            )

            if result.status == "AVAILABLE":
                discovery_result = DiscoveryResult(
                    latitude=latitude,
                    longitude=longitude,
                    provider=result.provider,
                    status=result.status,
                    image_id=result.image_id,
                    image_latitude=result.latitude,
                    image_longitude=result.longitude,
                    capture_date=result.capture_date,
                    heading=result.heading,
                    image_url=result.image_url,
                    metadata={
                        **result.metadata,
                        "requested_heading": requested_heading,
                        "attempts": self._attempts_metadata(
                            attempts
                        ),
                    },
                )

                self._save_cache(
                    latitude=latitude,
                    longitude=longitude,
                    radius_m=radius_m,
                    heading=requested_heading,
                    result=discovery_result,
                )

                return discovery_result

        discovery_result = DiscoveryResult(
            latitude=latitude,
            longitude=longitude,
            provider="none",
            status="NOT_AVAILABLE",
            image_id=None,
            image_latitude=None,
            image_longitude=None,
            capture_date=None,
            heading=None,
            image_url=None,
            metadata={
                "requested_heading": requested_heading,
                "attempts": self._attempts_metadata(
                    attempts
                ),
            },
        )

        self._save_cache(
            latitude=latitude,
            longitude=longitude,
            radius_m=radius_m,
            heading=requested_heading,
            result=discovery_result,
        )

        return discovery_result

    def discover_side(
        self,
        point_id: str,
        latitude: float,
        longitude: float,
        side: str,
        heading: float,
        radius_m: int = 50,
    ) -> SideImageryResult:
        normalized_side = side.strip().casefold()

        if normalized_side not in {"left", "right"}:
            raise ValueError(
                "side must be either 'left' or 'right'."
            )

        requested_heading = normalize_heading(heading)

        result = self.discover(
            latitude=latitude,
            longitude=longitude,
            radius_m=radius_m,
            heading=requested_heading,
        )

        return SideImageryResult(
            point_id=point_id,
            side=normalized_side,
            latitude=latitude,
            longitude=longitude,
            requested_heading=requested_heading,
            provider=result.provider,
            status=result.status,
            image_id=result.image_id,
            image_latitude=result.image_latitude,
            image_longitude=result.image_longitude,
            capture_date=result.capture_date,
            image_heading=result.heading,
            image_url=result.image_url,
            metadata=result.metadata,
        )

    def discover_both_sides(
        self,
        point_id: str,
        latitude: float,
        longitude: float,
        heading_left: float,
        heading_right: float,
        radius_m: int = 50,
    ) -> tuple[SideImageryResult, SideImageryResult]:
        left = self.discover_side(
            point_id=point_id,
            latitude=latitude,
            longitude=longitude,
            side="left",
            heading=heading_left,
            radius_m=radius_m,
        )

        right = self.discover_side(
            point_id=point_id,
            latitude=latitude,
            longitude=longitude,
            side="right",
            heading=heading_right,
            radius_m=radius_m,
        )

        return left, right

    def _save_cache(
        self,
        latitude: float,
        longitude: float,
        radius_m: int,
        heading: float | None,
        result: DiscoveryResult,
    ) -> None:
        if self.cache is None:
            return

        self.cache.set(
            provider="discovery",
            latitude=latitude,
            longitude=longitude,
            radius_m=radius_m,
            heading=heading,
            value={
                "latitude": result.latitude,
                "longitude": result.longitude,
                "provider": result.provider,
                "status": result.status,
                "image_id": result.image_id,
                "image_latitude": result.image_latitude,
                "image_longitude": result.image_longitude,
                "capture_date": result.capture_date,
                "heading": result.heading,
                "image_url": result.image_url,
                "metadata": result.metadata,
            },
        )

    @staticmethod
    def _attempts_metadata(
        attempts: list[ProviderAttempt],
    ) -> list[dict[str, Any]]:
        return [
            {
                "provider": attempt.provider,
                "status": attempt.status,
                **(
                    {
                        "error_type": attempt.error_type,
                        "error_message": attempt.error_message,
                    }
                    if attempt.error_type is not None
                    else {}
                ),
            }
            for attempt in attempts
        ]

    @staticmethod
    def _result_from_cache(
        latitude: float,
        longitude: float,
        cached: dict[str, Any],
    ) -> DiscoveryResult:
        return DiscoveryResult(
            latitude=latitude,
            longitude=longitude,
            provider=str(
                cached.get(
                    "provider",
                    "none",
                )
            ),
            status=str(
                cached.get(
                    "status",
                    "NOT_AVAILABLE",
                )
            ),
            image_id=cached.get("image_id"),
            image_latitude=cached.get(
                "image_latitude"
            ),
            image_longitude=cached.get(
                "image_longitude"
            ),
            capture_date=cached.get(
                "capture_date"
            ),
            heading=cached.get("heading"),
            image_url=cached.get("image_url"),
            metadata={
                **(
                    cached.get("metadata")
                    or {}
                ),
                "cache_hit": True,
            },
        )
