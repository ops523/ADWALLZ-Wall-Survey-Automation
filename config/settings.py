from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    """
    Application-wide configuration.
    """

    nominatim_url: str = os.getenv(
        "NOMINATIM_URL",
        "https://nominatim.openstreetmap.org/search",
    )

    overpass_url: str = os.getenv(
        "OVERPASS_URL",
        "https://overpass-api.de/api/interpreter",
    )

    osm_user_agent: str = os.getenv(
        "OSM_USER_AGENT",
        "ADWALLZ-Wall-Survey-Automation/1.0",
    )


settings = Settings()
