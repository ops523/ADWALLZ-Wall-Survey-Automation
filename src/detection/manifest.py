from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.detection.models import (
    BoundingBox,
    DetectionCandidate,
    DetectionResult,
)


class DetectionManifestError(Exception):
    """Raised when the detection manifest cannot be read or written."""


class DetectionManifest:
    """
    Durable JSON manifest for wall/facade detection results.

    The manifest is keyed by canonical asset_id.

    Design goals:
    - deterministic lookup
    - idempotent writes
    - atomic replacement
    - complete detector provenance
    - JSON-compatible in-memory records
    - no framework-specific inference objects
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
            raise DetectionManifestError(
                f"Unable to read detection manifest: {exc}"
            ) from exc

        if not isinstance(payload, dict):
            raise DetectionManifestError(
                "Detection manifest root must be a JSON object."
            )

        detections = payload.get(
            "detections",
            {},
        )

        if not isinstance(detections, dict):
            raise DetectionManifestError(
                "Detection manifest 'detections' must be a JSON object."
            )

        self._data = detections

    def save(
        self,
        result: DetectionResult,
    ) -> None:
        """
        Insert or replace a detection result.

        The asset_id is the stable primary key.

        Saving an identical result does not alter the stored record.
        """

        if not result.asset_id.strip():
            raise ValueError(
                "asset_id is required."
            )

        record = self._serialize(result)
        existing = self._data.get(
            result.asset_id
        )

        if existing is not None:
            existing_without_timestamp = {
                key: value
                for key, value in existing.items()
                if key != "manifest_updated_at"
            }

            record_without_timestamp = {
                key: value
                for key, value in record.items()
                if key != "manifest_updated_at"
            }

            if (
                existing_without_timestamp
                == record_without_timestamp
            ):
                return

        self._data[result.asset_id] = record
        self._write()

    def get(
        self,
        asset_id: str,
    ) -> DetectionResult | None:
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
    ) -> list[DetectionResult]:
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
            "detections": self._data,
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
            raise DetectionManifestError(
                f"Unable to write detection manifest: {exc}"
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
        result: DetectionResult,
    ) -> dict[str, Any]:
        """
        Convert a DetectionResult into a JSON-compatible record.

        DetectionResult deliberately uses tuples for immutable domain
        objects. JSON requires arrays, so candidates and polygons are
        explicitly converted to lists at this boundary.
        """

        record = asdict(result)

        record["candidates"] = [
            {
                **candidate,
                "polygon": (
                    [
                        list(point)
                        for point in candidate["polygon"]
                    ]
                    if candidate["polygon"] is not None
                    else None
                ),
            }
            for candidate in record["candidates"]
        ]

        record["manifest_updated_at"] = _utc_now()

        return record

    @staticmethod
    def _deserialize(
        record: dict[str, Any],
    ) -> DetectionResult:
        raw_candidates = record.get(
            "candidates",
            [],
        )

        if not isinstance(
            raw_candidates,
            (list, tuple),
        ):
            raise DetectionManifestError(
                "Detection record 'candidates' must be a list."
            )

        candidates: list[DetectionCandidate] = []

        for raw_candidate in raw_candidates:
            if not isinstance(
                raw_candidate,
                dict,
            ):
                raise DetectionManifestError(
                    "Detection candidate must be a JSON object."
                )

            raw_box = raw_candidate.get(
                "bounding_box"
            )

            if not isinstance(
                raw_box,
                dict,
            ):
                raise DetectionManifestError(
                    "Detection candidate bounding_box must be a JSON object."
                )

            try:
                box = BoundingBox(
                    left=float(raw_box["left"]),
                    top=float(raw_box["top"]),
                    right=float(raw_box["right"]),
                    bottom=float(raw_box["bottom"]),
                )
            except (
                KeyError,
                TypeError,
                ValueError,
            ) as exc:
                raise DetectionManifestError(
                    "Invalid detection candidate bounding_box."
                ) from exc

            raw_polygon = raw_candidate.get(
                "polygon"
            )

            polygon = None

            if raw_polygon is not None:
                if not isinstance(
                    raw_polygon,
                    (list, tuple),
                ):
                    raise DetectionManifestError(
                        "Detection candidate polygon must be a list."
                    )

                try:
                    polygon = tuple(
                        (
                            float(point[0]),
                            float(point[1]),
                        )
                        for point in raw_polygon
                    )
                except (
                    IndexError,
                    TypeError,
                    ValueError,
                ) as exc:
                    raise DetectionManifestError(
                        "Invalid detection candidate polygon."
                    ) from exc

            candidates.append(
                DetectionCandidate(
                    class_name=raw_candidate[
                        "class_name"
                    ],
                    confidence=float(
                        raw_candidate[
                            "confidence"
                        ]
                    ),
                    bounding_box=box,
                    class_id=raw_candidate.get(
                        "class_id"
                    ),
                    polygon=polygon,
                    metadata=raw_candidate.get(
                        "metadata"
                    ) or {},
                )
            )

        return DetectionResult(
            asset_id=record["asset_id"],
            detector_name=record[
                "detector_name"
            ],
            detector_version=record[
                "detector_version"
            ],
            status=record["status"],
            image_width=record.get(
                "image_width"
            ),
            image_height=record.get(
                "image_height"
            ),
            candidates=tuple(candidates),
            metadata=record.get(
                "metadata"
            ) or {},
            error_type=record.get(
                "error_type"
            ),
            error_message=record.get(
                "error_message"
            ),
        )


def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()
