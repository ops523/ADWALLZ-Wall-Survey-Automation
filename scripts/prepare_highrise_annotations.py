from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.detection.annotation_prep import (
    build_annotation_prep_manifest,
    write_annotation_prep_manifest,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare stable human polygon annotation tasks "
            "from the High-Rise classification manifest."
        )
    )

    parser.add_argument(
        "--classification-manifest",
        default=(
            "data/reference/highrise_wall/"
            "manifests/classification_manifest.json"
        ),
    )

    parser.add_argument(
        "--output",
        default=(
            "data/reference/highrise_wall/"
            "manifests/annotation_prep_manifest.json"
        ),
    )

    args = parser.parse_args()

    classification_path = Path(
        args.classification_manifest
    )

    if not classification_path.is_file():
        raise SystemExit(
            f"Classification manifest not found: "
            f"{classification_path}"
        )

    classification_manifest = json.loads(
        classification_path.read_text(
            encoding="utf-8"
        )
    )

    manifest = build_annotation_prep_manifest(
        classification_manifest
    )

    write_annotation_prep_manifest(
        manifest,
        args.output,
    )

    print(
        "===== HIGH-RISE ANNOTATION PREPARATION ====="
    )
    print(f"Images             : {manifest.image_count}")
    print(f"Positive tasks     : {manifest.positive_count}")
    print(f"Negative tasks     : {manifest.negative_count}")
    print(
        f"Hard-negative      : "
        f"{manifest.hard_negative_count}"
    )
    print(
        f"Pending polygons   : "
        f"{manifest.pending_polygon_count}"
    )
    print("Splits             : unassigned")
    print("Polygons generated : 0")
    print(f"Manifest           : {args.output}")


if __name__ == "__main__":
    main()
