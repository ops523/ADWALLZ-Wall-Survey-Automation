from __future__ import annotations

import argparse
import csv
from pathlib import Path

from src.geocoding.nominatim import NominatimClient
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
from src.geocoding.boundary import (
    bbox_dimensions_km,
    tighten_bbox,
)

OUTPUT_FIELDS = [
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

    parser.add_argument(
        "--state",
        required=True,
    )

    parser.add_argument(
        "--district",
        required=True,
    )

    parser.add_argument(
        "--pincode",
        required=True,
    )

    parser.add_argument(
        "--place",
        required=True,
    )

    parser.add_argument(
        "--road",
        default=None,
    )

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

    return parser.parse_args()


def deduplicate_records(
    records: list[dict],
) -> list[dict]:

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


def resolve_requested_roads(
    roads: list[dict],
    requested_road: str | None,
) -> list[dict]:

    if not requested_road:
        return roads

    matches = find_road_matches(
        roads,
        requested_road,
    )

    if not matches:

        print()
        print(
            f'No confident OSM match found for road: "{requested_road}"'
        )

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

        print()
        print(
            "The system will NOT automatically select a different "
            "road because that could survey the wrong corridor."
        )

        return []

    best_score = matches[0].score

    selected = [
        match.road
        for match in matches
        if match.score == best_score
    ]

    print()
    print("Road resolver:")

    print(
        f'  Requested : "{requested_road}"'
    )

    print(
        f"  Matches   : {len(matches)}"
    )

    print(
        f"  Best score: {best_score}"
    )

    print(
        "  Selected:"
    )

    for match in matches[:10]:

        road = match.road

        print(
            f"    score={match.score:<3} "
            f"field={match.matched_field:<14} "
            f"value={match.matched_value} "
            f"osm_way={road.get('osm_way_id')}"
        )

    return selected


def main() -> None:

    args = parse_args()

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
    print("PACK 1A — TARGET & ROAD RESOLUTION")
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

    # ---------------------------------------------------------
    # STEP 1 — Resolve target
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # STEP 2 — Retrieve geographic road network
    # ---------------------------------------------------------

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

    roads = elements_to_lines(
        payload.get("elements", [])
    )

    print(
        f"   Road segments retrieved: "
        f"{len(roads)}"
    )

    if not roads:

        print()
        print(
            "No road segments were found."
        )

        return

    # ---------------------------------------------------------
    # STEP 3 — Resolve requested road
    # ---------------------------------------------------------

    roads = resolve_requested_roads(
        roads,
        target.road_name,
    )

    if not roads:

        print()
        print(
            "Road resolution failed safely."
        )

        return

    # ---------------------------------------------------------
    # STEP 4 — Sample roads
    # ---------------------------------------------------------

    print()
    print(
        "3. Generating survey points..."
    )

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

    # ---------------------------------------------------------
    # STEP 5 — Deduplicate
    # ---------------------------------------------------------

    records = deduplicate_records(
        records
    )

    # ---------------------------------------------------------
    # STEP 6 — Write output
    # ---------------------------------------------------------

    output = write_csv(
        records,
        args.output,
    )

    print()
    print(
        f"   Survey points generated: "
        f"{len(records)}"
    )

    print()
    print("=" * 70)
    print("COMPLETED")
    print("=" * 70)
    print()

    print(
        f"Output: {output}"
    )

    print()

    print(
        "Every survey point retains:"
    )

    print(
        f"  {target.state} | "
        f"{target.district} | "
        f"{target.pincode} | "
        f"{target.place_name}"
    )

    print()


if __name__ == "__main__":
    main()
