from __future__ import annotations

import argparse
import csv
from pathlib import Path

from src.geocoding.boundary import (
    bbox_dimensions_km,
    tighten_bbox,
)
from src.geocoding.nominatim import NominatimClient
from src.geocoding.road_resolver import (
    RoadResolver,
    ResolvedRoad,
    print_resolution_result,
)
from src.models.target import SurveyTarget
from src.osm.client import OverpassClient
from src.osm.roads import (
    DEFAULT_ROAD_TYPES,
    build_road_query,
    elements_to_lines,
    find_road_matches,
)
from src.osm.sampling import (
    interpolate_every_meters,
    point_record,
)


OUTPUT_FIELDS = [
    "point_id",
    "state",
    "district",
    "pincode",
    "place_name",
    "road_name",
    "road_type",
    "osm_way_id",
    "latitude",
    "longitude",
    "road_bearing",
    "heading_left",
    "heading_right",
    "sample_distance_m",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "ADWALLZ Wall Survey Automation - "
            "OSM Road Network & Sampling Engine"
        )
    )

    parser.add_argument("--state", required=True)
    parser.add_argument("--district", required=True)
    parser.add_argument("--pincode", required=True)
    parser.add_argument("--place", required=True)
    parser.add_argument("--road", default=None)

    parser.add_argument(
        "--interval",
        type=float,
        default=20.0,
    )

    parser.add_argument(
        "--output",
        default="output/survey_points.csv",
    )

    parser.add_argument(
        "--radius-km",
        type=float,
        default=5.0,
        help=(
            "Maximum local target search radius in kilometres. "
            "Default: 5"
        ),
    )

    parser.add_argument(
        "--road-search-radius-km",
        type=float,
        default=20.0,
        help=(
            "Maximum radius for targeted road resolution. "
            "Default: 20"
        ),
    )

    parser.add_argument(
        "--road-confident-radius-km",
        type=float,
        default=10.0,
        help=(
            "Maximum distance for automatic road acceptance. "
            "Roads beyond this distance require review. "
            "Default: 10"
        ),
    )

    return parser.parse_args()


def deduplicate_records(records: list[dict]) -> list[dict]:
    """
    Remove duplicate physical survey points.

    Coordinates and bearing are used rather than OSM way ID because
    neighbouring OSM segments can represent the same physical road location.
    """
    unique: dict[tuple, dict] = {}

    for record in records:
        key = (
            round(record["latitude"], 7),
            round(record["longitude"], 7),
            round(record["road_bearing"], 2),
        )

        if key not in unique:
            unique[key] = record

    return list(unique.values())


def assign_point_ids(records: list[dict]) -> list[dict]:
    """
    Assign deterministic survey-point IDs.
    """
    ordered = sorted(
        records,
        key=lambda record: (
            record["latitude"],
            record["longitude"],
            record["road_bearing"],
        ),
    )

    for index, record in enumerate(ordered, start=1):
        record["point_id"] = f"SP-{index:06d}"

    return ordered


def write_csv(
    records: list[dict],
    output_path: str,
) -> Path:
    output = Path(output_path)

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=OUTPUT_FIELDS,
        )

        writer.writeheader()
        writer.writerows(records)

    return output


def print_local_road_candidates(
    roads: list[dict],
) -> None:
    print()
    print("Closest available named/reference roads:")

    candidates = []

    for road in roads:
        tags = road.get("tags") or {}

        name = (
            tags.get("name")
            or tags.get("official_name")
            or tags.get("alt_name")
            or ""
        )

        ref = tags.get("ref") or ""

        if name or ref:
            candidates.append(
                (
                    road.get("road_type") or "",
                    ref,
                    name,
                )
            )

    seen = set()
    count = 0

    for road_type, ref, name in candidates:
        key = (
            road_type,
            ref,
            name,
        )

        if key in seen:
            continue

        seen.add(key)

        print(
            f"  {road_type:<12} "
            f"ref={ref or '-':<12} "
            f"name={name or '-'}"
        )

        count += 1

        if count >= 20:
            break


