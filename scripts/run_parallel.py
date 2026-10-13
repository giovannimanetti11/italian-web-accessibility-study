#!/usr/bin/env python3
"""Run domain scans in isolated worker processes, then merge verified output."""
from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_WORKER_RESTARTS = 8
WORKER_STALL_SECONDS = 600  # A single domain normally fits within minutes.
WORKER_TERMINATE_GRACE_SECONDS = 8
SUPERVISOR_POLL_SECONDS = 30


def worker_stalled(last_progress_monotonic: float, current_monotonic: float,
                   timeout_seconds: float = WORKER_STALL_SECONDS) -> bool:
    return current_monotonic - last_progress_monotonic >= timeout_seconds


def terminate_worker_group(process: subprocess.Popen,
                           grace_seconds: float = WORKER_TERMINATE_GRACE_SECONDS) -> int:
    """Stop the dedicated worker session (including Chromium descendants).

    Workers start with start_new_session=True, so their process group is
    isolated from the supervising process and unrelated host applications.
    """
    if process.poll() is not None:
        return process.returncode
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        return process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        return process.wait(timeout=5)


def count_worker_results(root: Path, worker_id: str) -> int:
    domain_dir = root / "workers" / worker_id / "domains"
    return sum(1 for _ in domain_dir.glob("*.json")) if domain_dir.exists() else 0


def worker_should_restart(exit_code: int | None, retries: int) -> bool:
    # Restart only unexpected failures. A completed worker must not rerun.
    return exit_code is not None and exit_code != 0 and retries < MAX_WORKER_RESTARTS


def now() -> str:
    return datetime.now(UTC).isoformat()


def parse_targets(path: Path) -> list[tuple[str, str]]:
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.reader(stream):
            if not row or row[0].startswith("#"):
                continue
            if len(row) < 2 or not row[0].strip().isdigit():
                raise ValueError(f"Expected rank,domain CSV; got {row!r}")
            rows.append((row[0].strip(), row[1].strip().lower()))
    domains = [domain for _, domain in rows]
    if len(set(domains)) != len(domains):
        raise ValueError("Duplicate domains in input")
    if any(not name.endswith(".it") for name in domains):
        raise ValueError("Input contains non-.it target")
    return rows


def prepare_shards(rows: list[tuple[str, str]], root: Path, workers: int) -> list[Path]:
    paths = []
    for worker in range(workers):
        path = root / "inputs" / f"worker-{worker + 1:02}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "".join(f"{rank},{domain}\n" for rank, domain in rows[worker::workers]),
            encoding="utf-8",
        )
        paths.append(path)
    return paths


