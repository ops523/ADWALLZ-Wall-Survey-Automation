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
def test_verified_historical_road_identity_resolves_current_osm_road():
    target = SurveyTarget(
        state="Andhra Pradesh",
        district="Nellore",
        pincode="524322",
        place_name="Atmakur",
        road_name="SH57",
    )

    geocoder = FakeGeocoder(
        [
            {
                "osm_type": "way",
                "osm_id": 291808170,
                "lat": "14.669176",
                "lon": "79.5743613",
                "display_name": (
                    "NH67, Atmakur, Nellore, "
                    "Andhra Pradesh, 524322, India"
                ),
                "namedetails": {
                    "name": "NH67",
                    "ref": "NH67",
                },
                "address": {
                    "road": "NH67",
                    "postcode": "524322",
                    "district": "Nellore",
                    "state": "Andhra Pradesh",
                },
            }
        ]
    )

    osm = FakeOSM(
        {
            "elements": [
                {
                    "type": "way",
                    "id": 291808170,
                    "tags": {
                        "highway": "trunk",
                        "ref": "NH67",
                    },
                    "geometry": [
                        {
                            "lat": 14.669,
                            "lon": 79.574,
                        },
                        {
                            "lat": 14.670,
                            "lon": 79.575,
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
        expansion_depth=0,
    )

    result = resolver.resolve(
        target=target,
        requested_road="SH57",
        origin_latitude=14.669176,
        origin_longitude=79.5743613,
    )

    assert result is not None
    assert result.requested_name == "SH57"
    assert result.matched_reference == "NH67"
    assert result.osm_way_ids == (291808170,)
    assert result.method == "ROAD_IDENTITY_REGISTRY_SEED"


def test_historical_identity_is_not_cross_applied_to_nandyal_atmakur():
    target = SurveyTarget(
        state="Andhra Pradesh",
        district="Nandyal",
        pincode="518422",
        place_name="Atmakur",
        road_name="SH57",
    )

    geocoder = FakeGeocoder([])

    osm = FakeOSM(
        {
            "elements": []
        }
    )

    resolver = RoadResolver(
        geocoder=geocoder,
        osm_client=osm,
    )

    result = resolver.resolve(
        target=target,
        requested_road="SH57",
        origin_latitude=15.9149208,
        origin_longitude=78.7079658,
    )

    assert result is None