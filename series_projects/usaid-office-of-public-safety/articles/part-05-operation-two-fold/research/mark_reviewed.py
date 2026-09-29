"""Update review status fields without rewriting substantive source notes."""

from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path


LEDGER = Path(__file__).resolve().parent / "CORPUS_REVIEW_LEDGER.csv"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_ids", nargs="+")
    parser.add_argument(
        "--status",
        default="REVIEWED",
        choices=("REVIEWED", "DUPLICATE_REVIEWED", "OCR_BLOCKED"),
    )
    parser.add_argument("--relevance", default="")
    parser.add_argument("--document-type", default="")
    args = parser.parse_args()

    with LEDGER.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    requested = set(args.source_ids)
    found: set[str] = set()
    for row in rows:
        if row["source_id"] not in requested:
            continue
        found.add(row["source_id"])
        row["review_status"] = args.status
        row["reviewed_on"] = date.today().isoformat()
        if args.relevance:
            row["relevance"] = args.relevance
        if args.document_type:
            row["document_type"] = args.document_type

    missing = sorted(requested - found)
    if missing:
        raise SystemExit(f"Unknown source IDs: {', '.join(missing)}")

    with LEDGER.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
