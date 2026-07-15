import hashlib
import json
import shutil
from pathlib import Path

import pytest

from eval import stage2_failure_day11b_lock as lock_module


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results/stage2_failure_analysis/day11a_case_lock/stage2_failure_day11a_case_lock_v1"


def test_real_day11a_lock_is_independently_verified():
    result = lock_module.verify_day11a_case_lock(
        ROOT, SOURCE / "deterministic_diagnostic_case_lock.json"
    )
    assert result["verification_pass"] is True
    assert result["candidate_pool_row_count"] == 1600
    assert result["geometry_selected_row_count"] == 1
    assert result["observation_selected_row_count"] == 1


def test_case_lock_sha_mutation_is_rejected(tmp_path):
    target = tmp_path / "run"
    shutil.copytree(SOURCE, target)
    path = target / "deterministic_diagnostic_case_lock.json"
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="artifact hash"):
        lock_module.verify_day11a_case_lock(ROOT, path)


def test_candidate_pool_sha_mutation_is_rejected(tmp_path):
    target = tmp_path / "run"
    shutil.copytree(SOURCE, target)
    pool = target / "candidate_pool.csv"
    pool.write_text(pool.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="artifact hash"):
        lock_module.verify_day11a_case_lock(
            ROOT, target / "deterministic_diagnostic_case_lock.json"
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [("geometry_selected_index", 1), ("stage2c_commit", "0" * 40)],
)
def test_lock_scientific_mutations_are_rejected_after_rehash(tmp_path, monkeypatch, field, value):
    target = tmp_path / "run"
    shutil.copytree(SOURCE, target)
    path = target / "deterministic_diagnostic_case_lock.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data[field] = value
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    monkeypatch.setattr(
        lock_module,
        "EXPECTED_CASE_LOCK_SHA256",
        hashlib.sha256(path.read_bytes()).hexdigest(),
    )
    with pytest.raises(ValueError):
        lock_module.verify_day11a_case_lock(ROOT, path)


def test_stage2c_stress_config_hash_mutation_is_rejected(monkeypatch):
    monkeypatch.setitem(lock_module.EXPECTED_STAGE2C_HASHES, "stage2c_stress_config", "0" * 64)
    with pytest.raises(ValueError, match="Stage 2C source hash"):
        lock_module.verify_day11a_case_lock(
            ROOT, SOURCE / "deterministic_diagnostic_case_lock.json"
        )
