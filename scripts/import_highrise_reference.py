from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image


EXPECTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def stable_image_id(path: Path) -> str:
    return path.stem.strip().lower().replace(" ", "_")


def inspect_image(path: Path) -> dict[str, object]:
    with Image.open(path) as image:
        width, height = image.size
        image_format = image.format

    return {
        "image_id": stable_image_id(path),
        "original_filename": path.name,
        "width": width,
        "height": height,
        "format": image_format,
        "file_size_bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()

    source = Path(args.source)
    destination = Path(args.destination)
    manifest_path = Path(args.manifest)

    if not source.is_dir():
        raise SystemExit(f"Source directory does not exist: {source}")

    destination.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    files = sorted(
        path
        for path in source.rglob("*")
        if path.is_file()
        and path.suffix.lower() in EXPECTED_EXTENSIONS
    )

    if not files:
        raise SystemExit("No supported image files found")

    records: list[dict[str, object]] = []

    for source_file in files:
        image_id = stable_image_id(source_file)

        destination_file = destination / f"{image_id}.jpeg"

        shutil.copy2(source_file, destination_file)

        record = inspect_image(destination_file)
        record.update(
            {
                "category": "unclassified",
                "split": "unassigned",
                "scene_group": f"scene-{image_id}",
                "annotation_status": "unannotated",
                "source": "highrise_wall_reference_v1",
                "relative_path": str(
                    destination_file.relative_to(
                        Path("data/reference/highrise_wall")
                    )
                ),
            }
        )

        records.append(record)

    image_ids = [record["image_id"] for record in records]

    if len(image_ids) != len(set(image_ids)):
        raise SystemExit("Duplicate image IDs detected")

    manifest = {
        "dataset_version": "4.2.0",
        "import_version": "4.2A.0",
        "source_archive": "highrise_wall_reference_v1.zip",
        "image_count": len(records),
        "classification_status": "UNCLASSIFIED",
        "annotation_status": "UNANNOTATED",
        "images": records,
    }

    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(
            manifest,
            handle,
            indent=2,
            sort_keys=True,
        )
        handle.write("\n")

    print(f"Imported images : {len(records)}")
    print(f"Manifest        : {manifest_path}")

    for record in records:
        print(
            f"{record['image_id']:12} "
            f"{record['width']}x{record['height']} "
            f"{record['sha256'][:12]}"
        )


if __name__ == "__main__":
    main()
