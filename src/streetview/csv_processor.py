from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from src.streetview.discovery import ImageryDiscovery


INPUT_REQUIRED_FIELDS = {
    "point_id",
    "state",
    "district",
    "pincode",
    "place_name",
    "road_name",
    "latitude",
    "longitude",
    "road_bearing",
    "heading_left",
    "heading_right",
}

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
    "provider",
    "status",
    "image_id",
    "image_latitude",
    "image_longitude",
    "capture_date",
    "image_heading",
    "image_url",
]


def read_survey_points(
    input_path: str | Path,
) -> list[dict[str, str]]:
    """
    Read and validate the Pack 1A survey-point CSV.
    """

    path = Path(input_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Survey-point CSV not found: {path}"
        )

    with path.open(
        "r",
        newline="",
        encoding="utf-8",
    ) as handle:

        reader = csv.DictReader(handle)

        if reader.fieldnames is None:
            raise ValueError(
                "Survey-point CSV has no header."
            )

        missing = INPUT_REQUIRED_FIELDS - set(
            reader.fieldnames
        )

        if missing:
            raise ValueError(
                "Survey-point CSV is missing required fields: "
                + ", ".join(sorted(missing))
            )

        rows = list(reader)

    return rows


def validate_point(
    row: dict[str, str],
) -> None:
    """
    Validate fields required by imagery discovery.
    """

    if not row.get("point_id"):
        raise ValueError(
            "Survey point is missing point_id."
        )

    if not row.get("pincode"):
        raise ValueError(
            f"{row.get('point_id')}: pincode is required."
        )

    try:
        latitude = float(row["latitude"])
        longitude = float(row["longitude"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            f"{row.get('point_id')}: invalid coordinates."
        ) from exc

    if not -90 <= latitude <= 90:
        raise ValueError(
            f"{row['point_id']}: latitude is outside valid range."
        )

    if not -180 <= longitude <= 180:
        raise ValueError(
            f"{row['point_id']}: longitude is outside valid range."
        )


def process_survey_points(
    rows: Iterable[dict[str, str]],
    discovery: ImageryDiscovery,
    radius_m: int = 50,
    limit: int | None = None,
) -> list[dict]:
    """
    Run imagery discovery for survey points.

    Discovery is performed once per physical survey point. The resulting
    imagery heading is retained alongside the two road-side headings from
    the original survey point.
    """

    if radius_m < 0:
        raise ValueError(
            "radius_m cannot be negative."
        )

    results: list[dict] = []

    for index, row in enumerate(rows):

        if limit is not None and index >= limit:
            break

        validate_point(row)

        latitude = float(row["latitude"])
        longitude = float(row["longitude"])

        result = discovery.discover(
            latitude=latitude,
            longitude=longitude,
            radius_m=radius_m,
        )

        results.append(
            {
                "point_id": row["point_id"],
                "state": row["state"],
                "district": row["district"],
                "pincode": row["pincode"],
                "place_name": row["place_name"],
                "road_name": row.get("road_name", ""),
                "road_type": row.get("road_type", ""),
                "osm_way_id": row.get("osm_way_id", ""),
                "latitude": latitude,
                "longitude": longitude,
                "road_bearing": row.get("road_bearing", ""),
                "heading_left": row.get("heading_left", ""),
                "heading_right": row.get("heading_right", ""),
                "provider": result.provider,
                "status": result.status,
                "image_id": result.image_id,
                "image_latitude": result.image_latitude,
                "image_longitude": result.image_longitude,
                "capture_date": result.capture_date,
                "image_heading": result.heading,
                "image_url": result.image_url,
            }
        )

    return results


def write_discovery_csv(
    records: list[dict],
    output_path: str | Path,
) -> Path:
    """
    Write imagery discovery results.
    """

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
            extrasaction="ignore",
        )

        writer.writeheader()
        writer.writerows(records)

    return output