#!/usr/bin/env python3
"""Reconstruct the frozen IWASS .it cohort from Tranco standard-list CSV."""
from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path

EXPECTED_COUNT = 10022
EXPECTED_SHA256 = "6d57a4bdf1fecc941b5218d88c7b5d5b9980e876f7f5abdb98d4fdbc6db25471"


def filter_tranco_it(path: Path) -> list[tuple[int, str]]:
    """Keep original list ranks and .it domains; do not re-rank the slice."""
    selected = []
    with path.open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.reader(stream):
            if len(row) < 2:
                continue
            try:
                rank = int(row[0])
            except ValueError:
                continue
            domain = row[1].strip().lower()
            if domain.endswith(".it"):
                selected.append((rank, domain))
    if len({domain for _, domain in selected}) != len(selected):
        raise ValueError("Duplicate .it domain found in Tranco input")
    return selected


def encode_frame(rows: list[tuple[int, str]]) -> bytes:
    return "".join(f"{rank},{domain}\n" for rank, domain in rows).encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tranco_csv", type=Path, help="CSV extracted from Tranco list 46XZX")
    parser.add_argument("output_csv", type=Path, help="Path for reconstructed .it frame")
    args = parser.parse_args()
    if args.tranco_csv.resolve() == args.output_csv.resolve():
        parser.error("Input and output paths must differ")
    rows = filter_tranco_it(args.tranco_csv)
    payload = encode_frame(rows)
    sha = hashlib.sha256(payload).hexdigest()
    if len(rows) != EXPECTED_COUNT or sha != EXPECTED_SHA256:
        parser.error(f"Not the frozen IWASS frame: {len(rows)} rows, SHA-256 {sha}; "
                     f"expected {EXPECTED_COUNT} rows and {EXPECTED_SHA256}")
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    args.output_csv.write_bytes(payload)
    print(f"Verified {len(rows)} .it domains; SHA-256 {sha}")


if __name__ == "__main__":
    main()
