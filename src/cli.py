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
)
from src.osm.sampling import (
    interpolate_every_meters,
    point_record,
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
        help="State name",
    )

    parser.add_argument(
        "--district",
        required=True,
        help="District name",
    )

    parser.add_argument(
        "--pincode",
        required=True,
        help="6-digit Indian pincode",
    )

    parser.add_argument(
        "--place",
        required=True,
        help="Town / Village / City",
    )

    parser.add_argument(
        "--road",
        default=None,
        help="Optional road/highway name",
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=20.0,
        help="Sampling interval in metres. Default: 20",
    )

    parser.add_argument(
        "--output",
        default="output/survey_points.csv",
        help="Output CSV path",
    )

    return parser.parse_args()


def deduplicate_records(
    records: list[dict],
) -> list[dict]:
    """
    Remove duplicate sample points.

    Coordinates are rounded to 7 decimal places and road bearing is included
    to avoid collapsing genuinely different directional road segments.
    """

    unique: dict[tuple, dict] = {}

    for record in records:
        key = (
            record["latitude"],
            record["longitude"],
            record["road_bearing"],
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
    print("PACK 1 — ROAD NETWORK & SAMPLING")
    print("=" * 70)
    print()

    print("Target:")
    print(f"  State   : {target.state}")
    print(f"  District: {target.district}")
    print(f"  Pincode : {target.pincode}")
    print(f"  Place   : {target.place_name}")
    print(f"  Road    : {target.road_name or 'All relevant roads'}")
    print(f"  Interval: {target.sampling_interval_m}m")
    print()

    # ---------------------------------------------------------
    # STEP 1 — Resolve target
    # ---------------------------------------------------------

    print("1. Resolving target using Nominatim...")

    geocoder = NominatimClient()

    resolved = geocoder.resolve(target)

    print(
        f"   Resolved: {resolved.display_name}"
    )

    print(
        f"   Coordinates: "
        f"{resolved.latitude}, {resolved.longitude}"
    )

    if resolved.bbox is None:
        raise RuntimeError(
            "Nominatim did not return a bounding box for the target. "
            "Cannot safely discover the target's road network."
        )

    south, north, west, east = resolved.bbox

    print(
        "   Bounding box:"
        f" {south}, {west}, {north}, {east}"
    )

    # ---------------------------------------------------------
    # STEP 2 — Query OSM
    # ---------------------------------------------------------

    print()
    print("2. Querying OpenStreetMap / Overpass...")

    query = build_road_query(
        bbox=resolved.bbox,
        road_name=target.road_name,
        road_types=DEFAULT_ROAD_TYPES,
    )

    osm_client = OverpassClient()

    payload = osm_client.query(query)

    roads = elements_to_lines(
        payload.get("elements", [])
    )

    print(
        f"   Road segments found: {len(roads)}"
    )

    if not roads:
        print()
        print(
            "No road segments were found for this target."
        )
        return

    # ---------------------------------------------------------
    # STEP 3 — Sample roads
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
    # STEP 4 — Deduplicate
    # ---------------------------------------------------------

    records = deduplicate_records(records)

    # ---------------------------------------------------------
    # STEP 5 — Write output
    # ---------------------------------------------------------

    output = write_csv(
        records,
        args.output,
    )

    print(
        f"   Survey points generated: {len(records)}"
    )

    print()
    print("=" * 70)
    print("COMPLETED")
    print("=" * 70)
    print()
    print(f"Output: {output}")
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
