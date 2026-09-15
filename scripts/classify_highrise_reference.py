from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

from PIL import Image


CLASSIFICATION = {
    "positive": (
        "1", "2", "3", "4", "5",
        "9", "10", "11", "19", "23",
    ),
    "hard_negative": (
        "6", "12", "14",
    ),
    "negative": (
        "7", "8", "10a", "13", "15", "16",
        "17", "18", "20", "21", "22", "24",
    ),
}


RATIONALE = {
    "positive": (
        "Contains a visually plausible High-Rise wall/facade surface "
        "consistent with the supplied execution references."
    ),
    "hard_negative": (
        "Contains a wall/facade-like surface that could confuse a detector "
        "but is not treated as a confirmed High-Rise target."
    ),
    "negative": (
        "No confirmed High-Rise target surface; scene is dominated by "
        "ground-floor frontage, signage, street context, or unsuitable "
        "surface."
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def sort_key(path: Path) -> tuple[int, str]:
    stem = path.stem

    if stem == "10a":
        return (10, stem)

    if stem.isdigit():
        return (int(stem), stem)

    return (999, stem)


def find_images(source_dir: Path) -> list[Path]:
    files = [
        path
        for path in source_dir.rglob("*")
        if path.is_file()
        and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    ]

    return sorted(files, key=sort_key)


def build_lookup(files: list[Path]) -> dict[str, Path]:
    lookup: dict[str, Path] = {}

    for path in files:
        stem = path.stem.lower()

        if stem in lookup:
            raise ValueError(
                f"duplicate image stem detected: {stem}"
            )

        lookup[stem] = path

    return lookup


def extract_zip(zip_path: Path, destination: Path) -> Path:
    if not zip_path.is_file():
        raise FileNotFoundError(str(zip_path))

    destination.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(destination)

    return destination


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--source",
        required=True,
        help="Directory containing the extracted reference images.",
    )

    parser.add_argument(
        "--destination",
        required=True,
        help="Dataset root.",
    )

    parser.add_argument(
        "--archive",
        default=None,
        help="Optional source ZIP to preserve in the dataset.",
    )

    args = parser.parse_args()

    source = Path(args.source)
    root = Path(args.destination)

    if not source.is_dir():
        raise SystemExit(
            f"Source directory does not exist: {source}"
        )

    files = find_images(source)

    if len(files) != 25:
        raise SystemExit(
            f"Expected 25 reference images, found {len(files)}"
        )

    lookup = build_lookup(files)

    expected = {
        image_id
        for values in CLASSIFICATION.values()
        for image_id in values
    }

    actual = set(lookup)

    if actual != expected:
        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)

        raise SystemExit(
            f"Reference image mismatch. "
            f"Missing={missing}, unexpected={unexpected}"
        )

    if args.archive:
        archive = Path(args.archive)

        if archive.is_file():
            archive_destination = (
                root
                / "source"
                / "highrise_wall_reference_v1.zip"
            )

            archive_destination.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            if archive.resolve() != archive_destination.resolve():
                shutil.copy2(
                    archive,
                    archive_destination,
                )

    records: list[dict[str, object]] = []

    for category, image_ids in CLASSIFICATION.items():
        destination_dir = root / "images" / category
        destination_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        for image_id in image_ids:
            source_file = lookup[image_id]
            destination_file = (
                destination_dir / source_file.name
            )

            shutil.copy2(
                source_file,
                destination_file,
            )

            with Image.open(destination_file) as image:
                width, height = image.size
                image_format = image.format

            records.append(
                {
                    "image_id": image_id,
                    "original_filename": source_file.name,
                    "relative_path": str(
                        destination_file.relative_to(root)
                    ),
                    "category": category,
                    "split": "unassigned",
                    "scene_group": f"scene-{image_id}",
                    "width": width,
                    "height": height,
                    "format": image_format,
                    "file_size_bytes": (
                        destination_file.stat().st_size
                    ),
                    "sha256": sha256(destination_file),
                    "source": "highrise_wall_reference_v1",
                    "annotation_status": "unannotated",
                    "classification_basis": RATIONALE[category],
                }
            )

    records.sort(key=lambda record: sort_key(
        Path(str(record["original_filename"]))
    ))

    counts = {
        category: sum(
            record["category"] == category
            for record in records
        )
        for category in (
            "positive",
            "negative",
            "hard_negative",
        )
    }

    manifest = {
        "dataset_version": "4.2.0",
        "classification_version": "4.2B.0",
        "classification_status": "FIRST_PASS_REVIEWABLE",
        "source_archive": "highrise_wall_reference_v1.zip",
        "image_count": len(records),
        "counts": counts,
        "images": records,
    }

    manifest_path = (
        root
        / "manifests"
        / "classification_manifest.json"
    )

    manifest_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print("===== HIGH-RISE REFERENCE CLASSIFICATION =====")
    print(f"Images imported : {len(records)}")
    print(f"Positive        : {counts['positive']}")
    print(f"Negative        : {counts['negative']}")
    print(f"Hard negative   : {counts['hard_negative']}")
    print(f"Manifest        : {manifest_path}")
    print()
    print("===== CLASSIFICATION =====")

    for record in records:
        print(
            f"{record['image_id']:>3}  "
            f"{record['category']:<14} "
            f"{record['width']}x{record['height']}"
        )


if __name__ == "__main__":
    main()
