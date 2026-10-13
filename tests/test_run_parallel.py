import hashlib
import json
import subprocess
import sys

import pytest

from scripts.run_parallel import (
    MAX_WORKER_RESTARTS,
    merge_outputs,
    parse_targets,
    prepare_shards,
    terminate_worker_group,
    worker_should_restart,
    worker_stalled,
)


def test_shards_preserve_every_domain_without_overlap(tmp_path):
    rows = [(str(i), f"example{i}.it") for i in range(1, 12)]
    paths = prepare_shards(rows, tmp_path, 2)
    selected = []
    for path in paths:
        selected.extend(parse_targets(path))
    assert sorted(selected) == sorted(rows)
    assert [len(parse_targets(path)) for path in paths] == [6, 5]


def test_duplicate_domains_rejected(tmp_path):
    input_path = tmp_path / "input.csv"
    input_path.write_text("1,example.it\n2,example.it\n")
    with pytest.raises(ValueError, match="Duplicate"):
        parse_targets(input_path)


def test_merge_verifies_domain_and_counts(tmp_path):
    rows = [("1", "one.it"), ("2", "two.it")]
    for i, (_, domain) in enumerate(rows, start=1):
        result_dir = tmp_path / "workers" / f"worker-{i:02}" / "domains"
        result_dir.mkdir(parents=True)
        result = {"requested_domain": domain, "status": "complete" if i == 1 else "error"}
        filename = hashlib.sha256(domain.encode()).hexdigest() + ".json"
        (result_dir / filename).write_text(json.dumps(result))
    assert merge_outputs(tmp_path, "test", rows, 2) == {
        "completed": 1, "errors": 1, "total": 2
    }


def test_merge_rejects_missing_results(tmp_path):
    with pytest.raises(RuntimeError, match="No result"):
        merge_outputs(tmp_path, "test", [("1", "missing.it")], 2)


def test_worker_restarts_are_bounded_and_do_not_restart_success():
    assert worker_should_restart(1, 0)
    assert worker_should_restart(137, MAX_WORKER_RESTARTS - 1)
    assert not worker_should_restart(1, MAX_WORKER_RESTARTS)
    assert not worker_should_restart(0, 0)
    assert not worker_should_restart(None, 0)



def test_watchdog_only_triggers_after_worker_inactivity_timeout():
    assert not worker_stalled(100.0, 699.9, 600.0)
    assert worker_stalled(100.0, 700.0, 600.0)
    assert not worker_stalled(699.0, 700.0, 600.0)


def test_watchdog_terminates_only_the_stalled_worker_session():
    worker = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        start_new_session=True,
    )
    unrelated = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        start_new_session=True,
    )
    try:
        assert terminate_worker_group(worker, grace_seconds=1) != 0
        assert worker.poll() is not None
        assert unrelated.poll() is None
    finally:
        for process in (worker, unrelated):
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=3)
