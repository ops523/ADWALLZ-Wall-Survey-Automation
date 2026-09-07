from __future__ import annotations

import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageOps, UnidentifiedImageError

from src.streetview.models import (
    CanonicalImageAsset,
    DiscoveryResult,
)


DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_DOWNLOAD_BYTES = 15 * 1024 * 1024
DEFAULT_OUTPUT_FORMAT = "JPEG"
DEFAULT_JPEG_QUALITY = 92


class ImageDownloadError(Exception):
    """Raised when an imagery asset cannot be downloaded safely."""


class ImagePreprocessingError(Exception):
    """Raised when downloaded imagery cannot be normalized."""


class ImageDownloader:
    """
    Safe HTTP image downloader.

    This class deliberately knows nothing about imagery providers.
    It receives only a URL and returns validated image bytes.
    """

    def __init__(
        self,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_download_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
        session: requests.Session | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be greater than zero."
            )

        if max_download_bytes <= 0:
            raise ValueError(
                "max_download_bytes must be greater than zero."
            )

        self.timeout_seconds = timeout_seconds
        self.max_download_bytes = max_download_bytes
        self.session = session or requests.Session()

    def download(
        self,
        image_url: str,
    ) -> bytes:
        if not image_url or not image_url.strip():
            raise ImageDownloadError(
                "Image URL is missing."
            )

        try:
            response = self.session.get(
                image_url,
                timeout=self.timeout_seconds,
                stream=True,
            )
            response.raise_for_status()

        except requests.RequestException as exc:
            raise ImageDownloadError(
                f"Image download failed: {exc}"
            ) from exc

        content_type = (
            response.headers.get(
                "Content-Type",
                "",
            )
            .split(";")[0]
            .strip()
            .casefold()
        )

        if content_type and not content_type.startswith(
            "image/"
        ):
            raise ImageDownloadError(
                "URL did not return an image "
                f"content type: {content_type}"
            )

        content_length = response.headers.get(
            "Content-Length"
        )

        if content_length:
            try:
                declared_size = int(content_length)
            except ValueError:
                declared_size = None

            if (
                declared_size is not None
                and declared_size > self.max_download_bytes
            ):
                raise ImageDownloadError(
                    "Image exceeds configured download size limit."
                )

        chunks: list[bytes] = []
        total = 0

        try:
            for chunk in response.iter_content(
                chunk_size=64 * 1024
            ):
                if not chunk:
                    continue

                total += len(chunk)

                if total > self.max_download_bytes:
                    raise ImageDownloadError(
                        "Image exceeds configured download size limit."
                    )

                chunks.append(chunk)

        finally:
            response.close()

        data = b"".join(chunks)

        if not data:
            raise ImageDownloadError(
                "Image response was empty."
            )

        return data


