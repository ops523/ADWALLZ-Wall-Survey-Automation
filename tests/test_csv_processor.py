from pathlib import Path

import pytest

from src.streetview.csv_processor import (
    process_survey_points,
    read_survey_points,
    write_discovery_csv,
)


class FakeResult:
    provider = "fake"
    status = "AVAILABLE"
    image_id = "image-123"
    image_latitude = 15.915
    image_longitude = 78.708
    capture_date = "2026-09-07"
    heading = 92.5
    image_url = "https://example.com/image.jpg"


class FakeDiscovery:
    def __init__(self):
        self.calls = []

    def discover(
        self,
        latitude,
        longitude,
        radius_m,
    ):
        self.calls.append(
            (
                latitude,
                longitude,
                radius_m,
            )
        )
        return FakeResult()


def sample_row():
    return {
        "point_id": "SP-000001",
        "state": "Andhra Pradesh",
        "district": "Nandyal",
        "pincode": "518422",
        "place_name": "Atmakur",
        "road_name": "State Highway 57",
        "road_type": "primary",
        "osm_way_id": "12345",
        "latitude": "15.9149208",
        "longitude": "78.7079658",
        "road_bearing": "90.0",
        "heading_left": "0.0",
        "heading_right": "180.0",
        "sample_distance_m": "20.0",
    }


def test_process_survey_points_preserves_identity():
    discovery = FakeDiscovery()

    records = process_survey_points(
        [sample_row()],
        discovery,
        radius_m=50,
    )

    assert len(records) == 1

    record = records[0]

    assert record["point_id"] == "SP-000001"
    assert record["state"] == "Andhra Pradesh"
    assert record["district"] == "Nandyal"
    assert record["pincode"] == "518422"
    assert record["place_name"] == "Atmakur"

    assert record["latitude"] == 15.9149208
    assert record["longitude"] == 78.7079658

    assert record["heading_left"] == "0.0"
    assert record["heading_right"] == "180.0"


def test_process_survey_points_records_imagery():
    discovery = FakeDiscovery()

    records = process_survey_points(
        [sample_row()],
        discovery,
    )

    record = records[0]

    assert record["provider"] == "fake"
    assert record["status"] == "AVAILABLE"
    assert record["image_id"] == "image-123"
    assert record["image_latitude"] == 15.915
    assert record["image_longitude"] == 78.708
    assert record["capture_date"] == "2026-09-07"
    assert record["image_heading"] == 92.5


def test_process_survey_points_calls_discovery_once():
    discovery = FakeDiscovery()

    rows = [
        sample_row(),
        {
            **sample_row(),
            "point_id": "SP-000002",
            "latitude": "15.9151000",
        },
    ]

    process_survey_points(
        rows,
        discovery,
        radius_m=50,
    )

    assert len(discovery.calls) == 2
    assert discovery.calls[0] == (
        15.9149208,
        78.7079658,
        50,
    )


def test_process_survey_points_limit():
    discovery = FakeDiscovery()

    rows = [
        sample_row(),
        {
            **sample_row(),
            "point_id": "SP-000002",
        },
    ]

    records = process_survey_points(
        rows,
        discovery,
        limit=1,
    )

    assert len(records) == 1
    assert records[0]["point_id"] == "SP-000001"
    assert len(discovery.calls) == 1


def test_process_survey_points_requires_pincode():
    discovery = FakeDiscovery()

    row = sample_row()
    row["pincode"] = ""

    with pytest.raises(ValueError, match="pincode"):
        process_survey_points(
            [row],
            discovery,
        )


def test_process_survey_points_rejects_invalid_coordinates():
    discovery = FakeDiscovery()

    row = sample_row()
    row["latitude"] = "200"

    with pytest.raises(
        ValueError,
        match="latitude",
    ):
        process_survey_points(
            [row],
            discovery,
        )


def test_write_discovery_csv(tmp_path: Path):
    output = tmp_path / "imagery.csv"

    records = [
        {
            "point_id": "SP-000001",
            "state": "Andhra Pradesh",
            "district": "Nandyal",
            "pincode": "518422",
            "place_name": "Atmakur",
            "road_name": "State Highway 57",
            "provider": "fake",
            "status": "AVAILABLE",
        }
    ]

    result = write_discovery_csv(
        records,
        output,
    )

    assert result == output
    assert output.exists()

    contents = output.read_text(
        encoding="utf-8"
    )

    assert "point_id" in contents
    assert "SP-000001" in contents
    assert "518422" in contents


def test_read_survey_points_requires_identity_fields(
    tmp_path: Path,
):
    path = tmp_path / "bad.csv"

    path.write_text(
        "point_id,latitude,longitude\n"
        "SP-000001,15.9,78.7\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="missing required fields",
    ):
        read_survey_points(path)