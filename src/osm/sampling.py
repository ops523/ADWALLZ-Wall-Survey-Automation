from __future__ import annotations

from shapely.geometry import LineString, Point
from pyproj import Geod


GEOD = Geod(ellps="WGS84")


def bearing_between(
    start: Point,
    end: Point,
) -> float:
    """
    Calculate forward bearing from start to end.

    Returns:
        Bearing in degrees, normalized to 0-360.
    """

    azimuth, _, _ = GEOD.inv(
        start.x,
        start.y,
        end.x,
        end.y,
    )

    return azimuth % 360


def interpolate_every_meters(
    line: LineString,
    interval_m: float,
) -> list[Point]:
    """
    Generate points along a lon/lat LineString at approximately equal
    geodesic intervals.

    Shapely's normal interpolate() operates in coordinate units and therefore
    must not be used directly when coordinates are longitude/latitude.
    """

    if interval_m <= 0:
        raise ValueError(
            "interval_m must be greater than zero"
        )

    vertices = list(line.coords)

    if len(vertices) < 2:
        return []

    segments: list[tuple] = []

    total_distance = 0.0

    for (
        lon1,
        lat1,
    ), (
        lon2,
        lat2,
    ) in zip(vertices, vertices[1:]):

        azimuth, _, distance = GEOD.inv(
            lon1,
            lat1,
            lon2,
            lat2,
        )

        segments.append(
            (
                lon1,
                lat1,
                lon2,
                lat2,
                azimuth,
                distance,
                total_distance,
            )
        )

        total_distance += distance

    if total_distance == 0:
        return [Point(vertices[0])]

    points: list[Point] = []

    target_distance = 0.0

    for (
        lon1,
        lat1,
        lon2,
        lat2,
        azimuth,
        distance,
        segment_start,
    ) in segments:

        segment_end = segment_start + distance

        while target_distance <= segment_end + 1e-9:

            if target_distance >= segment_start - 1e-9:

                distance_into_segment = (
                    target_distance - segment_start
                )

                if distance_into_segment < 0:
                    distance_into_segment = 0

                if distance_into_segment > distance:
                    distance_into_segment = distance

                lon, lat, _ = GEOD.fwd(
                    lon1,
                    lat1,
                    azimuth,
                    distance_into_segment,
                )

                points.append(
                    Point(lon, lat)
                )

            target_distance += interval_m

    # Always retain the actual final vertex.
    final_point = Point(vertices[-1])

    if not points:
        points.append(final_point)

    else:
        _, _, final_distance = GEOD.inv(
            points[-1].x,
            points[-1].y,
            final_point.x,
            final_point.y,
        )

        if final_distance > 1:
            points.append(final_point)

    return points


def point_record(
    *,
    point: Point,
    previous: Point,
    following: Point,
    state: str,
    district: str,
    pincode: str,
    place_name: str,
    road_name: str | None,
    road_type: str | None,
    osm_way_id: int | None,
    interval_m: float,
) -> dict:
    """
    Convert a sampled point into the standard survey-point record.
    """

    road_bearing = bearing_between(
        previous,
        following,
    )

    return {
        "state": state,
        "district": district,
        "pincode": str(pincode),
        "place_name": place_name,
        "road_name": road_name,
        "road_type": road_type,
        "osm_way_id": osm_way_id,
        "latitude": round(point.y, 7),
        "longitude": round(point.x, 7),
        "road_bearing": round(road_bearing, 2),
        "heading_left": round(
            (road_bearing - 90) % 360,
            2,
        ),
        "heading_right": round(
            (road_bearing + 90) % 360,
            2,
        ),
        "sample_distance_m": interval_m,
    }
