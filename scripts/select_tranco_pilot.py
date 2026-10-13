#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from pathlib import Path


def load_tld_rows(path: Path, suffix: str) -> list[tuple[int, str]]:
    rows: list[tuple[int, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for parts in csv.reader(handle):
            if len(parts) < 2:
                continue
            try:
                rank = int(parts[0])
            except ValueError:
                continue
            domain = parts[1].strip().lower()
            if domain.endswith(suffix):
                rows.append((rank, domain))
    return rows


def evenly_spaced(rows: list[tuple[int, str]], count: int) -> list[tuple[int, str]]:
    if count < 1:
        raise ValueError("count must be >= 1")
    if not rows:
        return []
    if count == 1:
        return [rows[0]]
    if count >= len(rows):
        return rows.copy()
    indices = [round(i * (len(rows) - 1) / (count - 1)) for i in range(count)]
    return [rows[index] for index in indices]


def random_sample(rows: list[tuple[int, str]], count: int, seed: int) -> list[tuple[int, str]]:
    if count < 1:
        raise ValueError("count must be >= 1")
    if count >= len(rows):
        return rows.copy()
    selected = random.Random(seed).sample(rows, count)
    return sorted(selected, key=lambda row: row[0])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("tranco_csv", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--suffix", default=".it")
    parser.add_argument("--tranco-id")
    parser.add_argument("--list-date")
    parser.add_argument(
        "--method",
        choices=("evenly-spaced", "random"),
        default="evenly-spaced",
    )
    parser.add_argument("--seed", type=int, default=20261007)
    args = parser.parse_args()

    rows = load_tld_rows(args.tranco_csv, args.suffix.lower())
    if args.method == "random":
        selected = random_sample(rows, args.count, args.seed)
        selection_method = "random_without_replacement"
    else:
        selected = evenly_spaced(rows, args.count)
        selection_method = "evenly_spaced_over_filtered_rank_order"
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    args.output_csv.write_text(
        "\n".join(f"{rank},{domain}" for rank, domain in selected) + "\n",
        encoding="utf-8",
    )

    metadata = {
        "source_file_sha256": hashlib.sha256(args.tranco_csv.read_bytes()).hexdigest(),
        "tranco_id": args.tranco_id,
        "list_date": args.list_date,
        "suffix": args.suffix,
        "matching_domains": len(rows),
        "selection_method": selection_method,
        "seed": args.seed if args.method == "random" else None,
        "count": len(selected),
        "output_sha256": hashlib.sha256(args.output_csv.read_bytes()).hexdigest(),
    }
    args.output_csv.with_suffix(args.output_csv.suffix + ".meta.json").write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metadata, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