def resolve_requested_roads(
    roads: list[dict],
    requested_road: str | None,
    resolver: RoadResolver | None = None,
    target: SurveyTarget | None = None,
    origin_latitude: float | None = None,
    origin_longitude: float | None = None,
) -> list[dict]:
    """
    Resolve an operator-requested road.

    Resolution order:

        1. Exact/safe local OSM match
        2. Targeted Nominatim road resolution
        3. Exact OSM way validation

    A different road is never silently substituted.
    """

    if not requested_road:
        return roads

    local_matches = find_road_matches(
        roads,
        requested_road,
    )

    if local_matches:
        best_score = local_matches[0].score

        selected = [
            match.road
            for match in local_matches
            if match.score == best_score
        ]

        print()
        print("Local road resolver:")
        print(f'  Requested : "{requested_road}"')
        print(f"  Matches   : {len(local_matches)}")
        print(f"  Best score: {best_score}")
        print("  Selected:")

        for match in local_matches[:10]:
            road = match.road

            print(
                f"    score={match.score:<3} "
                f"field={match.matched_field:<14} "
                f"value={match.matched_value} "
                f"osm_way={road.get('osm_way_id')}"
            )

        return selected

    print()
    print(
        f'No local OSM match found for road: "{requested_road}"'
    )

    print(
        "The system will attempt targeted road resolution."
    )

    print_local_road_candidates(roads)

    if (
        resolver is None
        or target is None
        or origin_latitude is None
        or origin_longitude is None
    ):
        print()
        print(
            "Targeted road resolver was not configured."
        )
        print(
            "Road resolution failed safely."
        )
        return []

    resolved: ResolvedRoad | None = resolver.resolve(
        target=target,
        requested_road=requested_road,
        origin_latitude=origin_latitude,
        origin_longitude=origin_longitude,
    )

    print_resolution_result(resolved)

    if resolved is None:
        print()
        print(
            "Road resolution failed safely."
        )
        return []

    if resolved.confidence != "CONFIDENT":
        print()

        if resolved.confidence == "REVIEW_REQUIRED":
            print(
                "Road resolution requires human review."
            )
            print(
                "No survey points will be generated."
            )
        else:
            print(
                "Road resolution is unresolved."
            )
            print(
                "No survey points will be generated."
            )

        return []

    if not resolved.roads:
        print()
        print(
            "Road resolver returned no validated OSM ways."
        )
        print(
            "No survey points will be generated."
        )
        return []

    print()
    print(
        f"Targeted road resolution accepted "
        f"{len(resolved.roads)} OSM way(s)."
    )

    return list(resolved.roads)


def generate_records(
    roads: list[dict],
    target: SurveyTarget,
) -> list[dict]:
    records: list[dict] = []

    for road in roads:
        geometry = road["geometry"]

        points = interpolate_every_meters(
            geometry,
            target.sampling_interval_m,
        )

        if len(points) < 2:
            continue

        for index, point in enumerate(points):
            previous = points[
                max(0, index - 1)
            ]

            following = points[
                min(
                    len(points) - 1,
                    index + 1,
                )
            ]

            if previous.equals(following):
                continue

            record = point_record(
                point=point,
                previous=previous,
                following=following,
                state=target.state,
                district=target.district,
                pincode=target.pincode,
                place_name=target.place_name,
                road_name=road["road_name"],
                road_type=road["road_type"],
                osm_way_id=road["osm_way_id"],
                interval_m=target.sampling_interval_m,
            )

            records.append(record)

    return records


