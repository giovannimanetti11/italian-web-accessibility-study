#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()

    domains_dir = args.run_dir / "domains"
    if not domains_dir.exists():
        raise SystemExit(f"Missing {domains_dir}")

    results_path = args.run_dir / "accessibility-results.jsonl"
    manifest_path = args.run_dir / "url-manifest.csv"
    summary_path = args.run_dir / "dataset-summary.json"

    domains = pages = successful_pages = violation_rules = violation_nodes = 0
    with results_path.open("w", encoding="utf-8") as results_file, manifest_path.open(
        "w", encoding="utf-8", newline=""
    ) as manifest_file:
        writer = csv.DictWriter(
            manifest_file,
            fieldnames=["requested_domain", "scope_domain", "url", "reason", "rank"],
        )
        writer.writeheader()

        for path in sorted(domains_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            domains += 1
            if payload.get("status") != "complete":
                continue

            for item in payload.get("manifest") or []:
                writer.writerow(
                    {
                        "requested_domain": payload.get("requested_domain"),
                        "scope_domain": payload.get("scope_domain"),
                        "url": item.get("url"),
                        "reason": item.get("reason"),
                        "rank": item.get("rank"),
                    }
                )

            for page in payload.get("pages") or []:
                row = {
                    "domain": payload.get("requested_domain"),
                    "scope_domain": payload.get("scope_domain"),
                    "protocol_version": payload.get("protocol_version"),
                    **page,
                }
                results_file.write(json.dumps(row, ensure_ascii=False) + "\n")
                pages += 1
                if not page.get("error"):
                    successful_pages += 1
                    violation_rules += int(page.get("violation_rule_count") or 0)
                    violation_nodes += int(page.get("violation_node_count") or 0)

    summary = {
        "domain_result_files": domains,
        "page_rows": pages,
        "successful_page_rows": successful_pages,
        "violation_rules": violation_rules,
        "violation_nodes": violation_nodes,
        "results_jsonl": results_path.name,
        "url_manifest": manifest_path.name,
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
