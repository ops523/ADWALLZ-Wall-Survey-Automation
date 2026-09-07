from __future__ import annotations

from types import SimpleNamespace

from src.cli import (
    assign_point_ids,
    deduplicate_records,
    resolve_requested_roads,
)
from src.models.target import SurveyTarget


class FakeResolver:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def resolve(
        self,
        target,
        requested_road,
        origin_latitude,
        origin_longitude,
    ):
        self.calls.append(
            (
                target,
                requested_road,
                origin_latitude,
                origin_longitude,
            )
        )
        return self.result


def make_target():
    return SurveyTarget(
        state="Andhra Pradesh",
        district="Nandyal",
        pincode="518422",
        place_name="Atmakur",
        road_name="State Highway 57",
    )


def make_road(way_id=101, name="State Highway 57"):
    if name == "State Highway 57":
        reference = "SH 57"
    elif name == "NH 340C":
        reference = "NH 340C"
    else:
        reference = ""

    return {
        "osm_way_id": way_id,
        "road_name": name,
        "road_type": "primary",
        "geometry": None,
        "tags": {
            "name": name,
            "ref": reference,
        },
    }


def test_local_exact_match_is_used_without_targeted_resolver():
    roads = [
        make_road(),
        make_road(102, "Other Road"),
    ]

    resolver = FakeResolver(None)

    result = resolve_requested_roads(
        roads=roads,
        requested_road="State Highway 57",
        resolver=resolver,
        target=make_target(),
        origin_latitude=15.0,
        origin_longitude=78.0,
    )

    assert [road["osm_way_id"] for road in result] == [101]
    assert resolver.calls == []


def test_multiple_local_segments_of_same_requested_road_are_selected():
    roads = [
        make_road(101),
        make_road(102),
        make_road(103, "Other Road"),
    ]

    resolver = FakeResolver(None)

    result = resolve_requested_roads(
        roads=roads,
        requested_road="State Highway 57",
        resolver=resolver,
        target=make_target(),
        origin_latitude=15.0,
        origin_longitude=78.0,
    )

    assert [road["osm_way_id"] for road in result] == [101, 102]
    assert resolver.calls == []


def test_targeted_resolver_is_used_when_local_match_fails():
    local_roads = [
        make_road(201, "NH 340C"),
    ]

    resolved_road = make_road(
        301,
        "State Highway 57",
    )

    resolved = SimpleNamespace(
        requested_name="State Highway 57",
        osm_way_ids=(301,),
        roads=(resolved_road,),
        method="NOMINATIM_ROAD",
        confidence="CONFIDENT",
        distance_km=4.2,
        matched_name="State Highway 57",
        matched_reference="SH 57",
    )

    resolver = FakeResolver(resolved)

    result = resolve_requested_roads(
        roads=local_roads,
        requested_road="State Highway 57",
        resolver=resolver,
        target=make_target(),
        origin_latitude=15.0,
        origin_longitude=78.0,
    )

    assert [road["osm_way_id"] for road in result] == [301]
    assert len(resolver.calls) == 1
    assert resolver.calls[0][1] == "State Highway 57"


def test_review_required_does_not_generate_survey_roads():
    local_roads = [
        make_road(201, "NH 340C"),
    ]

    resolved = SimpleNamespace(
        requested_name="State Highway 57",
        osm_way_ids=(301,),
        roads=(make_road(301),),
        method="NOMINATIM_ROAD",
        confidence="REVIEW_REQUIRED",
        distance_km=12.5,
        matched_name="State Highway 57",
        matched_reference="SH 57",
    )

    resolver = FakeResolver(resolved)

    result = resolve_requested_roads(
        roads=local_roads,
        requested_road="State Highway 57",
        resolver=resolver,
        target=make_target(),
        origin_latitude=15.0,
        origin_longitude=78.0,
    )

    assert result == []


def test_unresolved_road_does_not_generate_survey_roads():
    local_roads = [
        make_road(201, "NH 340C"),
    ]

    resolved = SimpleNamespace(
        requested_name="State Highway 57",
        osm_way_ids=(),
        roads=(),
        method="NOMINATIM_ROAD",
        confidence="UNRESOLVED",
        distance_km=18.0,
        matched_name="State Highway 57",
        matched_reference="SH 57",
    )

    resolver = FakeResolver(resolved)

    result = resolve_requested_roads(
        roads=local_roads,
        requested_road="State Highway 57",
        resolver=resolver,
        target=make_target(),
        origin_latitude=15.0,
        origin_longitude=78.0,
    )

    assert result == []


def test_deduplication_uses_physical_location_and_bearing():
    records = [
        {
            "latitude": 15.123456789,
            "longitude": 78.123456789,
            "road_bearing": 90.1234,
        },
        {
            "latitude": 15.1234567891,
            "longitude": 78.1234567891,
            "road_bearing": 90.1235,
        },
        {
            "latitude": 15.1234568,
            "longitude": 78.1234568,
            "road_bearing": 180.0,
        },
    ]

    result = deduplicate_records(records)

    assert len(result) == 2


def test_point_ids_are_deterministic():
    records = [
        {
            "latitude": 15.2,
            "longitude": 78.2,
            "road_bearing": 180.0,
        },
        {
            "latitude": 15.1,
            "longitude": 78.1,
            "road_bearing": 90.0,
        },
    ]

    result = assign_point_ids(records)

    assert result[0]["point_id"] == "SP-000001"
    assert result[1]["point_id"] == "SP-000002"
    assert result[0]["latitude"] == 15.1
