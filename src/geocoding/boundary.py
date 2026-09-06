from __future__ import annotations

import math

BBox = tuple[float, float, float, float]

EARTH_RADIUS_KM = 6371.0088


def validate_radius_km(radius_km: float) -> float:
    radius = float(radius_km)

    if radius <= 0:
        raise ValueError("Target radius must be greater than 0 km.")

    if radius > 50:
        raise ValueError(
            "Target radius is unexpectedly large. "
            "Maximum allowed radius is 50 km."
        )

    return radius


def radius_bbox(
    latitude: float,
    longitude: float,
    radius_km: float,
) -> BBox:
    """
    Create an approximate bounding box around a coordinate.

    Output order:
        south, north, west, east
    """

    radius = validate_radius_km(radius_km)

    lat = float(latitude)
    lon = float(longitude)

    lat_delta = math.degrees(
        radius / EARTH_RADIUS_KM
    )

    cos_lat = math.cos(math.radians(lat))

    if abs(cos_lat) < 1e-12:
        raise ValueError(
            "Cannot calculate longitude radius near the poles."
        )

    lon_delta = math.degrees(
        radius / (EARTH_RADIUS_KM * cos_lat)
    )

    south = max(-90.0, lat - lat_delta)
    north = min(90.0, lat + lat_delta)
    west = max(-180.0, lon - lon_delta)
    east = min(180.0, lon + lon_delta)

    return (
        south,
        north,
        west,
        east,
    )


def tighten_bbox(
    original_bbox: BBox,
    latitude: float,
    longitude: float,
    radius_km: float,
) -> BBox:
    """
    Intersect the original geocoding bbox with a local radius bbox.

    This prevents a very large administrative Nominatim bounding box
    from causing the OSM discovery engine to search an unnecessarily
    large surrounding area.

    The original bbox is never expanded.
    """

    if len(original_bbox) != 4:
        raise ValueError(
            "Bounding box must contain "
            "(south, north, west, east)."
        )

    south, north, west, east = map(
        float,
        original_bbox,
    )

    if south >= north:
        raise ValueError(
            "Invalid bounding box: south must be less than north."
        )

    if west >= east:
        raise ValueError(
            "Invalid bounding box: west must be less than east."
        )

    local_south, local_north, local_west, local_east = (
        radius_bbox(
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
        )
    )

    tightened = (
        max(south, local_south),
        min(north, local_north),
        max(west, local_west),
        min(east, local_east),
    )

    t_south, t_north, t_west, t_east = tightened

    if t_south >= t_north or t_west >= t_east:
        raise RuntimeError(
            "Resolved place centre does not overlap "
            "the Nominatim bounding box. "
            "Target cannot be tightened safely."
        )

    return tightened


def haversine_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """
    Great-circle distance between two coordinates in kilometres.
    """

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    delta_phi = math.radians(
        lat2 - lat1
    )

    delta_lambda = math.radians(
        lon2 - lon1
    )

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1)
        * math.cos(phi2)
        * math.sin(delta_lambda / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a),
    )

    return EARTH_RADIUS_KM * c


def bbox_dimensions_km(
    bbox: BBox,
) -> tuple[float, float]:
    """
    Return approximate (height_km, width_km).
    """

    south, north, west, east = bbox

    centre_lat = (
        south + north
    ) / 2.0

    centre_lon = (
        west + east
    ) / 2.0

    height = haversine_km(
        south,
        centre_lon,
        north,
        centre_lon,
    )

    width = haversine_km(
        centre_lat,
        west,
        centre_lat,
        east,
    )

    return (
        height,
        width,
    )
