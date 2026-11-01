"""CLI demo: generate a medication safety report.

Usage:
    .venv/bin/python cli.py "lisinopril" "metformin" "ibuprofen"
    .venv/bin/python cli.py --lang Spanish "lisinopril" "warfarin" "aspirin"
"""

import argparse
import json

from src.agents import generate_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Medication safety report generator")
    parser.add_argument("medications", nargs="+", help="Drug names as written on the bottle")
    parser.add_argument("--lang", default="English", help="Preferred language for the report")
    args = parser.parse_args()

    print(f"Checking {len(args.medications)} medication(s)...\n")
    report = generate_report(args.medications, language=args.lang)
    print(json.dumps(report.model_dump(), indent=2))


if __name__ == "__main__":
    main()
