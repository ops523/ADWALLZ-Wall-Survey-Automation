from __future__ import annotations

import json

import pytest

from src.streetview.manifest import (
    AssetManifest,
    AssetManifestError,
)
from src.streetview.models import (
    CanonicalImageAsset,
)


def make_asset(
    asset_id: str = "img_123",
    status: str = "READY",
) -> CanonicalImageAsset:
    return CanonicalImageAsset(
        asset_id=asset_id,
        status=status,
        image_path="/assets/img_123.jpg",
        width=1200,
        height=800,
        format="JPEG",
        file_size_bytes=12345,
        sha256="abc123",
        provider="mapillary",
        image_id="image-001",
        source_latitude=15.0,
        source_longitude=78.0,
        image_latitude=15.0001,
        image_longitude=78.0001,
        requested_heading=90.0,
        actual_heading=92.0,
        side="left",
        capture_date="2026-08-01T10:00:00Z",
        metadata={
            "source_point_id": "point-001",
            "source_side": "left",
        },
    )


def test_manifest_saves_and_loads_asset(
    tmp_path,
):
    path = tmp_path / "manifest.json"

    manifest = AssetManifest(path)
    asset = make_asset()

    manifest.save(asset)

    assert manifest.exists("img_123")
    assert manifest.count() == 1

    loaded = manifest.get("img_123")

    assert loaded == asset


def test_manifest_persists_across_instances(
    tmp_path,
):
    path = tmp_path / "manifest.json"

    AssetManifest(path).save(
        make_asset()
    )

    reopened = AssetManifest(path)

    loaded = reopened.get(
        "img_123"
    )

    assert loaded is not None
    assert loaded.provider == "mapillary"
    assert loaded.image_id == "image-001"
    assert loaded.side == "left"
    assert loaded.requested_heading == 90.0
    assert loaded.actual_heading == 92.0


def test_manifest_write_is_idempotent(
    tmp_path,
):
    path = tmp_path / "manifest.json"

    manifest = AssetManifest(path)
    asset = make_asset()

    manifest.save(asset)
    first = path.read_text(
        encoding="utf-8"
    )

    manifest.save(asset)
    second = path.read_text(
        encoding="utf-8"
    )

    assert manifest.count() == 1

    first_payload = json.loads(first)
    second_payload = json.loads(second)

    assert (
        first_payload["assets"]
        == second_payload["assets"]
    )


def test_manifest_replaces_existing_asset(
    tmp_path,
):
    path = tmp_path / "manifest.json"

    manifest = AssetManifest(path)

    original = make_asset(
        status="READY"
    )

    replacement = make_asset(
        status="INVALID"
    )

    manifest.save(original)
    manifest.save(replacement)

    assert manifest.count() == 1
    assert (
        manifest.get("img_123").status
        == "INVALID"
    )


def test_manifest_returns_none_for_unknown_asset(
    tmp_path,
):
    manifest = AssetManifest(
        tmp_path / "manifest.json"
    )

    assert manifest.get(
        "does_not_exist"
    ) is None


def test_manifest_remove(
    tmp_path,
):
    manifest = AssetManifest(
        tmp_path / "manifest.json"
    )

    manifest.save(
        make_asset()
    )

    assert manifest.remove(
        "img_123"
    ) is True

    assert manifest.count() == 0
    assert manifest.get(
        "img_123"
    ) is None

    assert manifest.remove(
        "img_123"
    ) is False


def test_manifest_all_returns_assets(
    tmp_path,
):
    manifest = AssetManifest(
        tmp_path / "manifest.json"
    )

    manifest.save(
        make_asset("img_1")
    )
    manifest.save(
        make_asset("img_2")
    )

    assets = manifest.all()

    assert len(assets) == 2
    assert {
        asset.asset_id
        for asset in assets
    } == {
        "img_1",
        "img_2",
    }


def test_manifest_rejects_invalid_root(
    tmp_path,
):
    path = tmp_path / "manifest.json"

    path.write_text(
        json.dumps(["invalid"]),
        encoding="utf-8",
    )

    with pytest.raises(
        AssetManifestError,
        match="root",
    ):
        AssetManifest(path)


def test_manifest_rejects_invalid_assets_section(
    tmp_path,
):
    path = tmp_path / "manifest.json"

    path.write_text(
        json.dumps(
            {
                "version": 1,
                "assets": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        AssetManifestError,
        match="assets",
    ):
        AssetManifest(path)


def test_manifest_requires_asset_id(
    tmp_path,
):
    manifest = AssetManifest(
        tmp_path / "manifest.json"
    )

    asset = make_asset(
        asset_id=""
    )

    with pytest.raises(
        ValueError,
        match="asset_id",
    ):
        manifest.save(asset)


def test_manifest_preserves_error_information(
    tmp_path,
):
    manifest = AssetManifest(
        tmp_path / "manifest.json"
    )

    asset = CanonicalImageAsset(
        asset_id="invalid_123",
        status="INVALID",
        image_path=None,
        width=None,
        height=None,
        format=None,
        file_size_bytes=None,
        sha256=None,
        provider="mapillary",
        image_id="bad-image",
        source_latitude=15.0,
        source_longitude=78.0,
        image_latitude=None,
        image_longitude=None,
        requested_heading=180.0,
        actual_heading=None,
        side="right",
        capture_date=None,
        metadata={
            "source_point_id": "point-999",
        },
        error_type="ImageDownloadError",
        error_message="Image URL is missing.",
    )

    manifest.save(asset)

    loaded = manifest.get(
        "invalid_123"
    )

    assert loaded is not None
    assert loaded.status == "INVALID"
    assert (
        loaded.error_type
        == "ImageDownloadError"
    )
    assert (
        loaded.error_message
        == "Image URL is missing."
    )
    assert loaded.side == "right"
