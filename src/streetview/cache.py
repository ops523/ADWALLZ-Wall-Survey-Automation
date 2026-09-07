from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ImageryCache:
    def __init__(
        self,
        path: str | Path,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._data: dict[str, Any] = {}

        if self.path.exists():
            self._load()

    def _load(self) -> None:
        try:
            payload = json.loads(
                self.path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            json.JSONDecodeError,
            OSError,
        ):
            payload = {}

        if isinstance(payload, dict):
            self._data = payload

    @staticmethod
    def make_key(
        provider: str,
        latitude: float,
        longitude: float,
        radius_m: int,
        heading: float | None = None,
    ) -> str:
        """
        Build a cache key.

        Heading is optional for backward compatibility.

        - heading=None preserves the original cache-key format.
        - heading-aware requests receive a separate cache entry.
        """

        base = (
            f"{provider}:"
            f"{latitude:.7f}:"
            f"{longitude:.7f}:"
            f"{radius_m}"
        )

        if heading is None:
            return base

        normalized_heading = float(heading) % 360.0

        return (
            f"{base}:"
            f"{normalized_heading:.1f}"
        )

    def get(
        self,
        provider: str,
        latitude: float,
        longitude: float,
        radius_m: int,
        heading: float | None = None,
    ) -> dict[str, Any] | None:
        key = self.make_key(
            provider=provider,
            latitude=latitude,
            longitude=longitude,
            radius_m=radius_m,
            heading=heading,
        )

        return self._data.get(key)

    def set(
        self,
        provider: str,
        latitude: float,
        longitude: float,
        radius_m: int,
        value: dict[str, Any],
        heading: float | None = None,
    ) -> None:
        key = self.make_key(
            provider=provider,
            latitude=latitude,
            longitude=longitude,
            radius_m=radius_m,
            heading=heading,
        )

        self._data[key] = value

        self.path.write_text(
            json.dumps(
                self._data,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
