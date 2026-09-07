from __future__ import annotations

import hashlib
import io

import requests
from PIL import Image

from src.streetview.models import DiscoveryResult
from src.streetview.preprocessing import (
    ImageDownloadError,
    ImageDownloader,
    ImagePreprocessor,
)


def make_discovery(
    *,
    image_url: str | None = "https://example.com/image.jpg",
    provider: str = "mapillary",
    image_id: str = "12345",
    requested_heading: float = 90.0,
    actual_heading: float | None = 92.5,
) -> DiscoveryResult:
    return DiscoveryResult(
        latitude=15.0,
        longitude=78.0,
        provider=provider,
        status="AVAILABLE",
        image_id=image_id,
        image_latitude=15.0001,
        image_longitude=78.0001,
        capture_date="2026-08-01T10:00:00Z",
        heading=actual_heading,
        image_url=image_url,
        metadata={
            "requested_heading": requested_heading,
        },
    )


def make_image_bytes(
    mode: str = "RGB",
    size: tuple[int, int] = (100, 80),
) -> bytes:
    image = Image.new(
        mode,
        size,
        128,
    )

    output = io.BytesIO()

    if mode == "RGBA":
        image.save(
            output,
            format="PNG",
        )
    else:
        image.save(
            output,
            format="PNG",
        )

    return output.getvalue()


def test_process_creates_canonical_jpeg(tmp_path):
    preprocessor = ImagePreprocessor(
        tmp_path
    )

    result = preprocessor.process(
        discovery=make_discovery(),
        source_side="left",
        source_point_id="point-001",
        image_bytes=make_image_bytes(),
    )

    assert result.status == "READY"
    assert result.format == "JPEG"
    assert result.width == 100
    assert result.height == 80
    assert result.image_path is not None
    assert result.sha256 is not None
    assert result.file_size_bytes is not None
    assert result.provider == "mapillary"
    assert result.image_id == "12345"
    assert result.side == "left"
    assert result.requested_heading == 90.0
    assert result.actual_heading == 92.5

    output = Image.open(
        result.image_path
    )

    assert output.format == "JPEG"
    assert output.mode == "RGB"


def test_process_is_deterministic(tmp_path):
    discovery = make_discovery()
    image_bytes = make_image_bytes()

    first = ImagePreprocessor(
        tmp_path / "one"
    ).process(
        discovery=discovery,
        source_side="left",
        source_point_id="point-001",
        image_bytes=image_bytes,
    )

    second = ImagePreprocessor(
        tmp_path / "two"
    ).process(
        discovery=discovery,
        source_side="left",
        source_point_id="point-001",
        image_bytes=image_bytes,
    )

    assert first.asset_id == second.asset_id
    assert first.sha256 == second.sha256


def test_different_sides_get_different_asset_ids(tmp_path):
    preprocessor = ImagePreprocessor(
        tmp_path
    )

    image_bytes = make_image_bytes()
    discovery = make_discovery()

    left = preprocessor.process(
        discovery=discovery,
        source_side="left",
        source_point_id="point-001",
        image_bytes=image_bytes,
    )

    right = preprocessor.process(
        discovery=discovery,
        source_side="right",
        source_point_id="point-001",
        image_bytes=image_bytes,
    )

    assert left.asset_id != right.asset_id


def test_rgba_image_is_normalized_to_rgb(tmp_path):
    preprocessor = ImagePreprocessor(
        tmp_path
    )

    result = preprocessor.process(
        discovery=make_discovery(),
        image_bytes=make_image_bytes(
            mode="RGBA"
        ),
    )

    assert result.status == "READY"

    output = Image.open(
        result.image_path
    )

    assert output.mode == "RGB"
    assert output.format == "JPEG"


def test_invalid_image_does_not_crash_pipeline(tmp_path):
    preprocessor = ImagePreprocessor(
        tmp_path
    )

    result = preprocessor.process(
        discovery=make_discovery(),
        image_bytes=b"this is not an image",
    )

    assert result.status == "INVALID"
    assert result.image_path is None
    assert result.error_type is not None
    assert result.error_message is not None


def test_missing_url_returns_invalid_asset(tmp_path):
    preprocessor = ImagePreprocessor(
        tmp_path
    )

    result = preprocessor.process_from_url(
        discovery=make_discovery(
            image_url=None
        ),
        downloader=ImageDownloader(),
    )

    assert result.status == "INVALID"
    assert result.error_type == "ImageDownloadError"
    assert result.image_path is None


class FakeResponse:
    def __init__(
        self,
        content: bytes,
        content_type: str = "image/jpeg",
    ):
        self.headers = {
            "Content-Type": content_type,
            "Content-Length": str(len(content)),
        }
        self.content = content
        self.closed = False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=65536):
        yield self.content

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(
        self,
        response: FakeResponse,
    ):
        self.response = response

    def get(self, *args, **kwargs):
        return self.response


def test_downloader_accepts_image_response():
    content = make_image_bytes()

    downloader = ImageDownloader(
        session=FakeSession(
            FakeResponse(content)
        )
    )

    result = downloader.download(
        "https://example.com/image.jpg"
    )

    assert result == content


def test_downloader_rejects_non_image_content():
    response = FakeResponse(
        b"not an image",
        content_type="text/html",
    )

    downloader = ImageDownloader(
        session=FakeSession(response)
    )

    try:
        downloader.download(
            "https://example.com/image.jpg"
        )
    except ImageDownloadError as exc:
        assert "did not return an image" in str(exc)
    else:
        raise AssertionError(
            "Expected ImageDownloadError"
        )


def test_downloader_enforces_size_limit():
    content = b"x" * 100

    downloader = ImageDownloader(
        max_download_bytes=50,
        session=FakeSession(
            FakeResponse(content)
        ),
    )

    try:
        downloader.download(
            "https://example.com/image.jpg"
        )
    except ImageDownloadError as exc:
        assert "size limit" in str(exc)
    else:
        raise AssertionError(
            "Expected ImageDownloadError"
        )


def test_sha256_matches_canonical_output(tmp_path):
    preprocessor = ImagePreprocessor(
        tmp_path
    )

    result = preprocessor.process(
        discovery=make_discovery(),
        image_bytes=make_image_bytes(),
    )

    data = open(
        result.image_path,
        "rb",
    ).read()

    expected = hashlib.sha256(
        data
    ).hexdigest()

    assert result.sha256 == expected


def test_process_from_url_downloads_and_processes(
    tmp_path,
):
    image_bytes = make_image_bytes()

    preprocessor = ImagePreprocessor(
        tmp_path
    )

    downloader = ImageDownloader(
        session=FakeSession(
            FakeResponse(image_bytes)
        )
    )

    result = preprocessor.process_from_url(
        discovery=make_discovery(),
        downloader=downloader,
        source_side="right",
        source_point_id="point-002",
    )

    assert result.status == "READY"
    assert result.side == "right"
    assert result.image_path is not None


def test_requested_and_actual_heading_are_preserved(
    tmp_path,
):
    discovery = make_discovery(
        requested_heading=270.0,
        actual_heading=266.0,
    )

    result = ImagePreprocessor(
        tmp_path
    ).process(
        discovery=discovery,
        source_side="right",
        source_point_id="point-003",
        image_bytes=make_image_bytes(),
    )

    assert result.requested_heading == 270.0
    assert result.actual_heading == 266.0
