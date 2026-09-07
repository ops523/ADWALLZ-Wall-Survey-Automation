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


def test_reference_matching_does_not_match_partial_route_number():
    from src.osm.roads import road_match_score

    tags = {
        "ref": "SH5",
        "highway": "primary",
    }

    result = road_match_score(
        "State Highway 57",
        tags,
    )

    assert result is None


def test_reference_matching_accepts_equivalent_format():
    from src.osm.roads import road_match_score

    tags = {
        "ref": "SH57",
        "highway": "primary",
    }

    result = road_match_score(
        "State Highway 57",
        tags,
    )

    assert result is not None
    assert result[0] == 100
    assert result[1] == "ref"
    assert result[2] == "SH57"


def test_reference_matching_accepts_hyphen_and_space():
    from src.osm.roads import road_match_score

    tags = {
        "ref": "SH57",
        "highway": "primary",
    }

    assert road_match_score("SH-57", tags) is not None
    assert road_match_score("SH 57", tags) is not None
    assert road_match_score("SH57", tags) is not None
def test_point_record_contains_both_road_side_headings():
    from shapely.geometry import Point
    from src.osm.sampling import point_record

    record = point_record(
        point=Point(78.7079, 15.9149),
        previous=Point(78.7078, 15.9149),
        following=Point(78.7080, 15.9149),
        state="Andhra Pradesh",
        district="Nandyal",
        pincode="518422",
        place_name="Atmakur",
        road_name="State Highway 57",
        road_type="primary",
        osm_way_id=123,
        interval_m=20.0,
    )

    assert record["pincode"] == "518422"
    assert record["latitude"] == 15.9149
    assert record["longitude"] == 78.7079

    assert "road_bearing" in record
    assert "heading_left" in record
    assert "heading_right" in record

    assert (
        record["heading_right"]
        == (record["road_bearing"] + 180 - 90) % 360
    )


def test_point_record_accepts_stable_point_id():
    from shapely.geometry import Point
    from src.osm.sampling import point_record

    record = point_record(
        point=Point(78.7079, 15.9149),
        previous=Point(78.7078, 15.9149),
        following=Point(78.7080, 15.9149),
        state="Andhra Pradesh",
        district="Nandyal",
        pincode="518422",
        place_name="Atmakur",
        road_name="State Highway 57",
        road_type="primary",
        osm_way_id=123,
        interval_m=20.0,
        point_id="SP-000001",
    )

    assert record["point_id"] == "SP-000001"


def test_point_ids_are_deterministic():
    from src.cli import assign_point_ids

    records = [
        {
            "latitude": 15.9200,
            "longitude": 78.7000,
            "road_bearing": 90.0,
        },
        {
            "latitude": 15.9100,
            "longitude": 78.7000,
            "road_bearing": 90.0,
        },
    ]

    result = assign_point_ids(records)

    assert result[0]["point_id"] == "SP-000001"
    assert result[1]["point_id"] == "SP-000002"

    assert result[0]["latitude"] == 15.9100
    assert result[1]["latitude"] == 15.9200