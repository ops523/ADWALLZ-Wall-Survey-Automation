from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from shapely.geometry import LineString


DEFAULT_ROAD_TYPES = (
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "unclassified",
    "residential",
)


REFERENCE_FIELDS = (
    "ref",
    "old_ref",
    "nat_ref",
    "reg_ref",
    "route_ref",
)

NAME_FIELDS = (
    "name",
    "official_name",
    "alt_name",
    "short_name",
    "loc_name",
)


@dataclass(frozen=True)
class RoadMatch:
    """An OSM road way matched against an operator-supplied road."""

    road: dict[str, Any]
    score: int
    matched_field: str
    matched_value: str


def normalize_road_text(value: str | None) -> str:
    """
    Normalize a human road name/reference.

    Examples:

        State Highway 57 -> sh57
        state highway 57 -> sh57
        SH-57            -> sh57
        SH 57            -> sh57
        NH 167K          -> nh167k
    """

    if not value:
        return ""

    text = value.casefold().strip()

    text = (
        text
        .replace("–", "-")
        .replace("—", "-")
    )

    replacements = {
        "state highway": "sh",
        "national highway": "nh",
        "district road": "mdr",
        "highway": "",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"[^a-z0-9]+", "", text)

    return text


def normalize_reference(value: str | None) -> str:
    """
    Normalize an OSM route reference.

    References are intentionally treated as exact identifiers.

    SH-57 -> sh57
    SH 57 -> sh57
    SH57  -> sh57
    """

    return normalize_road_text(value)


def is_reference_request(value: str) -> bool:
    """
    Determine whether an operator request represents a route reference.

    Examples:

        SH57
        SH-57
        SH 57
        State Highway 57
        NH167
        National Highway 167

    return True.
    """

    normalized = normalize_reference(value)

    return bool(
        re.fullmatch(
            r"(sh|nh|mdr|mh|rh|sr)[a-z0-9]+",
            normalized,
        )
    )


def road_match_score(
    requested: str,
    tags: dict[str, Any],
) -> tuple[int, str, str] | None:
    """
    Score one OSM way against an operator-supplied road.

    Critical rule:

    Route references are matched EXACTLY.

    We never allow:

        SH5 -> SH57

    merely because one normalized string is contained inside another.

    Road names can use controlled exact/substring matching.
    """

    requested_norm = normalize_road_text(requested)

    if not requested_norm:
        return None

    # ---------------------------------------------------------
    # Route/reference matching
    # ---------------------------------------------------------

    if is_reference_request(requested):

        for field in REFERENCE_FIELDS:

            raw_value = tags.get(field)

            if not raw_value:
                continue

            for value in str(raw_value).split(";"):

                value = value.strip()

                if not value:
                    continue

                value_norm = normalize_reference(value)

                if value_norm == requested_norm:
                    return (
                        100,
                        field,
                        value,
                    )

        # A reference request must not fall through to substring
        # matching against another reference.
        return None

    # ---------------------------------------------------------
    # Road-name matching
    # ---------------------------------------------------------

    fields = (
        ("name", tags.get("name"), 95),
        ("official_name", tags.get("official_name"), 90),
        ("alt_name", tags.get("alt_name"), 85),
        ("short_name", tags.get("short_name"), 85),
        ("loc_name", tags.get("loc_name"), 80),
    )

    best: tuple[int, str, str] | None = None

    for field, raw_value, base_score in fields:

        if not raw_value:
            continue

        for value in str(raw_value).split(";"):

            value = value.strip()

            if not value:
                continue

            value_norm = normalize_road_text(value)

            if not value_norm:
                continue

            if value_norm == requested_norm:

                score = base_score

            elif (
                requested_norm in value_norm
                or value_norm in requested_norm
            ):

                score = base_score - 20

            else:
                continue

            candidate = (
                score,
                field,
                value,
            )

            if best is None or candidate[0] > best[0]:
                best = candidate

    return best


def build_road_query(
    *,
    bbox: tuple[float, float, float, float],
    road_name: str | None = None,
    road_types: tuple[str, ...] = DEFAULT_ROAD_TYPES,
) -> str:
    """
    Build a geographic Overpass query.

    Road matching is performed locally after retrieving the
    geographic road network.
    """

    south, north, west, east = bbox

    highway_regex = "|".join(
        re.escape(value)
        for value in road_types
    )

    return f"""
[out:json][timeout:180];

way
  ["highway"~"^({highway_regex})$"]
  ({south},{west},{north},{east});

out tags geom;
"""


def elements_to_lines(
    elements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert Overpass highway ways into Shapely LineStrings."""

    roads: list[dict[str, Any]] = []

    for element in elements:

        geometry = element.get("geometry") or []

        coordinates = [
            (
                point["lon"],
                point["lat"],
            )
            for point in geometry
            if "lon" in point and "lat" in point
        ]

        if len(coordinates) < 2:
            continue

        tags = element.get("tags") or {}

        roads.append(
            {
                "osm_way_id": element.get("id"),
                "road_name": tags.get("name"),
                "road_ref": tags.get("ref"),
                "road_type": tags.get("highway"),
                "geometry": LineString(coordinates),
                "tags": tags,
            }
        )

    return roads


def find_road_matches(
    roads: list[dict[str, Any]],
    requested: str,
) -> list[RoadMatch]:
    """Find OSM road ways matching the operator's requested road."""

    matches: list[RoadMatch] = []

    for road in roads:

        result = road_match_score(
            requested,
            road.get("tags") or {},
        )

        if result is None:
            continue

        score, field, value = result

        matches.append(
            RoadMatch(
                road=road,
                score=score,
                matched_field=field,
                matched_value=value,
            )
        )

    matches.sort(
        key=lambda item: (
            -item.score,
            item.road.get("road_type") or "",
            item.road.get("osm_way_id") or 0,
        )
    )

    return matches
