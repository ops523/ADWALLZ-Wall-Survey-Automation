from __future__ import annotations

from dataclasses import dataclass

import requests

from config.settings import settings
from src.models.target import SurveyTarget


@dataclass(frozen=True)
class GeocodedTarget:
    """
    Geographic result returned by Nominatim.
    """

    target: SurveyTarget
    latitude: float
    longitude: float
    display_name: str
    osm_type: str | None
    osm_id: int | None
    bounding_box: tuple[float, float, float, float] | None
    address: dict[str, str]

    @property
    def bbox(self) -> tuple[float, float, float, float] | None:
        return self.bounding_box


class NominatimClient:
    """
    Client for OpenStreetMap Nominatim.
    """

    def __init__(
        self,
        url: str | None = None,
        user_agent: str | None = None,
        session=None,
    ) -> None:
        self.url = url or settings.nominatim_url
        self.user_agent = user_agent or settings.osm_user_agent
        self.session = session or requests.Session()

    def search(
        self,
        target: SurveyTarget,
    ) -> list[dict]:
        query = (
            f"{target.place_name}, "
            f"{target.district}, "
            f"{target.state}, "
            f"{target.pincode}, India"
        )

        params = {
            "q": query,
            "format": "jsonv2",
            "addressdetails": 1,
            "limit": 10,
            "countrycodes": "in",
        }

        response = self.session.get(
            self.url,
            params=params,
            headers={
                "User-Agent": self.user_agent,
            },
            timeout=60,
        )

        response.raise_for_status()

        return response.json()

    def resolve(
        self,
        target: SurveyTarget,
    ) -> GeocodedTarget:
        results = self.search(target)

        if not results:
            raise ValueError(
                "Nominatim could not resolve target: "
                f"{target.target_key}"
            )

        result = self._select_best_result(
            results,
            target,
        )

        lat = float(result["lat"])
        lon = float(result["lon"])

        bbox = None

        raw_bbox = result.get("boundingbox")

        if raw_bbox and len(raw_bbox) == 4:
            bbox = (
                float(raw_bbox[0]),
                float(raw_bbox[1]),
                float(raw_bbox[2]),
                float(raw_bbox[3]),
            )

        return GeocodedTarget(
            target=target,
            latitude=lat,
            longitude=lon,
            display_name=result.get(
                "display_name",
                "",
            ),
            osm_type=result.get("osm_type"),
            osm_id=(
                int(result["osm_id"])
                if result.get("osm_id") is not None
                else None
            ),
            bounding_box=bbox,
            address={
                str(k): str(v)
                for k, v in (
                    result.get("address") or {}
                ).items()
            },
        )

    @staticmethod
    def _select_best_result(
        results: list[dict],
        target: SurveyTarget,
    ) -> dict:
        target_state = (
            target.state.casefold().strip()
        )

        target_district = (
            target.district.casefold().strip()
        )

        target_place = (
            target.place_name.casefold().strip()
        )

        target_pincode = target.pincode.strip()

        scored: list[tuple[int, dict]] = []

        for result in results:
            address = result.get("address") or {}

            score = 0

            result_postcode = str(
                address.get("postcode", "")
            ).strip()

            if result_postcode == target_pincode:
                score += 100

            result_state = str(
                address.get("state", "")
            ).casefold().strip()

            if target_state and target_state in result_state:
                score += 30

            district_values = [
                address.get("state_district"),
                address.get("district"),
                address.get("county"),
            ]

            district_text = " ".join(
                str(value or "").casefold()
                for value in district_values
            )

            if (
                target_district
                and target_district in district_text
            ):
                score += 30

            place_values = [
                address.get("city"),
                address.get("town"),
                address.get("village"),
                address.get("municipality"),
                address.get("suburb"),
            ]

            place_text = " ".join(
                str(value or "").casefold()
                for value in place_values
            )

            if target_place and target_place in place_text:
                score += 40

            display_name = str(
                result.get("display_name", "")
            ).casefold()

            if target_place and target_place in display_name:
                score += 10

            scored.append(
                (score, result)
            )

        scored.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        best_score, best_result = scored[0]

        if best_score < 40:
            raise ValueError(
                "Could not confidently match target using "
                "State + District + Pincode + Place. "
                f"Target: {target.target_key}"
            )

        return best_result
