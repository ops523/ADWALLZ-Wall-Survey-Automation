from __future__ import annotations

import argparse
from pathlib import Path

from src.detection.annotation import (
    create_annotation_manifest_from_prep,
    load_annotation_manifest,
    write_annotation_manifest,
)
from src.detection.annotation_tool import run_annotation_server


DATASET_ROOT = Path("data/reference/highrise_wall")
PREP_MANIFEST = DATASET_ROOT / "manifests/annotation_prep_manifest.json"
ANNOTATION_MANIFEST = (
    DATASET_ROOT / "annotations/highrise_wall_annotations.json"
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ADWALLZ High-Rise polygon annotation tool"
    )

    parser.add_argument(
        "--host",
        default="0.0.0.0",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8765,
    )

    args = parser.parse_args()

    if not PREP_MANIFEST.exists():
        raise SystemExit(
            f"Preparation manifest not found: {PREP_MANIFEST}"
        )

    ANNOTATION_MANIFEST.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if ANNOTATION_MANIFEST.exists():
        manifest = load_annotation_manifest(
            ANNOTATION_MANIFEST
        )
    else:
        manifest = create_annotation_manifest_from_prep(
            PREP_MANIFEST
        )

        write_annotation_manifest(
            manifest,
            ANNOTATION_MANIFEST,
        )

        print(
            f"Created annotation manifest: "
            f"{ANNOTATION_MANIFEST}"
        )

    run_annotation_server(
        dataset_root=DATASET_ROOT,
        annotation_manifest_path=ANNOTATION_MANIFEST,
        manifest=manifest,
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
