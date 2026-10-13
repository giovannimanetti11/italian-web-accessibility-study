import json

from scripts.analyze_pilot import analyze, classify_error


def test_error_taxonomy():
    assert classify_error("RuntimeError: homepage returned 403") == "http_403"
    assert classify_error("RuntimeError: non-public or unresolved URL rejected") == (
        "dns_or_nonpublic_rejected"
    )
    assert classify_error("Page.goto: net::ERR_CERT_COMMON_NAME_INVALID") == "certificate_error"


def test_quality_report_flags_policy_pages(tmp_path):
    frame = tmp_path / "frame.csv"
    frame.write_text("1,example.it\n")
    domains = tmp_path / "run" / "domains"
    domains.mkdir(parents=True)
    payload = {
        "requested_domain": "example.it",
        "status": "complete",
        "scope_domain": "example.it",
        "redirected_cross_domain": False,
        "timings": {"domain_total_ms": 100},
        "manifest": [
            {"url": "https://example.it/", "reason": "homepage"},
            {"url": "https://example.it/_/_/policy/notice-at-collection", "reason": "deep"},
        ],
        "pages": [
            {"violation_rule_count": 0, "violation_node_count": 0, "violations": []}
        ],
    }
    (domains / "one.json").write_text(json.dumps(payload))
    result = analyze(domains.parent, frame)
    assert result["sampled_domains"] == result["completed_domains"] == 1
    assert result["pages_selected"] == 2
    assert result["manifest_anomalies"][0]["issue"] == "possible_legal_boilerplate"