def main() -> None:
    args = parse_args()

    if args.interval <= 0:
        raise ValueError(
            "--interval must be greater than zero"
        )

    if args.road_search_radius_km <= 0:
        raise ValueError(
            "--road-search-radius-km must be greater than zero"
        )

    if args.road_confident_radius_km <= 0:
        raise ValueError(
            "--road-confident-radius-km must be greater than zero"
        )

    if (
        args.road_confident_radius_km
        > args.road_search_radius_km
    ):
        raise ValueError(
            "--road-confident-radius-km cannot exceed "
            "--road-search-radius-km"
        )

    target = SurveyTarget(
        state=args.state,
        district=args.district,
        pincode=args.pincode,
        place_name=args.place,
        road_name=args.road,
        sampling_interval_m=args.interval,
    )

    print()
    print("=" * 70)
    print("ADWALLZ WALL SURVEY AUTOMATION")
    print("PACK 1A-C — TARGETED ROAD RESOLUTION")
    print("=" * 70)
    print()

    print("Target:")
    print(f"  State   : {target.state}")
    print(f"  District: {target.district}")
    print(f"  Pincode : {target.pincode}")
    print(f"  Place   : {target.place_name}")
    print(
        f"  Road    : "
        f"{target.road_name or 'All relevant roads'}"
    )
    print(
        f"  Interval: "
        f"{target.sampling_interval_m}m"
    )

    print()
    print(
        "1. Resolving target using Nominatim..."
    )

    geocoder = NominatimClient()

    resolved = geocoder.resolve(target)

    print(
        f"   Resolved: {resolved.display_name}"
    )

    print(
        f"   Coordinates: "
        f"{resolved.latitude}, "
        f"{resolved.longitude}"
    )

    if resolved.bbox is None:
        raise RuntimeError(
            "Nominatim did not return a bounding box for the target. "
            "Cannot safely discover the target's road network."
        )

    original_bbox = resolved.bbox

    south, north, west, east = original_bbox

    print(
        "   Nominatim bbox:"
        f" {south}, {west}, {north}, {east}"
    )

    search_bbox = tighten_bbox(
        original_bbox=original_bbox,
        latitude=resolved.latitude,
        longitude=resolved.longitude,
        radius_km=args.radius_km,
    )

    south, north, west, east = search_bbox

    height_km, width_km = bbox_dimensions_km(
        search_bbox
    )

    print(
        f"   Target radius : {args.radius_km:.1f} km"
    )

    print(
        "   Search bbox   :"
        f" {south:.7f}, {west:.7f}, "
        f"{north:.7f}, {east:.7f}"
    )

    print(
        f"   Search size   : "
        f"{height_km:.2f} km × {width_km:.2f} km"
    )

    print()
    print(
        "2. Querying OpenStreetMap / Overpass..."
    )

    query = build_road_query(
        bbox=search_bbox,
        road_name=None,
        road_types=DEFAULT_ROAD_TYPES,
    )

    osm_client = OverpassClient()

    payload = osm_client.query(query)

    local_roads = elements_to_lines(
        payload.get("elements", [])
    )

    print(
        f"   Road segments retrieved: "
        f"{len(local_roads)}"
    )

    if not local_roads:
        print()
        print(
            "No road segments were found."
        )
        return

    resolver = RoadResolver(
        geocoder=geocoder,
        osm_client=osm_client,
        road_search_radius_km=args.road_search_radius_km,
        confident_radius_km=args.road_confident_radius_km,
    )

    roads = resolve_requested_roads(
        roads=local_roads,
        requested_road=target.road_name,
        resolver=resolver,
        target=target,
        origin_latitude=resolved.latitude,
        origin_longitude=resolved.longitude,
    )

    if not roads:
        print()
        print(
            "No safe road corridor was resolved."
        )
        print(
            "Stopping before survey-point generation."
        )
        return

    print()
    print(
        "3. Generating survey points..."
    )

    records = generate_records(
        roads=roads,
        target=target,
    )

    print(
        f"   Raw survey points: "
        f"{len(records)}"
    )

    print()
    print(
        "4. Deduplicating physical survey points..."
    )

    records = deduplicate_records(records)

    print(
        f"   Unique survey points: "
        f"{len(records)}"
    )

    records = assign_point_ids(records)

    if not records:
        print()
        print(
            "No valid survey points were generated."
        )
        return

    output = write_csv(
        records,
        args.output,
    )

    print()
    print("=" * 70)
    print("COMPLETED")
    print("=" * 70)
    print()

    print(
        f"Output: {output}"
    )

    print(
        f"Survey points: {len(records)}"
    )

    print()
    print("Identity retained for every point:")
    print(
        f"  {target.state} | "
        f"{target.district} | "
        f"{target.pincode} | "
        f"{target.place_name}"
    )

    print()
    print("Each physical survey point contains:")
    print("  • Coordinates")
    print("  • Road bearing")
    print("  • Left-side imagery heading")
    print("  • Right-side imagery heading")
    print("  • OSM way ID")


if __name__ == "__main__":
    main()
