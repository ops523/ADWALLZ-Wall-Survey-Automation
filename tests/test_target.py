import pytest

from src.models.target import SurveyTarget


def test_valid_target():
    target = SurveyTarget(
        state="Andhra Pradesh",
        district="Nandyal",
        pincode="518422",
        place_name="Atmakur",
    )

    assert target.state == "Andhra Pradesh"
    assert target.district == "Nandyal"
    assert target.pincode == "518422"
    assert target.place_name == "Atmakur"


def test_target_key_contains_pincode():
    target = SurveyTarget(
        state="Andhra Pradesh",
        district="Nandyal",
        pincode="518422",
        place_name="Atmakur",
    )

    assert target.target_key == (
        "Andhra Pradesh|Nandyal|518422|Atmakur"
    )


def test_pincode_required():
    with pytest.raises(ValueError):
        SurveyTarget(
            state="Andhra Pradesh",
            district="Nandyal",
            pincode="",
            place_name="Atmakur",
        )


def test_pincode_must_be_six_digits():
    with pytest.raises(ValueError):
        SurveyTarget(
            state="Andhra Pradesh",
            district="Nandyal",
            pincode="51842",
            place_name="Atmakur",
        )


def test_sampling_interval_must_be_positive():
    with pytest.raises(ValueError):
        SurveyTarget(
            state="Andhra Pradesh",
            district="Nandyal",
            pincode="518422",
            place_name="Atmakur",
            sampling_interval_m=0,
        )
