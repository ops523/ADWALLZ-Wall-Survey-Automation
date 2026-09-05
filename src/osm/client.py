from __future__ import annotations

import requests

from config.settings import settings


class OverpassClient:
    """
    Client for the Overpass API.
    """

    def __init__(
        self,
        url: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.url = url or settings.overpass_url
        self.user_agent = user_agent or settings.osm_user_agent

    def query(self, query: str) -> dict:
        response = requests.post(
            self.url,
            data={"data": query},
            headers={"User-Agent": self.user_agent},
            timeout=180,
        )

        response.raise_for_status()

        return response.json()
