from __future__ import annotations


def normalize_heading(
    heading: float,
) -> float:
    return float(heading) % 360.0


def opposite_heading(
    heading: float,
) -> float:
    return normalize_heading(
        heading + 180.0
    )


def road_side_headings(
    road_bearing: float,
) -> tuple[float, float]:
    """
    Return headings perpendicular to the road.

    The two headings point toward opposite sides of the road.
    """

    base = normalize_heading(
        road_bearing
    )

    left = normalize_heading(
        base - 90.0
    )

    right = normalize_heading(
        base + 90.0
    )

    return left, right
