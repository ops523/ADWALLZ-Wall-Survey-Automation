from __future__ import annotations

from src.geocoding.road_identity_registry import (
    DEFAULT_ROAD_IDENTITY_REGISTRY,
    RoadIdentity,
    RoadIdentityRegistry,
)


def test_sh57_maps_to_nh67_for_nellore_atmakur():
    result = DEFAULT_ROAD_IDENTITY_REGISTRY.find(
        requested_reference="State Highway 57",
        state="Andhra Pradesh",
        district="Nellore",
        pincode="524322",
        place_name="Atmakur",
    )

    assert result is not None
    assert result.current_reference == "nh67"
    assert result.matched_historical_reference == "sh57"


def test_sh57_does_not_map_to_nh67_for_nandyal_atmakur():
    result = DEFAULT_ROAD_IDENTITY_REGISTRY.find(
        requested_reference="SH57",
        state="Andhra Pradesh",
        district="Nandyal",
        pincode="518422",
        place_name="Atmakur",
    )

    assert result is None


def test_wrong_pincode_does_not_match():
    result = DEFAULT_ROAD_IDENTITY_REGISTRY.find(
        requested_reference="SH57",
        state="Andhra Pradesh",
        district="Nellore",
        pincode="518422",
        place_name="Atmakur",
    )

    assert result is None


def test_wrong_place_does_not_match():
    result = DEFAULT_ROAD_IDENTITY_REGISTRY.find(
        requested_reference="SH57",
        state="Andhra Pradesh",
        district="Nellore",
        pincode="524323",
        place_name="Another Place",
    )

    assert result is None


def test_unverified_identity_is_never_used():
    registry = RoadIdentityRegistry(
        identities=(
            RoadIdentity(
                requested_reference="SH57",
                historical_references=("SH57",),
                current_references=("NH67",),
                state="Andhra Pradesh",
                district="Nellore",
                pincode="524322",
                place_name="Atmakur",
                verification_status="REVIEW_REQUIRED",
                verification_source="test",
            ),
        )
    )

    result = registry.find(
        requested_reference="SH57",
        state="Andhra Pradesh",
        district="Nellore",
        pincode="524322",
        place_name="Atmakur",
    )

    assert result is None


def test_current_reference_is_returned_from_verified_identity():
    result = DEFAULT_ROAD_IDENTITY_REGISTRY.find(
        requested_reference="SH-57",
        state="Andhra Pradesh",
        district="Nellore",
        pincode="524322",
        place_name="Atmakur",
    )

    assert result is not None
    assert result.current_reference == "nh67"
