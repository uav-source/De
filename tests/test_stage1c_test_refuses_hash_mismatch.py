from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import eval.analysis_lock as locks  # noqa: E402


def test_verify_lock_refuses_metric_statistics_and_test_config_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(locks, "git_status_clean", lambda _root: True)
    metric = tmp_path / "metric.py"
    statistics = tmp_path / "statistics.py"
    test_config = tmp_path / "stage1c_test.yaml"
    paths = [metric, statistics, test_config]
    for path in paths:
        path.write_text("version: 1\n", encoding="utf-8")
    monkeypatch.setattr(locks, "stage1c_source_paths", lambda _root: paths)
    monkeypatch.setattr(locks, "stage1c_config_paths", lambda _root: [test_config])

    for changed_path in paths:
        for path in paths:
            path.write_text("version: 1\n", encoding="utf-8")
        source_hash, snapshot = locks.compute_source_tree_snapshot(paths)
        lock = {
            "source_tree_sha256": source_hash,
            "source_file_hashes": snapshot,
            "config_bundle_sha256": locks.compute_bundle_hash([test_config]),
        }
        changed_path.write_text("version: 2\n", encoding="utf-8")
        with pytest.raises(RuntimeError, match="mismatch"):
            locks.verify_analysis_lock(tmp_path, lock)
