#!/usr/bin/env python3
# ruff: noqa: E402
"""Descriptive quality checks for a reproducible accessibility pilot."""
from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from iwass.config import SKIP_EXTENSIONS


def percentile(values: list[int], p: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[round((len(ordered) - 1) * p)])


def classify_error(error: str) -> str:
    err = error.lower()
    if "non-public or unresolved" in err:
        return "dns_or_nonpublic_rejected"
    if "homepage returned 403" in err:
        return "http_403"
    if "homepage returned " in err:
        return "other_http_homepage"
    if "timeout" in err:
        return "navigation_timeout"
    if "certificate" in err or "cert_" in err:
        return "certificate_error"
    if "connection refused" in err or "err_connection_refused" in err:
        return "connection_refused"
    return "other_navigation_or_scan"


def analyze(run_dir: Path, source: Path, baseline: Path | None = None) -> dict:
    ranks = {}
    with source.open(encoding="utf-8-sig", newline="") as handle:
        for rank, domain in csv.reader(handle):
            ranks[domain] = int(rank)
    ranked = sorted(ranks, key=lambda domain: ranks[domain])
    quartiles = {domain: min(4, (i * 4 // len(ranked)) + 1)
                 for i, domain in enumerate(ranked)}
    data = []
    for path in (run_dir / "domains").glob("*.json"):
        data.append(json.loads(path.read_text(encoding="utf-8")))
    by_domain = {item["requested_domain"]: item for item in data}
    if set(by_domain) != set(ranks) or len(data) != len(ranks):
        raise RuntimeError("Domain set and input frame do not match")

    complete = [item for item in data if item["status"] == "complete"]
    errored = [item for item in data if item["status"] != "complete"]
    page_rows = [page for d in complete for page in d.get("pages", [])]
    successful = [page for page in page_rows if not page.get("error")]
    rule_counter = Counter()
    impact_counter = Counter()
    nodes = 0
    for page in successful:
        for violation in page.get("violations", []):
            rule_counter[violation["id"]] += 1
            impact_counter[violation.get("impact") or "unknown"] += 1
        nodes += page.get("violation_node_count", 0)
    strata = []
    for q in range(1, 5):
        group = [by_domain[domain] for domain in ranked if quartiles[domain] == q]
        strata.append({"quartile": q, "domains": len(group),
                       "complete": sum(item["status"] == "complete" for item in group),
                       "errors": sum(item["status"] != "complete" for item in group)})

    low_value_segments = {
        "privacy", "privacy-policy", "cookie", "cookies", "cookie-policy",
        "cookies-policy", "terms", "terms-of-service", "legal", "policy",
        "notice-at-collection", "impressum", "note-legali",
    }
    issues = []
    for d in complete:
        seen = set()
        for item in d.get("manifest", []):
            url = item["url"]
            parsed = urlsplit(url)
            suffix = Path(parsed.path).suffix.lower()
            if url in seen or suffix in SKIP_EXTENSIONS or parsed.scheme not in ("http", "https"):
                issues.append({"domain": d["requested_domain"], "reason": item["reason"],
                               "url": url, "issue": "duplicate/media/invalid_scheme"})
            segments = {segment for segment in parsed.path.lower().split("/") if segment}
            if segments & low_value_segments:
                issues.append({"domain": d["requested_domain"], "reason": item["reason"],
                               "url": url, "issue": "possible_legal_boilerplate"})
            seen.add(url)
        if len(d.get("manifest", [])) > 5:
            issues.append({"domain": d["requested_domain"], "issue": "over_five_pages"})

    cross = [d for d in complete if d.get("redirected_cross_domain")]
    timings = [d["timings"]["domain_total_ms"] for d in complete]
    error_taxonomy = dict(sorted(Counter(classify_error(d.get("error", ""))
                                         for d in errored).items()))
    compared = {}
    if baseline:
        old = {}
        for path in (baseline / "domains").glob("*.json"):
            item = json.loads(path.read_text(encoding="utf-8"))
            old[item["requested_domain"]] = item
        overlap = set(old) & set(by_domain)
        both = [domain for domain in overlap
                if old[domain]["status"] == by_domain[domain]["status"] == "complete"]
        changed = [domain for domain in both
                   if [x["url"] for x in old[domain]["manifest"]] !=
                   [x["url"] for x in by_domain[domain]["manifest"]]]
        compared = {"overlap_domains": len(overlap), "both_completed": len(both),
                    "manifest_urls_changed": len(changed)}

    rng = random.Random(20261008)
    manual = []
    for q in range(1, 5):
        available = [domain for domain in ranked if quartiles[domain] == q
                     and by_domain[domain]["status"] == "complete"]
        for domain in sorted(rng.sample(available, min(5, len(available)))):
            d = by_domain[domain]
            for item in d["manifest"]:
                manual.append({"quartile": q, "domain": domain, "reason": item["reason"],
                               "url": item["url"]})
    if manual:
        review_path = run_dir / "stratified-manifest-review.csv"
        with review_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["quartile", "domain", "reason", "url"])
            writer.writeheader()
            writer.writerows(manual)

    report = {
        "sampled_domains": len(ranks),
        "completed_domains": len(complete),
        "error_domains": len(errored),
        "completion_rate": round(len(complete) / len(ranks), 4),
        "failure_taxonomy": error_taxonomy,
        "rank_quartiles": strata,
        "cross_domain_redirects": [{"from": d["requested_domain"], "to": d["scope_domain"]}
                                   for d in sorted(cross, key=lambda d: d["requested_domain"])],
        "pages_selected": sum(len(d.get("manifest", [])) for d in complete),
        "page_rows": len(page_rows),
        "pages_successful": len(successful),
        "domains_with_axe_violations": sum(
            any(p.get("violation_rule_count", 0) > 0 for p in d.get("pages", [])
                if not p.get("error")) for d in complete
        ),
        "violation_rule_occurrences": sum(rule_counter.values()),
        "violation_nodes": nodes,
        "impact_occurrences": dict(impact_counter),
        "most_frequent_rules": rule_counter.most_common(15),
        "timing_ms": {"median": round(statistics.median(timings)) if timings else None,
                      "p90": percentile(timings, .9), "p95": percentile(timings, .95)},
        "manifest_anomalies": issues,
        "compared_to_pilot_100": compared,
        "manual_review_rows": len(manual),
        "automated_wcag_conformance_claim": False,
    }
    (run_dir / "quality-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("source_csv", type=Path)
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args()
    print(json.dumps(analyze(args.run_dir, args.source_csv, args.baseline),
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
