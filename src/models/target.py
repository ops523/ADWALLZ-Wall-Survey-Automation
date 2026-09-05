from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SurveyTarget:
    """
    Geographic target supplied by the operations team.

    Pincode is deliberately part of the target identity because place names
    are not unique across India.
    """

    state: str
    district: str
    pincode: str
    place_name: str
    road_name: str | None = None
    sampling_interval_m: float = 20.0

    def __post_init__(self) -> None:
        if not self.state.strip():
            raise ValueError("state is required")

        if not self.district.strip():
            raise ValueError("district is required")

        if not self.pincode.strip():
            raise ValueError("pincode is required")

        if not self.place_name.strip():
            raise ValueError("place_name is required")

        if not self.pincode.isdigit():
            raise ValueError("pincode must contain digits only")

        if len(self.pincode) != 6:
            raise ValueError("pincode must be exactly 6 digits")

        if self.sampling_interval_m <= 0:
            raise ValueError(
                "sampling_interval_m must be greater than zero"
            )

    @property
    def target_key(self) -> str:
        """
        Stable human-readable target identity.
        """

        return (
            f"{self.state.strip()}|"
            f"{self.district.strip()}|"
            f"{self.pincode.strip()}|"
            f"{self.place_name.strip()}"
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "state": self.state.strip(),
            "district": self.district.strip(),
            "pincode": self.pincode.strip(),
            "place_name": self.place_name.strip(),
            "road_name": (
                self.road_name.strip()
                if self.road_name
                else None
            ),
            "sampling_interval_m": self.sampling_interval_m,
            "target_key": self.target_key,
        }
