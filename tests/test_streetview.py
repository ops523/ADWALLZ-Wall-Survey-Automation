from src.streetview.headings import (
    normalize_heading,
    opposite_heading,
    road_side_headings,
)


def test_heading_normalization():
    assert normalize_heading(360) == 0
    assert normalize_heading(450) == 90
    assert normalize_heading(-90) == 270


def test_opposite_heading():
    assert opposite_heading(0) == 180
    assert opposite_heading(90) == 270
    assert opposite_heading(270) == 90


def test_road_side_headings():
    left, right = road_side_headings(90)

    assert left == 0
    assert right == 180


def test_road_side_headings_wrap():
    left, right = road_side_headings(10)

    assert left == 280
    assert right == 100
