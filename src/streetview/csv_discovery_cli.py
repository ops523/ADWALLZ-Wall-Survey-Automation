from __future__ import annotations

import argparse

from src.streetview.csv_processor import (
    process_survey_points,
    read_survey_points,
    write_discovery_csv,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "ADWALLZ — Survey CSV to imagery discovery processor"
        )
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Pack 1A survey-point CSV",
    )

    parser.add_argument(
        "--output",
        default="output/imagery_discovery.csv",
    )

    parser.add_argument(
        "--radius-m",
        type=int,
        default=50,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of survey points to process.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    rows = read_survey_points(
        args.input
    )

    print(
        f"Survey points loaded: {len(rows)}"
    )

    print(
        f"Processing limit: "
        f"{args.limit if args.limit is not None else 'all'}"
    )

    print(
        f"Imagery radius: {args.radius_m}m"
    )

    # Provider construction is intentionally kept outside this module.
    #
    # Pack 2B's existing ImageryDiscovery object should be supplied here
    # once provider configuration is enabled.
    raise RuntimeError(
        "Provider configuration is not wired into this CLI yet. "
        "Use process_survey_points() with an ImageryDiscovery instance."
    )


if __name__ == "__main__":
    main()