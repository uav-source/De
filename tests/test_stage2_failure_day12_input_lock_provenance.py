import shutil
from pathlib import Path

import pytest

from eval import stage2_failure_day12 as day12
from eval.stage2_failure_day12_input_audit import LOCKED_DAY11B_SOURCE_FILES


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "results/stage2_failure_analysis/day11b_replay/stage2_failure_day11b_replay_v2"
RUN_RELATIVE = Path(
    "results/stage2_failure_analysis/day11b_replay/stage2_failure_day11b_replay_v2"
)


def _lock_with_copied_sources(tmp_path, monkeypatch):
    monkeypatch.setattr(day12, "git_status_clean", lambda root: True)
    day12.verify_day12_input(ROOT, RUN, "lock", tmp_path / "output")
    lock_path = tmp_path / "output/lock/day12_input_lock.json"
    fake_root = tmp_path / "fake_root"
    copied_run = fake_root / RUN_RELATIVE
    copied_run.mkdir(parents=True)
    for _, _, filename in LOCKED_DAY11B_SOURCE_FILES.values():
        shutil.copy2(RUN / filename, copied_run / filename)
    return lock_path, fake_root, copied_run


def test_all_fourteen_sources_and_four_provenance_files_are_rehashed(tmp_path, monkeypatch):
    lock_path, fake_root, _ = _lock_with_copied_sources(tmp_path, monkeypatch)
    result = day12.validate_input_lock(lock_path, fake_root)
    assert result["source_file_verification_count"] == 14
    assert result["provenance_source_rehash_count"] == 4
    assert result["source_file_hash_mismatch_count"] == 0
    assert result["DAY12_V3_INPUT_LOCK_PASS"] is True


@pytest.mark.parametrize(
    "filename",
    (
        "strategy_chain_audit.csv", "axial_support_audit.csv",
        "base_observation_pairing_audit.csv",
        "v1_v2_scientific_equivalence_audit.csv",
    ),
)
def test_provenance_file_byte_mutation_rejects_lock(tmp_path, monkeypatch, filename):
    lock_path, fake_root, copied_run = _lock_with_copied_sources(tmp_path, monkeypatch)
    target = copied_run / filename
    target.write_bytes(target.read_bytes() + b"\n")
    with pytest.raises(day12.InputLockValidationError) as caught:
        day12.validate_input_lock(lock_path, fake_root)
    assert caught.value.verification["source_file_hash_mismatch_count"] == 1
    assert caught.value.verification["DAY12_V3_INPUT_LOCK_PASS"] is False
