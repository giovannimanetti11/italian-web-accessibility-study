#!/usr/bin/env python3
# ruff: noqa: E402
"""Conservative, independent reachability diagnostics for historical scan failures.

One HTTPS homepage request per non-403 failure, no redirect following, no login,
no anti-bot bypass. Does not alter any recorded scanner results.
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from iwass.url_utils import host_is_public


def error_class(value: str) -> str:
    error = value.lower()
    if "homepage returned 403" in error:
        return "http_403"
    if "non-public or unresolved" in error:
        return "dns_nonpublic"
    if "cert_" in error or "certificate" in error:
        return "certificate"
    if "timeout" in error:
        return "navigation_timeout"
    if "connection_refused" in error:
        return "connection_refused"
    if "homepage returned" in error:
        return "other_http_status"
    if "interrupted by another navigation" in error:
        return "browser_navigation_interrupted"
    return "other_browser_failure"


def probe(item: dict) -> dict:
    domain = item["domain"]
    category = item["original_error_category"]
    output = dict(item)
    if category == "http_403":
        output["probe_status"] = "skipped_explicit_http_403"
        return output

    try:
        ips = sorted(set(result[4][0] for result in socket.getaddrinfo(domain, 443)))
        output["dns_address_count"] = len(ips)
        output["dns_public"] = host_is_public(domain)
    except OSError as exc:
        output["dns_address_count"] = 0
        output["dns_public"] = False
        output["dns_error"] = type(exc).__name__
    if not output["dns_public"]:
        output["probe_status"] = "dns_unresolved_or_nonpublic"
        return output

    url = "https://" + domain + "/"
    try:
        started = time.monotonic()
        with httpx.Client(timeout=httpx.Timeout(8.0), follow_redirects=False,
                          headers={"User-Agent": "IWASS-MethodologyValidation/1.0",
                                   "Accept": "text/html,*/*;q=0.2"}) as client:
            with client.stream("GET", url) as response:
                output["probe_status"] = "http_response"
                output["http_status"] = response.status_code
                output["https_redirect_location"] = (
                    response.headers.get("Location", "")[:500]
                    if response.is_redirect else None
                )
        output["elapsed_ms"] = round((time.monotonic() - started) * 1000)
    except httpx.HTTPError as exc:
        output["probe_status"] = "httpx_exception"
        output["exception_type"] = type(exc).__name__
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.workers < 1 or args.workers > 4:
        parser.error("1..4 workers allowed")
    source = args.run_dir / "domains"
    records = []
    for path in sorted(source.glob("*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        if item["status"] == "error":
            records.append({
                "domain": item["requested_domain"],
                "original_error_category": error_class(item["error"]),
                "original_error": item["error"].splitlines()[0][:350],
            })
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        tasks = {executor.submit(probe, record): record for record in records}
        for job in as_completed(tasks):
            results.append(job.result())
    results.sort(key=lambda entry: entry["domain"])
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "original_run": args.run_dir.name,
        "original_error_count": len(records),
        "original_error_taxonomy": dict(Counter(x["original_error_category"] for x in records)),
        "probe_outcomes": dict(Counter(x["probe_status"] for x in results)),
        "https_statuses": dict(Counter(str(x.get("http_status")) for x in results
                                    if x.get("http_status") is not None)),
        "probe_limitations": [
            "HTTP-level diagnostics are not Playwright rescans.",
            "403 sites were not re-probed or bypassed.",
            "No redirects were followed; no non-public IP destinations were requested.",
            "Original outcomes remain immutable; DNS and HTTP availability vary over time.",
        ],
        "records": results,
    }
    output = args.run_dir / "failure-diagnostics.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: val for key, val in report.items() if key != "records"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
