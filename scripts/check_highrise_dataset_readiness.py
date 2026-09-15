from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.detection.annotation import load_annotation_manifest
from src.detection.dataset_split import assess_dataset_readiness


MANIFEST = (
    ROOT
    / "data"
    / "reference"
    / "highrise_wall"
    / "annotations"
    / "highrise_wall_annotations.json"
)


def main() -> int:
    manifest = load_annotation_manifest(MANIFEST)

    report = assess_dataset_readiness(manifest)

    print(json.dumps(
        report.as_dict(),
        indent=2,
        sort_keys=True,
    ))

    print()
    print(f"Production ready: {report.ready}")
    print(f"Images: {report.image_count}")
    print(f"Positive: {report.positive_count}")
    print(f"Negative: {report.negative_count}")
    print(f"Hard negative: {report.hard_negative_count}")
    print(f"Annotated positive: {report.annotated_positive_count}")
    print(f"No target: {report.no_target_count}")
    print(f"Scene groups: {report.scene_group_count}")

    if report.errors:
        print()
        print("Errors:")
        for error in report.errors:
            print(f"  - {error}")

    if report.warnings:
        print()
        print("Warnings:")
        for warning in report.warnings:
            print(f"  - {warning}")

    if report.ready:
        print()
        print("Dataset readiness: PASS")
    else:
        print()
        print(
            "Dataset readiness: BLOCKED "
            "(expected for the current seed dataset)"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
