from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

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

    # Pack 1A-E:
    # These fields make partial resolution explicit without
    # breaking existing callers that construct ResolvedRoad
    # positionally.
    expansion_status: str = "NOT_ATTEMPTED"
    expansion_error: str | None = None


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

    Pack 1A-E additionally makes Overpass failures resilient:

        Seed retrieval failure
            → UNRESOLVED

        Expansion failure
            → retain validated seed roads
            → mark expansion as FAILED

    This means a transient Overpass outage cannot invalidate an
    already-validated road identity, while also preventing survey
    point generation when no road geometry was successfully
    retrieved.
    """

    ROAD_SEARCH_LIMIT = 10

    DEFAULT_EXPANSION_DEPTH = 3

    # Number of attempts for an Overpass operation.
    OVERPASS_RETRIES = 2

    # Maximum number of ways retrieved in one Overpass request.
    # Smaller requests are less likely to trigger gateway limits.
    OVERPASS_BATCH_SIZE = 25

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
                expansion_status="NOT_ATTEMPTED",
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

        # ---------------------------------------------------------
        # Pack 1A-E: seed retrieval is mandatory.
        #
        # Without road geometry we cannot safely generate survey
        # points. A transient Overpass failure therefore results in
        # an explicit UNRESOLVED result rather than an exception.
        # ---------------------------------------------------------
        try:
            seed_roads = self._retrieve_ways(
                seed_way_ids
            )
        except requests.RequestException as exc:
            return ResolvedRoad(
                requested_name=requested_road,
                osm_way_ids=(),
                roads=(),
                method="NOMINATIM_ROAD_OVERPASS_UNAVAILABLE",
                confidence="UNRESOLVED",
                distance_km=distance_km,
                matched_name=selected.name,
                matched_reference=selected.reference,
                expansion_status="NOT_ATTEMPTED",
                expansion_error=str(exc),
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
                expansion_status="NOT_ATTEMPTED",
            )

        # ---------------------------------------------------------
        # Pack 1A-E:
        #
        # Expansion is best-effort. A failure here must NOT discard
        # already validated seed roads.
        # ---------------------------------------------------------
        expansion_status = "NOT_ATTEMPTED"
        expansion_error: str | None = None

        if self.expansion_depth > 0:
            try:
                expanded_roads = self._expand_connected_roads(
                    seed_roads=seed_roads,
                    requested_road=requested_road,
                )

                if expanded_roads:
                    expansion_status = "SUCCESS"
                else:
                    # The seed roads remain valid even if expansion
                    # simply finds nothing additional.
                    expanded_roads = seed_roads
                    expansion_status = "NO_ADDITIONAL_ROADS"

            except requests.RequestException as exc:
                # Critical safety rule:
                #
                # We DO NOT replace the road.
                # We DO NOT retry with another nearby road.
                # We retain only the already validated seed roads.
                expanded_roads = seed_roads
                expansion_status = "FAILED"
                expansion_error = str(exc)

        else:
            expanded_roads = seed_roads
            expansion_status = "DISABLED"

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
            method=(
                "NOMINATIM_ROAD_CONNECTED"
                if expansion_status == "SUCCESS"
                else "NOMINATIM_ROAD_SEED"
            ),
            confidence=confidence,
            distance_km=distance_km,
            matched_name=selected.name,
            matched_reference=selected.reference,
            expansion_status=expansion_status,
            expansion_error=expansion_error,
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
        """
        Retrieve OSM way geometry in small batches.

        Pack 1A-E deliberately avoids sending a large list of ways
        through one public Overpass request. Each batch is retried,
        reducing the probability that a transient gateway failure
        destroys an otherwise valid road resolution.
        """

        if not way_ids:
            return []

        unique_ids = sorted(
            set(way_ids)
        )

        roads: list[dict[str, Any]] = []

        for start in range(
            0,
            len(unique_ids),
            self.OVERPASS_BATCH_SIZE,
        ):
            batch = unique_ids[
                start:start + self.OVERPASS_BATCH_SIZE
            ]

            query = f"""
[out:json][timeout:180];
way(id:{",".join(map(str, batch))});
out tags geom;
"""

            payload = self._query_overpass_with_retry(
                query
            )

            batch_roads = elements_to_lines(
                payload.get("elements", [])
            )

            roads.extend(batch_roads)

        return roads

    def _query_overpass_with_retry(
        self,
        query: str,
    ) -> dict:
        """
        Execute an Overpass query with bounded retries.

        The original exception is re-raised after all attempts so
        the caller can distinguish infrastructure failure from
        an empty/invalid OSM result.
        """

        last_error: requests.RequestException | None = None

        for _ in range(self.OVERPASS_RETRIES):
            try:
                return self.osm_client.query(
                    query
                )
            except requests.RequestException as exc:
                last_error = exc

        if last_error is not None:
            raise last_error

        raise RuntimeError(
            "Overpass query failed without an exception."
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

        Overpass errors are deliberately allowed to propagate to
        resolve(), where Pack 1A-E converts them into a partial
        seed-only resolution.
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

        payload = self._query_overpass_with_retry(
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

    expansion_status = getattr(
        result,
        "expansion_status",
        "NOT_REPORTED",
    )

    expansion_error = getattr(
        result,
        "expansion_error",
        None,
    )

    print(
        f"  Expansion  : "
        f"{expansion_status}"
    )

    if expansion_error:
        print(
            f"  Exp. error : "
            f"{expansion_error}"
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