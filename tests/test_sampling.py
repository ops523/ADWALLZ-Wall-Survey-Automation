from shapely.geometry import LineString

from src.osm.sampling import (
    bearing_between,
    interpolate_every_meters,
)


def test_sampling_returns_points():
    line = LineString(
        [
            (77.5946, 12.9716),
            (77.5956, 12.9716),
        ]
    )

    points = interpolate_every_meters(
        line,
        20,
    )

    assert len(points) > 1


def test_final_point_is_retained():
    line = LineString(
        [
            (77.5946, 12.9716),
            (77.5956, 12.9716),
        ]
    )

    points = interpolate_every_meters(
        line,
        20,
    )

    final = points[-1]

    assert abs(final.x - 77.5956) < 1e-7
    assert abs(final.y - 12.9716) < 1e-7


def test_bearing_is_normalized():
    start = (77.5946, 12.9716)
    end = (77.5956, 12.9716)

    from shapely.geometry import Point

    bearing = bearing_between(
        Point(*start),
        Point(*end),
    )

    assert 0 <= bearing < 360


def test_interval_must_be_positive():
    line = LineString(
        [
            (77.5946, 12.9716),
            (77.5956, 12.9716),
        ]
    )

    try:
        interpolate_every_meters(line, 0)
        assert False
    except ValueError:
        assert True