def merge_outputs(root: Path, run_id: str, rows: list[tuple[str, str]], workers: int) -> dict:
    destination = root / "domains"
    destination.mkdir(parents=True, exist_ok=True)
    complete = errors = 0
    for worker in range(workers):
        source = root / "workers" / f"worker-{worker + 1:02}" / "domains"
        for file in source.glob("*.json"):
            temp = destination / (file.name + ".tmp")
            shutil.copyfile(file, temp)
            os.replace(temp, destination / file.name)
    for _, domain in rows:
        filename = hashlib.sha256(domain.encode()).hexdigest() + ".json"
        path = destination / filename
        if not path.exists():
            raise RuntimeError(f"No result for {domain}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("requested_domain") != domain:
            raise RuntimeError(f"Domain mismatch for {domain}")
        if payload.get("status") == "complete":
            complete += 1
        else:
            errors += 1
    if len(list(destination.glob("*.json"))) != len(rows):
        raise RuntimeError("Result count mismatch: stale or extra domain files")
    return {"completed": complete, "errors": errors, "total": len(rows)}


def run(args: argparse.Namespace) -> int:
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}", args.run_id):
        raise ValueError("Invalid run ID")
    if not 1 <= args.workers <= 4:
        raise ValueError("Allowed workers: 1 to 4")
    input_path = args.input.resolve()
    rows = parse_targets(input_path)
    root = ROOT / "runs" / args.run_id
    root.mkdir(parents=True, exist_ok=True)
    lock = (root / ".lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        raise RuntimeError("This run is already active") from exc

    input_hash = hashlib.sha256(input_path.read_bytes()).hexdigest()
    marker = root / "execution.json"
    if marker.exists():
        existing = json.loads(marker.read_text(encoding="utf-8"))
        if (existing["input_sha256"], existing["workers"]) != (input_hash, args.workers):
            raise RuntimeError("Input or worker count differs from the original run")
    else:
        marker.write_text(json.dumps({
            "run_id": args.run_id,
            "input_path": str(input_path),
            "input_sha256": input_hash,
            "workers": args.workers,
            "targets": len(rows),
            "started_at": now(),
        }, indent=2) + "\n", encoding="utf-8")

    paths = prepare_shards(rows, root, args.workers)
    processes = []
    for i, path in enumerate(paths):
        worker_id = f"worker-{i + 1:02}"
        log = (root / f"{worker_id}.log").open("a", encoding="utf-8")
        # Use Linux niceness to protect other services hosted on this machine.
        cmd = ["/usr/bin/nice", "-n", "8", sys.executable,
               str(ROOT / "scripts/scan.py"), "scan", str(path),
               "--run-id", worker_id, "--runs-dir", str(root / "workers")]
        p = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                             start_new_session=True)
        processes.append({
            "worker_id": worker_id, "process": p, "log": log, "cmd": cmd,
            "restarts": 0, "last_count": count_worker_results(root, worker_id),
            "last_progress": time.monotonic(),
        })
        print(f"{now()} {worker_id} pid={p.pid}, targets={len(rows[i::args.workers])}",
              flush=True)

    while True:
        active = False
        counts = []
        for state in processes:
            worker_id = state["worker_id"]
            count = count_worker_results(root, worker_id)
            counts.append(count)
            tick = time.monotonic()
            if count > state["last_count"]:
                state["last_count"] = count
                state["last_progress"] = tick

            p = state["process"]
            code = p.poll()
            reason = "nonzero_exit"
            if code is None and worker_stalled(state["last_progress"], tick):
                reason = "no_domain_result_timeout"
                print(f"{now()} WATCHDOG: {worker_id} pid={p.pid} did not save a "
                      f"domain result for {WORKER_STALL_SECONDS}s; terminating "
                      "isolated worker process group", flush=True)
                code = terminate_worker_group(p)

            if code is None:
                active = True
            elif worker_should_restart(code, state["restarts"]):
                # Preserve all existing records. The replacement process uses
                # --resume and skips already-recorded domain results.
                state["log"].close()
                state["log"] = (
                    root / f"{worker_id}.log"
                ).open("a", encoding="utf-8")
                restarted = subprocess.Popen(
                    state["cmd"], cwd=ROOT, stdout=state["log"],
                    stderr=subprocess.STDOUT, start_new_session=True,
                )
                state["process"] = restarted
                state["restarts"] += 1
                state["last_progress"] = time.monotonic()
                event = {
                    "timestamp": now(), "worker_id": worker_id,
                    "previous_exit": code, "reason": reason,
                    "attempt": state["restarts"], "new_pid": restarted.pid,
                    "last_saved_count": count,
                }
                with (root / "worker-restarts.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(event) + "\n")
                print(f"RESTART: {json.dumps(event)}", flush=True)
                active = True
            elif code != 0:
                print(f"{now()} FAILED: {worker_id} exit={code}, "
                      f"restarts={state['restarts']}; no more retries", flush=True)
        if not active:
            break

        progress = {"updated_at": now(), "done": sum(counts), "total": len(rows),
                    "per_worker": counts,
                    "watchdog_seconds": WORKER_STALL_SECONDS}
        (root / "progress.json").write_text(json.dumps(progress, indent=2) + "\n")
        print(json.dumps(progress), flush=True)
        time.sleep(SUPERVISOR_POLL_SECONDS)

    codes = []
    for state in processes:
        code = state["process"].wait()
        state["log"].close()
        codes.append(code)
        print(f"{state['worker_id']} exit={code}, "
              f"restarts={state['restarts']}", flush=True)
    if any(code != 0 for code in codes):
        print("Worker failed; preserve shards for inspection/resume", file=sys.stderr)
        return 1

    totals = merge_outputs(root, args.run_id, rows, args.workers)
    subprocess.run([sys.executable,
                    str(ROOT / "scripts/build_dataset.py"), str(root)],
                   cwd=ROOT, check=True)
    quality_cmd = [sys.executable,
                   str(ROOT / "scripts/analyze_pilot.py"), str(root), str(input_path)]
    if args.baseline:
        quality_cmd.extend(["--baseline", str(args.baseline.resolve())])
    with (root / "quality-report.log").open("w", encoding="utf-8") as report_log:
        subprocess.run(quality_cmd, cwd=ROOT, check=True, stdout=report_log)
    metadata = json.loads(marker.read_text(encoding="utf-8"))
    metadata.update({"finished_at": now(), **totals})
    (root / "execution.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (root / "progress.json").write_text(json.dumps({
        "updated_at": now(), "done": len(rows), "total": len(rows),
        "per_worker": [len(rows[i::args.workers]) for i in range(args.workers)],
        "status": "completed",
    }, indent=2) + "\n")
    print(f"SUCCESS: {json.dumps(totals)}", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--baseline", type=Path)
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
