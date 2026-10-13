import json

from iwass.storage import is_recorded, result_path


def test_resume_preserves_success_and_failures(tmp_path):
    for status in ("complete", "error"):
        path = result_path(tmp_path, status + ".it")
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps({
            "requested_domain": status + ".it", "status": status
        }))
        assert is_recorded(tmp_path, status + ".it")


def test_resume_does_not_skip_corrupted_or_mismatched_files(tmp_path):
    path = result_path(tmp_path, "one.it")
    path.parent.mkdir(exist_ok=True)
    path.write_text("not json")
    assert not is_recorded(tmp_path, "one.it")
    path.write_text(json.dumps({
        "requested_domain": "two.it", "status": "complete"
    }))
    assert not is_recorded(tmp_path, "one.it")
