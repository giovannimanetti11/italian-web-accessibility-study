from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def result_filename(domain: str) -> str:
    digest = hashlib.sha256(domain.encode("utf-8")).hexdigest()
    return f"{digest}.json"


def ensure_run_dir(root: Path, run_id: str) -> Path:
    run_dir = root / run_id
    (run_dir / "domains").mkdir(parents=True, exist_ok=True)
    return run_dir


def result_path(run_dir: Path, domain: str) -> Path:
    return run_dir / "domains" / result_filename(domain)


def is_recorded(run_dir: Path, domain: str) -> bool:
    """Preserve every completed attempt, including explicit domain failures.

    Retries must use a separate validation run, never silently mutate a study
    outcome during recovery from an interrupted worker process.
    """
    path = result_path(run_dir, domain)
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return (payload.get("requested_domain") == domain and
            payload.get("status") in {"complete", "error"})


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def write_domain_result(run_dir: Path, domain: str, payload: dict) -> None:
    atomic_write_json(result_path(run_dir, domain), payload)


def write_run_metadata(run_dir: Path, payload: dict) -> None:
    atomic_write_json(run_dir / "run-metadata.json", payload)


def summarize_domain_results(run_dir: Path) -> dict[str, int]:
    complete = error = 0
    for path in (run_dir / "domains").glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            error += 1
            continue
        if payload.get("status") == "complete":
            complete += 1
        else:
            error += 1
    return {"completed": complete, "errors": error}
