from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.streetview.models import CanonicalImageAsset


class AssetManifestError(Exception):
    """Raised when the asset manifest cannot be read or written."""


class AssetManifest:
    """
    Durable JSON manifest for canonical imagery assets.

    The manifest is keyed by deterministic asset_id.

    Design goals:
    - deterministic lookup
    - idempotent writes
    - atomic replacement
    - no silent corruption
    - preserve complete asset provenance
    """

    def __init__(
        self,
        path: str | Path,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._data: dict[str, dict[str, Any]] = {}

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
            OSError,
            json.JSONDecodeError,
        ) as exc:
            raise AssetManifestError(
                f"Unable to read asset manifest: {exc}"
            ) from exc

        if not isinstance(payload, dict):
            raise AssetManifestError(
                "Asset manifest root must be a JSON object."
            )

        assets = payload.get("assets", {})

        if not isinstance(assets, dict):
            raise AssetManifestError(
                "Asset manifest 'assets' must be a JSON object."
            )

        self._data = assets


    def save(
        self,
        asset: CanonicalImageAsset,
    ) -> None:

        if not asset.asset_id.strip():
            raise ValueError(
                "asset_id is required."
            )

        record = self._serialize(asset)

        existing = self._data.get(asset.asset_id)

        if existing == record:
            return

        if existing is not None:
            record["manifest_updated_at"] = existing.get(
                "manifest_updated_at"
            )

        self._data[asset.asset_id] = record

        self._write()

    def get(
        self,
        asset_id: str,
    ) -> CanonicalImageAsset | None:
        record = self._data.get(asset_id)

        if record is None:
            return None

        return self._deserialize(record)

    def exists(
        self,
        asset_id: str,
    ) -> bool:
        return asset_id in self._data

    def all(
        self,
    ) -> list[CanonicalImageAsset]:
        return [
            self._deserialize(record)
            for record in self._data.values()
        ]

    def count(self) -> int:
        return len(self._data)

    def remove(
        self,
        asset_id: str,
    ) -> bool:
        if asset_id not in self._data:
            return False

        del self._data[asset_id]
        self._write()
        return True

    def _write(self) -> None:
        payload = {
            "version": 1,
            "updated_at": _utc_now(),
            "assets": self._data,
        }

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary_path: Path | None = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(
                    handle.name
                )

                json.dump(
                    payload,
                    handle,
                    indent=2,
                    ensure_ascii=False,
                    sort_keys=True,
                )

                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(
                temporary_path,
                self.path,
            )

            temporary_path = None

        except OSError as exc:
            raise AssetManifestError(
                f"Unable to write asset manifest: {exc}"
            ) from exc

        finally:
            if (
                temporary_path is not None
                and temporary_path.exists()
            ):
                try:
                    temporary_path.unlink()
                except OSError:
                    pass

    @staticmethod
    def _serialize(
        asset: CanonicalImageAsset,
    ) -> dict[str, Any]:
        record = asdict(asset)

        record["manifest_updated_at"] = _utc_now()

        return record

    @staticmethod
    def _deserialize(
        record: dict[str, Any],
    ) -> CanonicalImageAsset:
        fields = {
            "asset_id",
            "status",
            "image_path",
            "width",
            "height",
            "format",
            "file_size_bytes",
            "sha256",
            "provider",
            "image_id",
            "source_latitude",
            "source_longitude",
            "image_latitude",
            "image_longitude",
            "requested_heading",
            "actual_heading",
            "side",
            "capture_date",
            "metadata",
            "error_type",
            "error_message",
        }

        values = {
            key: record.get(key)
            for key in fields
        }

        if values["metadata"] is None:
            values["metadata"] = {}

        return CanonicalImageAsset(
            **values
        )


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat()
    )
