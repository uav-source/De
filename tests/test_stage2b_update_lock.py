import json

import pytest
import yaml

import eval.weak_update_stage2b_lock as locks


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value), encoding="utf-8")


def test_update_lock_verification_rejects_stress_mismatch(tmp_path, monkeypatch):
    common = {"attenuation_alpha_candidates": [0.25]}
    stress = {"stress_regimes": {"clean": {"enabled": False}}}
    development = {"geometry_seeds": [1], "sensor_seeds": [2], "process_seeds": [3]}
    reserved = {"geometry_seeds": [4], "sensor_seeds": [5], "process_seeds": [6]}
    _write(tmp_path / "configs/update/stage2b_common.yaml", common)
    _write(tmp_path / "configs/update/stage2b_stress.yaml", stress)
    _write(tmp_path / "configs/update/stage2b_development.yaml", development)
    _write(tmp_path / "configs/update/stage2b_test.yaml", reserved)
    monkeypatch.setattr(locks, "compute_source_tree_snapshot", lambda _paths: ("source", {"a": "b"}))
    monkeypatch.setattr(locks, "compute_bundle_hash", lambda _paths: "config")
    monkeypatch.setattr(locks, "sha256_file", lambda _path: "stage2a")
    monkeypatch.setattr(locks, "changed_snapshot_files", lambda _left, _right: [])
    monkeypatch.setattr(locks, "git_status_clean", lambda _root: True)
    lock = {
        "source_tree_sha256": "source", "config_bundle_sha256": "config",
        "stage2a_detector_lock_sha256": "stage2a", "source_file_hashes": {"a": "b"},
        "stress_parameters": json.loads(json.dumps(stress)), "selected_attenuation_alpha": 0.25,
        "alpha_selection_table": [{"attenuation_alpha": 0.25, "selected": True}],
    }
    checks = locks.verify_update_lock(tmp_path, lock)
    assert all(value for key, value in checks.items() if key != "changed_files")
    lock["stress_parameters"] = {"tampered": True}
    with pytest.raises(RuntimeError, match="stress_parameters_matched"):
        locks.verify_update_lock(tmp_path, lock)
