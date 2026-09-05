from __future__ import annotations

from typing import Any

from shapely.geometry import LineString


# Main road classes we are interested in for wall advertising.
DEFAULT_ROAD_TYPES = (
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "unclassified",
    "residential",
)


def build_road_query(
    *,
    bbox: tuple[float, float, float, float],
    road_name: str | None = None,
    road_types: tuple[str, ...] = DEFAULT_ROAD_TYPES,
) -> str:
    """
    Build an Overpass query using the resolved geographic bounding box.

    bbox order:
        south, north, west, east

    Pincode/place-name matching is performed before this stage.
    Once the target has been geocoded, OSM is queried geographically.
    """

    south, north, west, east = bbox

    highway_regex = "|".join(road_types)

    name_filter = ""

    if road_name:
        escaped_name = (
            road_name
            .replace("\\", "\\\\")
            .replace('"', '\\"')
        )

        name_filter = f'[name="{escaped_name}"]'

    return f"""
[out:json][timeout:180];

way
  ["highway"~"^({highway_regex})$"]
  {name_filter}
  ({south},{west},{north},{east});

out tags geom;
"""


def elements_to_lines(
    elements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Convert Overpass way geometries into Shapely LineStrings.
    """

    roads: list[dict[str, Any]] = []

    for element in elements:
        geometry = element.get("geometry") or []

        coordinates = [
            (point["lon"], point["lat"])
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
                "road_type": tags.get("highway"),
                "geometry": LineString(coordinates),
                "tags": tags,
            }
        )

    return roads
