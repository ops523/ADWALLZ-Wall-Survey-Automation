from __future__ import annotations

from dataclasses import dataclass

from src.geocoding.road_resolver import RoadResolver
from src.models.target import SurveyTarget


def make_target(
    road_name: str = "State Highway 57",
) -> SurveyTarget:
    return SurveyTarget(
        state="Andhra Pradesh",
        district="Nandyal",
        pincode="518422",
        place_name="Atmakur",
        road_name=road_name,
    )


def make_road(
    way_id: int,
    *,
    name: str = "State Highway 57",
    ref: str = "SH 57",
    node_ids: tuple[int, ...] = (),
) -> dict:
    return {
        "osm_way_id": way_id,
        "road_name": name,
        "road_ref": ref,
        "road_type": "primary",
        "geometry": None,
        "tags": {
            "name": name,
            "ref": ref,
            "node_ids": list(node_ids),
        },
    }


def test_reference_road_accepts_same_reference():
    roads = [
        make_road(
            100,
            ref="SH 57",
        )
    ]

    result = RoadResolver._validate_roads(
        roads=roads,
        requested_road="State Highway 57",
    )

    assert [road["osm_way_id"] for road in result] == [100]


def test_reference_road_rejects_different_reference():
    roads = [
        make_road(
            100,
            name="State Highway 57",
            ref="SH 57",
        ),
        make_road(
            200,
            name="State Highway 5",
            ref="SH 5",
        ),
    ]

    result = RoadResolver._validate_roads(
        roads=roads,
        requested_road="State Highway 57",
    )

    assert [road["osm_way_id"] for road in result] == [100]


def test_named_road_accepts_exact_name():
    roads = [
        make_road(
            100,
            name="Atmakur Main Road",
            ref="",
        )
    ]

    result = RoadResolver._validate_roads(
        roads=roads,
        requested_road="Atmakur Main Road",
    )

    assert [road["osm_way_id"] for road in result] == [100]


def test_named_road_rejects_different_name():
    roads = [
        make_road(
            100,
            name="Atmakur Main Road",
            ref="",
        ),
        make_road(
            200,
            name="Market Road",
            ref="",
        ),
    ]

    result = RoadResolver._validate_roads(
        roads=roads,
        requested_road="Atmakur Main Road",
    )

    assert [road["osm_way_id"] for road in result] == [100]


def test_connected_expansion_adds_same_reference_ways():
    resolver = RoadResolver(
        expansion_depth=1
    )

    seed = [
        make_road(
            100,
            ref="SH 57",
            node_ids=(1, 2),
        )
    ]

    connected_ids = {100, 200, 300}

    retrieved = [
        make_road(
            100,
            ref="SH 57",
            node_ids=(1, 2),
        ),
        make_road(
            200,
            ref="SH 57",
            node_ids=(2, 3),
        ),
        make_road(
            300,
            ref="SH 5",
            node_ids=(2, 4),
        ),
    ]

    resolver._find_connected_way_ids = (
        lambda way_ids: connected_ids
    )

    resolver._retrieve_ways = (
        lambda way_ids: retrieved
    )

    result = resolver._expand_connected_roads(
        seed_roads=seed,
        requested_road="State Highway 57",
    )

    assert [
        road["osm_way_id"]
        for road in result
    ] == [100, 200]


def test_connected_expansion_does_not_cross_into_other_highway():
    resolver = RoadResolver(
        expansion_depth=2
    )

    seed = [
        make_road(
            100,
            ref="SH 57",
        )
    ]

    calls = []

    def fake_connected(way_ids):
        calls.append(tuple(way_ids))

        if len(calls) == 1:
            return {100, 200}

        return {200, 300}

    resolver._find_connected_way_ids = (
        fake_connected
    )

    resolver._retrieve_ways = lambda way_ids: [
        make_road(
            200,
            ref="SH 57",
        ),
        make_road(
            300,
            ref="NH 340C",
        ),
    ]

    result = resolver._expand_connected_roads(
        seed_roads=seed,
        requested_road="State Highway 57",
    )

    ids = {
        road["osm_way_id"]
        for road in result
    }

    assert ids == {100, 200}
    assert 300 not in ids


def test_expansion_depth_zero_returns_seed_only():
    resolver = RoadResolver(
        expansion_depth=0
    )

    seed = [
        make_road(
            100,
            ref="SH 57",
        )
    ]

    resolver._find_connected_way_ids = (
        lambda way_ids: {100, 200}
    )

    resolver._retrieve_ways = lambda way_ids: [
        make_road(100, ref="SH 57"),
        make_road(200, ref="SH 57"),
    ]

    result = resolver._expand_connected_roads(
        seed_roads=seed,
        requested_road="State Highway 57",
    )

    assert [
        road["osm_way_id"]
        for road in result
    ] == [100]
