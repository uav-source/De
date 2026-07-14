from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import eval.analysis_lock as locks  # noqa: E402


def test_verify_lock_refuses_dirty_tree(monkeypatch):
    source_hash, snapshot = locks.compute_source_tree_snapshot(locks.stage1c_source_paths(ROOT))
    lock = {"source_tree_sha256": source_hash, "source_file_hashes": snapshot, "config_bundle_sha256": locks.compute_bundle_hash(locks.stage1c_config_paths(ROOT))}
    monkeypatch.setattr(locks, "git_status_clean", lambda _root: False)
    with pytest.raises(RuntimeError, match="git worktree is dirty"):
        locks.verify_analysis_lock(ROOT, lock, require_clean=True)
