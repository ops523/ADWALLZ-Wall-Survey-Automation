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

    Resolution:

        Nominatim road search
            ↓
        exact OSM way retrieval
            ↓
        seed-way identity validation
            ↓
        connected OSM way expansion
            ↓
        expanded road identity validation
            ↓
        distance/confidence classification

    A different road is never silently substituted.
    """

    ROAD_SEARCH_LIMIT = 10

    # Maximum number of expansion iterations from the seed ways.
    # This prevents an incorrectly mapped road from consuming an
    # uncontrolled portion of the OSM network.
    DEFAULT_EXPANSION_DEPTH = 3

    def __init__(
        self,
        geocoder: NominatimClient | None = None,
        osm_client: OverpassClient | None = None,
        road_search_radius_km: float = 20.0,
        confident_radius_km: float = 10.0,
        expansion_depth: int = DEFAULT_EXPANSION_DEPTH,
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

        if expansion_depth < 0:
            raise ValueError(
                "expansion_depth cannot be negative."
            )

        self.geocoder = geocoder or NominatimClient()
        self.osm_client = osm_client or OverpassClient()

        self.road_search_radius_km = float(
            road_search_radius_km
        )

        self.confident_radius_km = float(
            confident_radius_km
        )

        self.expansion_depth = int(
            expansion_depth
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

        confidence = (
            "CONFIDENT"
            if distance_km <= self.confident_radius_km
            else "REVIEW_REQUIRED"
        )

        seed_way_ids = [
            candidate.osm_id
            for candidate in nearby_candidates[:10]
        ]

        seed_roads = self._retrieve_ways(
            seed_way_ids
        )

        seed_roads = self._validate_roads(
            roads=seed_roads,
            requested_road=requested_road,
        )

        if not seed_roads:
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

        expanded_roads = self._expand_connected_roads(
            seed_roads=seed_roads,
            requested_road=requested_road,
        )

        if not expanded_roads:
            expanded_roads = seed_roads

        return ResolvedRoad(
            requested_name=requested_road,
            osm_way_ids=tuple(
                sorted(
                    {
                        int(road["osm_way_id"])
                        for road in expanded_roads
                    }
                )
            ),
            roads=tuple(
                expanded_roads
            ),
            method="NOMINATIM_ROAD_CONNECTED",
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

            if target.state.casefold().strip() in state:
                score += 30

            district_text = " ".join(
                str(value or "").casefold()
                for value in (
                    address.get("state_district"),
                    address.get("district"),
                    address.get("county"),
                )
            )

            if target.district.casefold().strip() in district_text:
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

    def _expand_connected_roads(
        self,
        seed_roads: list[dict[str, Any]],
        requested_road: str,
    ) -> list[dict[str, Any]]:
        """
        Expand validated seed ways through connected OSM ways.

        Expansion is intentionally conservative:

        1. Find ways sharing nodes with the current frontier.
        2. Retrieve their tags and geometry.
        3. Accept only ways whose road identity matches the
           requested road exactly.
        4. Repeat for a bounded number of iterations.

        A touching but differently named/referenced road is rejected.
        """

        if not seed_roads:
            return []

        accepted: dict[int, dict[str, Any]] = {
            int(road["osm_way_id"]): road
            for road in seed_roads
        }

        frontier = list(
            accepted.values()
        )

        for _ in range(self.expansion_depth):
            if not frontier:
                break

            frontier_ids = [
                int(road["osm_way_id"])
                for road in frontier
            ]

            candidate_ids = self._find_connected_way_ids(
                frontier_ids
            )

            candidate_ids -= set(
                accepted.keys()
            )

            if not candidate_ids:
                break

            candidate_roads = self._retrieve_ways(
                sorted(candidate_ids)
            )

            validated = self._validate_roads(
                roads=candidate_roads,
                requested_road=requested_road,
            )

            if not validated:
                break

            frontier = []

            for road in validated:
                way_id = int(
                    road["osm_way_id"]
                )

                if way_id in accepted:
                    continue

                accepted[way_id] = road
                frontier.append(road)

        return [
            accepted[way_id]
            for way_id in sorted(accepted)
        ]

    def _find_connected_way_ids(
        self,
        way_ids: list[int],
    ) -> set[int]:
        """
        Return OSM way IDs that share at least one node with
        the supplied seed/frontier ways.

        Overpass performs the node-to-way relationship lookup.
        """

        if not way_ids:
            return set()

        unique_ids = sorted(
            set(way_ids)
        )

        query = f"""
[out:json][timeout:180];

way(id:{",".join(map(str, unique_ids))})->.seed;

(
  way(bn.seed);
);

out ids;
"""

        payload = self.osm_client.query(
            query
        )

        elements = payload.get(
            "elements",
            []
        )

        result: set[int] = set()

        for element in elements:
            if element.get("type") != "way":
                continue

            try:
                result.add(
                    int(element["id"])
                )
            except (
                KeyError,
                TypeError,
                ValueError,
            ):
                continue

        return result

    @staticmethod
    def _validate_roads(
        roads: list[dict[str, Any]],
        requested_road: str,
    ) -> list[dict[str, Any]]:
        requested_norm = normalize_road_text(
            requested_road
        )

        requested_is_reference = (
            requested_norm.startswith("sh")
            or requested_norm.startswith("nh")
            or requested_norm.startswith("mdr")
            or requested_norm.startswith("mh")
            or requested_norm.startswith("rh")
            or requested_norm.startswith("sr")
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

            normalized_names = [
                normalize_road_text(value)
                for value in names
                if value
            ]

            normalized_references = [
                normalize_reference(value)
                for value in references
                if value
            ]

            if requested_is_reference:
                # For SH/NH/etc. requests, reference identity is
                # authoritative. A different reference must never
                # enter the corridor simply because its name matches.
                reference_match = (
                    requested_norm in normalized_references
                )

                if reference_match:
                    validated.append(road)

                continue

            # Named-road request.
            name_match = any(
                requested_norm == normalized_name
                for normalized_name in normalized_names
            )

            reference_match = any(
                requested_norm == normalized_reference
                for normalized_reference in normalized_references
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
