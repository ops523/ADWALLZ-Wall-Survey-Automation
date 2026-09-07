from __future__ import annotations

from types import SimpleNamespace

from src.geocoding.road_resolver import RoadResolver
from src.models.target import SurveyTarget


TARGET = SurveyTarget(
    state="Andhra Pradesh",
    district="Nandyal",
    pincode="518422",
    place_name="Atmakur",
    road_name="Atmakur Main Road",
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return FakeResponse(self.payload)


class FakeGeocoder:
    url = "https://example.test"
    user_agent = "test-agent"

    def __init__(self, payload):
        self.session = FakeSession(payload)


class FakeOSM:
    def __init__(self, payload):
        self.payload = payload
        self.queries = []

    def query(self, query):
        self.queries.append(query)
        return self.payload


def nominatim_result(
    osm_id=1450441172,
    lat=15.8743880,
    lon=78.5778966,
):
    return {
        "osm_type": "way",
        "osm_id": osm_id,
        "lat": str(lat),
        "lon": str(lon),
        "display_name": (
            "Atmakur Main Road, Atmakur, "
            "Nandyal, Andhra Pradesh, 518422, India"
        ),
        "namedetails": {
            "name": "Atmakur Main Road",
        },
        "address": {
            "road": "Atmakur Main Road",
            "postcode": "518422",
            "district": "Nandyal",
            "state": "Andhra Pradesh",
        },
    }


def osm_way(way_id=1450441172):
    return {
        "elements": [
            {
                "type": "way",
                "id": way_id,
                "tags": {
                    "highway": "tertiary",
                    "name": "Atmakur Main Road",
                },
                "geometry": [
                    {
                        "lat": 15.864969,
                        "lon": 78.5682277,
                    },
                    {
                        "lat": 15.8788652,
                        "lon": 78.5898519,
                    },
                ],
            }
        ]
    }


def test_exact_nominatim_road_can_resolve_within_radius():
    geocoder = FakeGeocoder(
        [nominatim_result()]
    )

    osm = FakeOSM(
        osm_way()
    )

    resolver = RoadResolver(
        geocoder=geocoder,
        osm_client=osm,
        road_search_radius_km=20,
        confident_radius_km=20,
    )

    result = resolver.resolve(
        target=TARGET,
        requested_road="Atmakur Main Road",
        origin_latitude=15.8743880,
        origin_longitude=78.5778966,
    )

    assert result is not None
    assert result.confidence == "CONFIDENT"
    assert result.osm_way_ids == (1450441172,)
    assert result.roads[0]["road_name"] == "Atmakur Main Road"


def test_distant_road_is_not_accepted():
    geocoder = FakeGeocoder(
        [nominatim_result()]
    )

    osm = FakeOSM(
        osm_way()
    )

    resolver = RoadResolver(
        geocoder=geocoder,
        osm_client=osm,
        road_search_radius_km=5,
        confident_radius_km=5,
    )

    result = resolver.resolve(
        target=TARGET,
        requested_road="Atmakur Main Road",
        origin_latitude=15.9149208,
        origin_longitude=78.7079658,
    )

    assert result is not None
    assert result.confidence == "UNRESOLVED"
    assert result.osm_way_ids == ()
    assert result.roads == ()


def test_wrong_osm_way_name_is_rejected():
    geocoder = FakeGeocoder(
        [nominatim_result()]
    )

    osm = FakeOSM(
        {
            "elements": [
                {
                    "type": "way",
                    "id": 1450441172,
                    "tags": {
                        "highway": "tertiary",
                        "name": "Completely Different Road",
                    },
                    "geometry": [
                        {
                            "lat": 15.874,
                            "lon": 78.577,
                        },
                        {
                            "lat": 15.875,
                            "lon": 78.578,
                        },
                    ],
                }
            ]
        }
    )

    resolver = RoadResolver(
        geocoder=geocoder,
        osm_client=osm,
        road_search_radius_km=20,
        confident_radius_km=20,
    )

    result = resolver.resolve(
        target=TARGET,
        requested_road="Atmakur Main Road",
        origin_latitude=15.8743880,
        origin_longitude=78.5778966,
    )

    assert result is not None
    assert result.confidence == "UNRESOLVED"
    assert result.osm_way_ids == ()


def test_no_nominatim_candidate_returns_none():
    geocoder = FakeGeocoder([])

    osm = FakeOSM({"elements": []})

    resolver = RoadResolver(
        geocoder=geocoder,
        osm_client=osm,
    )

    result = resolver.resolve(
        target=TARGET,
        requested_road="Unknown Road",
        origin_latitude=15.9149208,
        origin_longitude=78.7079658,
    )

    assert result is None
