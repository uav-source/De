from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import eval.test_provenance as provenance  # noqa: E402


def test_verified_pytest_status_depends_on_return_code(tmp_path, monkeypatch):
    monkeypatch.setattr(provenance, "git_status_clean", lambda _root: True)
    monkeypatch.setattr(provenance, "git_commit", lambda _root: "commit")
    monkeypatch.setattr(provenance, "compute_source_tree_hash", lambda _paths: "source")
    monkeypatch.setattr(provenance, "stage1c_source_paths", lambda _root: [])
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 1, stdout="999 passed", stderr="failure")

    monkeypatch.setattr(provenance, "_run_pytest_command", fake_run)
    record = provenance.run_verified_pytest(ROOT, tmp_path / "provenance.json")
    assert captured["command"] == [sys.executable, "-m", "pytest", "-q"]
    assert record["return_code"] == 1
    assert record["status"] == "failed"