class ImagePreprocessor:
    """
    Convert downloaded imagery into the canonical Pack 3 asset format.

    Canonical output:
    - JPEG
    - EXIF orientation applied
    - RGB color space
    - deterministic quality
    - SHA-256 content hash
    - deterministic asset ID
    """

    def __init__(
        self,
        output_dir: str | Path,
        jpeg_quality: int = DEFAULT_JPEG_QUALITY,
    ) -> None:
        if not 1 <= jpeg_quality <= 100:
            raise ValueError(
                "jpeg_quality must be between 1 and 100."
            )

        self.output_dir = Path(output_dir)
        self.jpeg_quality = jpeg_quality

    def process(
        self,
        discovery: DiscoveryResult,
        *,
        source_side: str | None = None,
        source_point_id: str | None = None,
        image_bytes: bytes,
    ) -> CanonicalImageAsset:
        try:
            image = self._decode(image_bytes)

            normalized = self._normalize(image)

            output_bytes = self._encode(normalized)

            sha256 = hashlib.sha256(
                output_bytes
            ).hexdigest()

            asset_id = self._build_asset_id(
                discovery=discovery,
                sha256=sha256,
                side=source_side,
                point_id=source_point_id,
            )

            output_path = self._write_asset(
                asset_id=asset_id,
                data=output_bytes,
            )

            return CanonicalImageAsset(
                asset_id=asset_id,
                status="READY",
                image_path=str(output_path),
                width=normalized.width,
                height=normalized.height,
                format="JPEG",
                file_size_bytes=len(output_bytes),
                sha256=sha256,
                provider=discovery.provider,
                image_id=discovery.image_id,
                source_latitude=discovery.latitude,
                source_longitude=discovery.longitude,
                image_latitude=discovery.image_latitude,
                image_longitude=discovery.image_longitude,
                requested_heading=_requested_heading(
                    discovery
                ),
                actual_heading=discovery.heading,
                side=source_side,
                capture_date=discovery.capture_date,
                metadata={
                    **discovery.metadata,
                    "source_point_id": source_point_id,
                    "source_side": source_side,
                },
            )

        except (
            OSError,
            UnidentifiedImageError,
            ValueError,
            ImagePreprocessingError,
        ) as exc:
            return CanonicalImageAsset(
                asset_id=self._failed_asset_id(
                    discovery=discovery,
                    side=source_side,
                    point_id=source_point_id,
                ),
                status="INVALID",
                image_path=None,
                width=None,
                height=None,
                format=None,
                file_size_bytes=None,
                sha256=None,
                provider=discovery.provider,
                image_id=discovery.image_id,
                source_latitude=discovery.latitude,
                source_longitude=discovery.longitude,
                image_latitude=discovery.image_latitude,
                image_longitude=discovery.image_longitude,
                requested_heading=_requested_heading(
                    discovery
                ),
                actual_heading=discovery.heading,
                side=source_side,
                capture_date=discovery.capture_date,
                metadata={
                    **discovery.metadata,
                    "source_point_id": source_point_id,
                    "source_side": source_side,
                },
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

    def process_from_url(
        self,
        discovery: DiscoveryResult,
        downloader: ImageDownloader,
        *,
        source_side: str | None = None,
        source_point_id: str | None = None,
    ) -> CanonicalImageAsset:
        """
        Download and process imagery from DiscoveryResult.image_url.

        Missing URLs and download failures become INVALID assets rather
        than crashing the discovery pipeline.
        """

        if not discovery.image_url:
            return self._invalid_download_asset(
                discovery=discovery,
                side=source_side,
                point_id=source_point_id,
                error_type="ImageDownloadError",
                error_message="Image URL is missing.",
            )

        try:
            image_bytes = downloader.download(
                discovery.image_url
            )

        except ImageDownloadError as exc:
            return self._invalid_download_asset(
                discovery=discovery,
                side=source_side,
                point_id=source_point_id,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

        return self.process(
            discovery=discovery,
            source_side=source_side,
            source_point_id=source_point_id,
            image_bytes=image_bytes,
        )

    @staticmethod
    def _decode(
        image_bytes: bytes,
    ) -> Image.Image:
        if not image_bytes:
            raise ImagePreprocessingError(
                "Image bytes are empty."
            )

        try:
            image = Image.open(
                io.BytesIO(image_bytes)
            )

            # Force complete decoding while the source buffer is alive.
            image.load()

            return image

        except (
            UnidentifiedImageError,
            OSError,
            ValueError,
        ) as exc:
            raise ImagePreprocessingError(
                f"Unable to decode image: {exc}"
            ) from exc

    @staticmethod
    def _normalize(
        image: Image.Image,
    ) -> Image.Image:
        try:
            oriented = ImageOps.exif_transpose(
                image
            )

            if oriented.mode in {
                "RGBA",
                "LA",
            }:
                background = Image.new(
                    "RGB",
                    oriented.size,
                    "white",
                )

                if oriented.mode == "RGBA":
                    background.paste(
                        oriented,
                        mask=oriented.getchannel("A"),
                    )
                else:
                    background.paste(
                        oriented.convert("RGBA"),
                        mask=oriented.getchannel("A"),
                    )

                return background

            if oriented.mode != "RGB":
                return oriented.convert("RGB")

            return oriented

        except (
            OSError,
            ValueError,
        ) as exc:
            raise ImagePreprocessingError(
                f"Unable to normalize image: {exc}"
            ) from exc

    def _encode(
        self,
        image: Image.Image,
    ) -> bytes:
        output = io.BytesIO()

        try:
            image.save(
                output,
                format=DEFAULT_OUTPUT_FORMAT,
                quality=self.jpeg_quality,
                optimize=True,
                progressive=False,
                subsampling=0,
            )

        except OSError as exc:
            raise ImagePreprocessingError(
                f"Unable to encode image: {exc}"
            ) from exc

        return output.getvalue()

    def _write_asset(
        self,
        asset_id: str,
        data: bytes,
    ) -> Path:
        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        path = self.output_dir / (
            f"{asset_id}.jpg"
        )

        try:
            path.write_bytes(data)
        except OSError as exc:
            raise ImagePreprocessingError(
                f"Unable to write canonical image: {exc}"
            ) from exc

        return path

    @staticmethod
    def _build_asset_id(
        discovery: DiscoveryResult,
        sha256: str,
        side: str | None,
        point_id: str | None,
    ) -> str:
        payload = {
            "provider": discovery.provider,
            "image_id": discovery.image_id,
            "latitude": discovery.latitude,
            "longitude": discovery.longitude,
            "requested_heading": _requested_heading(
                discovery
            ),
            "actual_heading": discovery.heading,
            "side": side,
            "point_id": point_id,
            "sha256": sha256,
        }

        digest = hashlib.sha256(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("utf-8")
        ).hexdigest()

        return f"img_{digest[:24]}"

    @staticmethod
    def _failed_asset_id(
        discovery: DiscoveryResult,
        side: str | None,
        point_id: str | None,
    ) -> str:
        payload = {
            "provider": discovery.provider,
            "image_id": discovery.image_id,
            "latitude": discovery.latitude,
            "longitude": discovery.longitude,
            "requested_heading": _requested_heading(
                discovery
            ),
            "actual_heading": discovery.heading,
            "side": side,
            "point_id": point_id,
            "url": discovery.image_url,
        }

        digest = hashlib.sha256(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("utf-8")
        ).hexdigest()

        return f"invalid_{digest[:24]}"

    def _invalid_download_asset(
        self,
        discovery: DiscoveryResult,
        side: str | None,
        point_id: str | None,
        error_type: str,
        error_message: str,
    ) -> CanonicalImageAsset:
        return CanonicalImageAsset(
            asset_id=self._failed_asset_id(
                discovery=discovery,
                side=side,
                point_id=point_id,
            ),
            status="INVALID",
            image_path=None,
            width=None,
            height=None,
            format=None,
            file_size_bytes=None,
            sha256=None,
            provider=discovery.provider,
            image_id=discovery.image_id,
            source_latitude=discovery.latitude,
            source_longitude=discovery.longitude,
            image_latitude=discovery.image_latitude,
            image_longitude=discovery.image_longitude,
            requested_heading=_requested_heading(
                discovery
            ),
            actual_heading=discovery.heading,
            side=side,
            capture_date=discovery.capture_date,
            metadata={
                **discovery.metadata,
                "source_point_id": point_id,
                "source_side": side,
            },
            error_type=error_type,
            error_message=error_message,
        )


def _requested_heading(
    discovery: DiscoveryResult,
) -> float | None:
    value = discovery.metadata.get(
        "requested_heading"
    )

    if value is None:
        return None

    try:
        return float(value) % 360.0
    except (TypeError, ValueError):
        return None


def sanitize_asset_component(
    value: str,
) -> str:
    """
    Utility for future human-readable asset paths.

    Asset IDs themselves are hash-based and do not depend on this function.
    """

    cleaned = re.sub(
        r"[^a-zA-Z0-9_-]+",
        "_",
        value.strip(),
    )

    return cleaned.strip("_") or "unknown"
