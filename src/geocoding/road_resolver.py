from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.geocoding.boundary import haversine_km
from src.geocoding.nominatim import NominatimClient
from src.models.target import SurveyTarget
from src.osm.client import OverpassClient
from src.osm.roads import (
    elements_to_lines,
    normalize_reference,
    normalize_road_text,
)


@dataclass(frozen=True)
class RoadCandidate:
    osm_type: str
    osm_id: int
    latitude: float
    longitude: float
    display_name: str
    name: str
    reference: str | None
    address: dict[str, str]
    score: int


@dataclass(frozen=True)
class ResolvedRoad:
    requested_name: str
    osm_way_ids: tuple[int, ...]
    roads: tuple[dict[str, Any], ...]
    method: str
    confidence: str
    distance_km: float
    matched_name: str
    matched_reference: str | None


class RoadResolver:
    """
    Resolve an operator-supplied road independently of the local
    place-search bounding box.

    Resolution order:

        local OSM matching
            ↓
        Nominatim road search
            ↓
        exact OSM way retrieval
            ↓
        road identity validation
            ↓
        distance/confidence classification

    A distant road is never silently accepted.
    """

    ROAD_SEARCH_LIMIT = 10

    def __init__(
        self,
        geocoder: NominatimClient | None = None,
        osm_client: OverpassClient | None = None,
        road_search_radius_km: float = 20.0,
        confident_radius_km: float = 10.0,
    ) -> None:
        if road_search_radius_km <= 0:
            raise ValueError(
                "road_search_radius_km must be greater than zero."
            )

        if confident_radius_km <= 0:
            raise ValueError(
                "confident_radius_km must be greater than zero."
            )

        if confident_radius_km > road_search_radius_km:
            raise ValueError(
                "confident_radius_km cannot exceed "
                "road_search_radius_km."
            )

        self.geocoder = geocoder or NominatimClient()
        self.osm_client = osm_client or OverpassClient()

        self.road_search_radius_km = float(
            road_search_radius_km
        )

        self.confident_radius_km = float(
            confident_radius_km
        )

    def resolve(
        self,
        target: SurveyTarget,
        requested_road: str,
        origin_latitude: float,
        origin_longitude: float,
    ) -> ResolvedRoad | None:
        requested_road = requested_road.strip()

        if not requested_road:
            raise ValueError(
                "requested_road must not be empty."
            )

        results = self._search_nominatim(
            target=target,
            requested_road=requested_road,
        )

        candidates = self._build_candidates(
            results=results,
            target=target,
            requested_road=requested_road,
        )

        if not candidates:
            return None

        candidates.sort(
            key=lambda candidate: (
                -candidate.score,
                candidate.osm_id,
            )
        )

        # Only candidates inside the configured road-search radius
        # can become a valid resolution.
        nearby_candidates = [
            candidate
            for candidate in candidates
            if haversine_km(
                origin_latitude,
                origin_longitude,
                candidate.latitude,
                candidate.longitude,
            ) <= self.road_search_radius_km
        ]

        if not nearby_candidates:
            # We deliberately return an unresolved result with the
            # nearest candidate distance so the CLI can explain why.
            nearest = min(
                candidates,
                key=lambda candidate: haversine_km(
                    origin_latitude,
                    origin_longitude,
                    candidate.latitude,
                    candidate.longitude,
                ),
            )

            distance_km = haversine_km(
                origin_latitude,
                origin_longitude,
                nearest.latitude,
                nearest.longitude,
            )

            return ResolvedRoad(
                requested_name=requested_road,
                osm_way_ids=(),
                roads=(),
                method="NOMINATIM_ROAD",
                confidence="UNRESOLVED",
                distance_km=distance_km,
                matched_name=nearest.name,
                matched_reference=nearest.reference,
            )

        selected = nearby_candidates[0]

        distance_km = haversine_km(
            origin_latitude,
            origin_longitude,
            selected.latitude,
            selected.longitude,
        )

        if distance_km <= self.confident_radius_km:
            confidence = "CONFIDENT"
        else:
            confidence = "REVIEW_REQUIRED"

        way_ids = [
            candidate.osm_id
            for candidate in nearby_candidates[:10]
        ]

        roads = self._retrieve_ways(
            way_ids
        )

        roads = self._validate_roads(
            roads=roads,
            requested_road=requested_road,
        )

        if not roads:
            return ResolvedRoad(
                requested_name=requested_road,
                osm_way_ids=(),
                roads=(),
                method="NOMINATIM_ROAD",
                confidence="UNRESOLVED",
                distance_km=distance_km,
                matched_name=selected.name,
                matched_reference=selected.reference,
            )

        return ResolvedRoad(
            requested_name=requested_road,
            osm_way_ids=tuple(
                int(road["osm_way_id"])
                for road in roads
            ),
            roads=tuple(roads),
            method="NOMINATIM_ROAD",
            confidence=confidence,
            distance_km=distance_km,
            matched_name=selected.name,
            matched_reference=selected.reference,
        )

    def _search_nominatim(
        self,
        target: SurveyTarget,
        requested_road: str,
    ) -> list[dict]:
        query = (
            f"{requested_road}, "
            f"{target.place_name}, "
            f"{target.district}, "
            f"{target.state}, "
            f"{target.pincode}, India"
        )

        params = {
            "q": query,
            "format": "jsonv2",
            "addressdetails": 1,
            "namedetails": 1,
            "limit": self.ROAD_SEARCH_LIMIT,
            "countrycodes": "in",
            "dedupe": 1,
        }

        response = self.geocoder.session.get(
            self.geocoder.url,
            params=params,
            headers={
                "User-Agent": self.geocoder.user_agent,
            },
            timeout=60,
        )

        response.raise_for_status()

        payload = response.json()

        if not isinstance(payload, list):
            return []

        return payload

    @staticmethod
    def _build_candidates(
        results: list[dict],
        target: SurveyTarget,
        requested_road: str,
    ) -> list[RoadCandidate]:
        candidates: list[RoadCandidate] = []

        requested_norm = normalize_road_text(
            requested_road
        )

        for result in results:
            if str(
                result.get("osm_type") or ""
            ).casefold() != "way":
                continue

            try:
                osm_id = int(result["osm_id"])
                latitude = float(result["lat"])
                longitude = float(result["lon"])
            except (
                KeyError,
                TypeError,
                ValueError,
            ):
                continue

            address = {
                str(key): str(value)
                for key, value in (
                    result.get("address") or {}
                ).items()
            }

            namedetails = (
                result.get("namedetails") or {}
            )

            name = str(
                namedetails.get("name")
                or address.get("road")
                or ""
            )

            reference = (
                namedetails.get("ref")
                or address.get("ref")
                or None
            )

            display_name = str(
                result.get("display_name") or ""
            )

            normalized_name = normalize_road_text(
                name
            )

            normalized_display = normalize_road_text(
                display_name
            )

            normalized_reference = (
                normalize_reference(reference)
                if reference
                else ""
            )

            if not (
                requested_norm == normalized_name
                or requested_norm in normalized_name
                or requested_norm in normalized_display
                or requested_norm == normalized_reference
            ):
                continue

            score = 0

            postcode = str(
                address.get("postcode") or ""
            ).strip()

            if postcode == target.pincode:
                score += 100

            state = str(
                address.get("state") or ""
            ).casefold()

            if (
                target.state.casefold().strip()
                in state
            ):
                score += 30

            district_text = " ".join(
                str(value or "").casefold()
                for value in (
                    address.get("state_district"),
                    address.get("district"),
                    address.get("county"),
                )
            )

            if (
                target.district.casefold().strip()
                in district_text
            ):
                score += 30

            if normalized_name == requested_norm:
                score += 100
            elif requested_norm in normalized_name:
                score += 70
            elif requested_norm in normalized_display:
                score += 50
            elif requested_norm == normalized_reference:
                score += 100

            candidates.append(
                RoadCandidate(
                    osm_type="way",
                    osm_id=osm_id,
                    latitude=latitude,
                    longitude=longitude,
                    display_name=display_name,
                    name=name,
                    reference=reference,
                    address=address,
                    score=score,
                )
            )

        return candidates

    def _retrieve_ways(
        self,
        way_ids: list[int],
    ) -> list[dict[str, Any]]:
        if not way_ids:
            return []

        unique_ids = sorted(
            set(way_ids)
        )

        query = f"""
[out:json][timeout:180];
way(id:{",".join(map(str, unique_ids))});
out tags geom;
"""

        payload = self.osm_client.query(
            query
        )

        return elements_to_lines(
            payload.get("elements", [])
        )

    @staticmethod
    def _validate_roads(
        roads: list[dict[str, Any]],
        requested_road: str,
    ) -> list[dict[str, Any]]:
        requested_norm = normalize_road_text(
            requested_road
        )

        validated = []

        for road in roads:
            tags = road.get("tags") or {}

            names = [
                tags.get("name"),
                tags.get("official_name"),
                tags.get("alt_name"),
                tags.get("short_name"),
                tags.get("loc_name"),
            ]

            references = [
                tags.get("ref"),
                tags.get("old_ref"),
                tags.get("nat_ref"),
                tags.get("reg_ref"),
                tags.get("route_ref"),
            ]

            name_match = any(
                requested_norm
                == normalize_road_text(value)
                for value in names
                if value
            )

            reference_match = any(
                requested_norm
                == normalize_reference(value)
                for value in references
                if value
            )

            if name_match or reference_match:
                validated.append(road)

        return validated


def print_resolution_result(
    result: ResolvedRoad | None,
) -> None:
    print()
    print("Targeted road resolver:")

    if result is None:
        print("  Status     : UNRESOLVED")
        print(
            "  Reason     : "
            "No validated Nominatim road candidate."
        )
        return

    print(
        f"  Requested  : {result.requested_name}"
    )

    print(
        f"  Method     : {result.method}"
    )

    print(
        f"  Confidence : {result.confidence}"
    )

    print(
        f"  Distance   : "
        f"{result.distance_km:.2f} km"
    )

    print(
        f"  OSM name   : "
        f"{result.matched_name or '-'}"
    )

    print(
        f"  OSM ref    : "
        f"{result.matched_reference or '-'}"
    )

    print(
        "  Way IDs    : "
        + (
            ", ".join(
                str(value)
                for value in result.osm_way_ids
            )
            if result.osm_way_ids
            else "-"
        )
    )
