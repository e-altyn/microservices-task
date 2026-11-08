"""Prepare a reproducible sample from the complete Lending Club CSV."""
import argparse
import csv
import json
import random
from collections import Counter
from itertools import islice
from pathlib import Path

COLUMNS = ["loan_amnt", "int_rate", "annual_inc", "dti", "revol_util", "term", "home_ownership", "purpose", "loan_status", "issue_d"]
MONTHS = {name: index for index, name in enumerate(
    ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}


def issue_month(value):
    month, year = value.split("-")
    return f"{int(year):04d}-{MONTHS[month]:02d}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/lending_club_sample.csv"))
    parser.add_argument("--rows", type=int, default=10000)
    parser.add_argument("--scan-rows", type=int, default=None,
                        help="Optional prefix limit; by default scan the complete file")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.rows < 40 or (args.scan_rows is not None and args.scan_rows < args.rows):
        parser.error("rows must be >= 40 and scan-rows, when set, must be >= rows")
    rng, selected, eligible, scanned = random.Random(args.seed), [], 0, 0
    with args.input.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or set(COLUMNS) - set(reader.fieldnames):
            parser.error("Missing required columns: " + str(set(COLUMNS) - set(reader.fieldnames or [])))
        for row in islice(reader, args.scan_rows):
            scanned += 1
            if None in row or any(row.get(key) is None for key in COLUMNS):
                continue
            if row["loan_status"] not in {"Fully Paid", "Charged Off"}:
                continue
            eligible += 1
            record = {key: row[key] for key in COLUMNS}
            if len(selected) < args.rows:
                selected.append(record)
            else:
                index = rng.randrange(eligible)
                if index < args.rows:
                    selected[index] = record
    if len(selected) < args.rows:
        parser.error(f"Only {len(selected)} eligible records; reduce rows or remove the scan limit")
    rng.shuffle(selected)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(selected)
    missing = {column: sum(not row[column].strip() for row in selected) for column in COLUMNS}
    info = {"source": "https://www.kaggle.com/datasets/adarshsng/lending-club-loan-data-csv",
            "sampling": "reservoir sample from all eligible rows, then shuffle" if args.scan_rows is None
                        else "reservoir sample from a bounded prefix, then shuffle",
            "source_complete": args.scan_rows is None,
            "seed": args.seed, "scanned_rows": scanned, "eligible_rows": eligible, "rows": len(selected),
            "sample_issue_date_range": [min(issue_month(row["issue_d"]) for row in selected),
                                        max(issue_month(row["issue_d"]) for row in selected)],
            "sample_missing_values": {column: count for column, count in missing.items() if count},
            "class_counts": dict(Counter(row["loan_status"] for row in selected))}
    args.output.with_suffix(".meta.json").write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
