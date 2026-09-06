import pytest

from src.geocoding.boundary import (
    bbox_dimensions_km,
    radius_bbox,
    tighten_bbox,
    validate_radius_km,
)


def test_radius_must_be_positive():
    with pytest.raises(ValueError):
        validate_radius_km(0)

    with pytest.raises(ValueError):
        validate_radius_km(-1)


def test_radius_has_safety_maximum():
    with pytest.raises(ValueError):
        validate_radius_km(51)


def test_radius_bbox_contains_centre():
    latitude = 15.9149208
    longitude = 78.7079658

    south, north, west, east = radius_bbox(
        latitude,
        longitude,
        5.0,
    )

    assert south < latitude < north
    assert west < longitude < east


def test_tighten_bbox_does_not_expand_original():
    original = (
        15.763355,
        16.0660984,
        78.5334062,
        78.9218129,
    )

    tightened = tighten_bbox(
        original_bbox=original,
        latitude=15.9149208,
        longitude=78.7079658,
        radius_km=5.0,
    )

    south, north, west, east = tightened

    assert south >= original[0]
    assert north <= original[1]
    assert west >= original[2]
    assert east <= original[3]


def test_five_km_radius_creates_roughly_ten_km_box():
    bbox = radius_bbox(
        latitude=15.9149208,
        longitude=78.7079658,
        radius_km=5.0,
    )

    height, width = bbox_dimensions_km(
        bbox
    )

    assert 9.8 <= height <= 10.2
    assert 9.8 <= width <= 10.2
