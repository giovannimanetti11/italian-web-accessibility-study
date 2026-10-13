from __future__ import annotations

import csv
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress

from iwass.config import MAX_PAGES_PER_DOMAIN, PROTOCOL_VERSION, WCAG_TAGS
from iwass.scanner import AccessibilityScanner
from iwass.storage import (
    ensure_run_dir,
    is_recorded,
    summarize_domain_results,
    utc_now,
    write_domain_result,
    write_run_metadata,
)
from iwass.url_utils import is_it_domain, registrable_domain

console = Console()


def _load_targets(path: Path) -> list[str]:
    targets: list[str] = []
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            parts = next(csv.reader([line]))
        except csv.Error:
            parts = [line]
        if len(parts) >= 2 and parts[0].strip().isdigit():
            value = parts[1].strip()
        else:
            value = parts[0].strip()
        if value and value.lower() not in {"domain", "url"}:
            targets.append(value)
    return targets


@click.group()
def cli() -> None:
    """Italian Web Accessibility Study tools."""


@cli.command("scan")
@click.argument("targets_file", type=click.Path(exists=True, path_type=Path))
@click.option("--run-id", default=None, help="Stable run identifier. Reuse it to resume.")
@click.option("--runs-dir", default="runs", type=click.Path(path_type=Path))
@click.option("--limit", type=int, default=None, help="Scan only the first N valid targets.")
@click.option(
    "--allow-non-it",
    is_flag=True,
    help="Allow non-.it targets for development/smoke tests.",
)
@click.option("--resume/--no-resume", default=True)
def scan_command(
    targets_file: Path,
    run_id: str | None,
    runs_dir: Path,
    limit: int | None,
    allow_non_it: bool,
    resume: bool,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    targets = _load_targets(targets_file)

    deduped = []
    seen = set()
    for target in targets:
        domain = registrable_domain(target)
        if not domain or domain in seen:
            continue
        if not allow_non_it and not is_it_domain(target):
            continue
        seen.add(domain)
        deduped.append(target)

    if limit is not None:
        deduped = deduped[: max(0, limit)]
    if not deduped:
        raise click.ClickException("No valid targets to scan")

    if not run_id:
        run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = ensure_run_dir(repo_root / runs_dir, run_id)

    input_sha256 = hashlib.sha256(targets_file.read_bytes()).hexdigest()
    metadata = {
        "study": "Italian Web Accessibility Study",
        "protocol_version": PROTOCOL_VERSION,
        "run_id": run_id,
        "created_at": utc_now(),
        "targets_file": str(targets_file),
        "targets_file_sha256": input_sha256,
        "targets_selected": len(deduped),
        "python_version": sys.version.split()[0],
        "max_pages_per_domain": MAX_PAGES_PER_DOMAIN,
        "wcag_tags": list(WCAG_TAGS),
        "automated_conformance_claim": False,
        "sampling_scope": ".it" if not allow_non_it else "development: non-.it allowed",
    }
    write_run_metadata(run_dir, metadata)

    completed = errors = skipped = 0
    with AccessibilityScanner(repo_root) as scanner:
        metadata.update(
            {
                "axe_version": scanner.axe_version,
                "chromium_version": scanner.chromium_version,
            }
        )
        write_run_metadata(run_dir, metadata)
        with Progress() as progress:
            task = progress.add_task("Scanning", total=len(deduped))
            for target in deduped:
                domain = registrable_domain(target)
                if resume and is_recorded(run_dir, domain):
                    skipped += 1
                    progress.advance(task)
                    continue

                result = scanner.scan_domain(target)
                write_domain_result(run_dir, domain, result)
                if result.get("status") == "complete":
                    completed += 1
                else:
                    errors += 1
                progress.advance(task)

    totals = summarize_domain_results(run_dir)
    metadata.update(
        {
            "finished_at": utc_now(),
            **totals,
            "invocation_completed": completed,
            "invocation_errors": errors,
            "resume_skipped": skipped,
        }
    )
    write_run_metadata(run_dir, metadata)
    console.print(
        f"[bold]Run {run_id}[/bold]: {completed} complete, {errors} errors, "
        f"{skipped} resume-skipped"
    )
    console.print(f"Results: {run_dir}")


if __name__ == "__main__":
    cli()
