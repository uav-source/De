import json
import shutil
from pathlib import Path

import pytest

from eval import stage2_failure_day12 as day12
from eval.stage2_failure_day12_input_audit import (
    LOCKED_DAY11B_SOURCE_FILES,
    LockedInputPathError,
    resolve_locked_input_file,
)


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "results/stage2_failure_analysis/day11b_replay/stage2_failure_day11b_replay_v2"
RUN_RELATIVE = Path(
    "results/stage2_failure_analysis/day11b_replay/stage2_failure_day11b_replay_v2"
)


def _fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(day12, "git_status_clean", lambda root: True)
    day12.verify_day12_input(ROOT, RUN, "lock", tmp_path / "output")
    lock_path = tmp_path / "output/lock/day12_input_lock.json"
    fake_root = tmp_path / "fake_root"
    copied_run = fake_root / RUN_RELATIVE
    copied_run.mkdir(parents=True)
    for _, _, filename in LOCKED_DAY11B_SOURCE_FILES.values():
        shutil.copy2(RUN / filename, copied_run / filename)
    return lock_path, fake_root, copied_run


def _rewrite_lock(lock_path, field, value):
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock[field] = value
    lock_path.write_text(json.dumps(lock), encoding="utf-8")


@pytest.mark.parametrize("bad_path", ("../../fake.csv", "/home/lj/fake.csv"))
def test_resolver_rejects_traversal_and_absolute_paths(tmp_path, bad_path):
    with pytest.raises(LockedInputPathError):
        resolve_locked_input_file(tmp_path, bad_path)


@pytest.mark.parametrize(
    "bad_path", ("../strategy_chain_audit.csv", "/home/lj/strategy_chain_audit.csv")
)
def test_lock_rejects_traversal_and_absolute_paths(tmp_path, monkeypatch, bad_path):
    lock_path, fake_root, _ = _fixture(tmp_path, monkeypatch)
    _rewrite_lock(lock_path, "strategy_chain_audit_path", bad_path)
    with pytest.raises(day12.InputLockValidationError) as caught:
        day12.validate_input_lock(lock_path, fake_root)
    assert caught.value.verification["source_file_path_violation_count"] > 0


def test_lock_rejects_same_content_under_wrong_filename(tmp_path, monkeypatch):
    lock_path, fake_root, copied_run = _fixture(tmp_path, monkeypatch)
    original = copied_run / "strategy_chain_audit.csv"
    shutil.copy2(original, copied_run / "strategy_chain_copy.csv")
    _rewrite_lock(lock_path, "strategy_chain_audit_path", "strategy_chain_copy.csv")
    with pytest.raises(day12.InputLockValidationError) as caught:
        day12.validate_input_lock(lock_path, fake_root)
    assert caught.value.verification["source_file_path_violation_count"] > 0


def test_lock_rejects_symlink_and_directory_substitution(tmp_path, monkeypatch):
    lock_path, fake_root, copied_run = _fixture(tmp_path, monkeypatch)
    target = copied_run / "strategy_chain_audit.csv"
    outside = tmp_path / "outside.csv"
    outside.write_bytes(target.read_bytes())
    target.unlink()
    target.symlink_to(outside)
    with pytest.raises(day12.InputLockValidationError) as caught:
        day12.validate_input_lock(lock_path, fake_root)
    assert caught.value.verification["source_file_symlink_count"] == 1

    target.unlink()
    target.mkdir()
    with pytest.raises(day12.InputLockValidationError) as caught:
        day12.validate_input_lock(lock_path, fake_root)
    assert caught.value.verification["source_file_path_violation_count"] > 0


def test_lock_rejects_correct_path_with_wrong_sha(tmp_path, monkeypatch):
    lock_path, fake_root, _ = _fixture(tmp_path, monkeypatch)
    _rewrite_lock(lock_path, "strategy_chain_audit_sha256", "0" * 64)
    with pytest.raises(day12.InputLockValidationError) as caught:
        day12.validate_input_lock(lock_path, fake_root)
    assert caught.value.verification["source_file_hash_mismatch_count"] == 1


def test_lock_reports_missing_source_file(tmp_path, monkeypatch):
    lock_path, fake_root, copied_run = _fixture(tmp_path, monkeypatch)
    (copied_run / "strategy_chain_audit.csv").unlink()
    with pytest.raises(day12.InputLockValidationError) as caught:
        day12.validate_input_lock(lock_path, fake_root)
    assert caught.value.verification["source_file_missing_count"] == 1
