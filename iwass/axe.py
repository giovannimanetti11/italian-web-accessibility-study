from __future__ import annotations

import json
from pathlib import Path

from iwass.config import WCAG_TAGS


def axe_assets(repo_root: Path) -> tuple[Path, str]:
    package_path = repo_root / "node_modules" / "axe-core" / "package.json"
    source_path = repo_root / "node_modules" / "axe-core" / "axe.min.js"
    if not package_path.exists() or not source_path.exists():
        raise RuntimeError("axe-core missing: run npm install")
    package = json.loads(package_path.read_text(encoding="utf-8"))
    return source_path, str(package["version"])


def _trim(value, limit: int = 1200):
    if value is None:
        return None
    text = str(value)
    return text if len(text) <= limit else text[:limit] + "..."


def normalize_rule(rule: dict) -> dict:
    nodes = []
    for node in rule.get("nodes") or []:
        nodes.append(
            {
                "target": node.get("target") or [],
                "failure_summary": _trim(node.get("failureSummary")),
            }
        )
    return {
        "id": rule.get("id"),
        "impact": rule.get("impact"),
        "tags": sorted(
            tag for tag in (rule.get("tags") or []) if str(tag).startswith("wcag")
        ),
        "description": _trim(rule.get("description")),
        "help": _trim(rule.get("help")),
        "help_url": rule.get("helpUrl"),
        "node_count": len(nodes),
        "nodes": nodes,
    }


def run_axe(page) -> dict:
    available = page.evaluate("() => typeof window.axe !== 'undefined'")
    if not available:
        raise RuntimeError("axe-core was not injected into the page")

    raw = page.evaluate(
        """async (tags) => await window.axe.run(document, {
            runOnly: { type: "tag", values: tags },
            resultTypes: ["violations", "incomplete", "passes", "inapplicable"]
        })""",
        list(WCAG_TAGS),
    )
    violations = [normalize_rule(rule) for rule in raw.get("violations") or []]
    incomplete = [normalize_rule(rule) for rule in raw.get("incomplete") or []]
    return {
        "violations": violations,
        "incomplete": incomplete,
        "passes_count": len(raw.get("passes") or []),
        "inapplicable_count": len(raw.get("inapplicable") or []),
        "violation_rule_count": len(violations),
        "violation_node_count": sum(rule["node_count"] for rule in violations),
        "incomplete_rule_count": len(incomplete),
    }
