import json

import pytest
import yaml

import eval.weak_update_stage2c_lock as locks
from eval.weak_update_stage2c import lock_update_analysis


def _write_yaml(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value), encoding="utf-8")


def _lock_fixture(tmp_path, monkeypatch):
    common = {
        "attenuation_alpha_candidates": [0.25],
        "update_definition_version": "projected_gain_stage2c_v1",
    }
    stress = {
        "stress_regimes": {
            "clean": {"enabled": False},
            "coherent_subhuber_slip": {"enabled": True},
            "gross_outlier_control": {"enabled": True},
        }
    }
    development = {"geometry_seeds": [1], "sensor_seeds": [2], "process_seeds": [3]}
    reserved = {"geometry_seeds": [4], "sensor_seeds": [5], "process_seeds": [6]}
    _write_yaml(tmp_path / "configs/update/stage2c_common.yaml", common)
    _write_yaml(tmp_path / "configs/update/stage2c_stress.yaml", stress)
    _write_yaml(tmp_path / "configs/update/stage2c_development.yaml", development)
    _write_yaml(tmp_path / "configs/update/stage2c_test.yaml", reserved)
    monkeypatch.setattr(locks, "compute_source_tree_snapshot", lambda _paths: ("source", {"a": "b"}))
    monkeypatch.setattr(locks, "compute_bundle_hash", lambda _paths: "config")
    monkeypatch.setattr(locks, "compute_directory_hash", lambda path: "stage2b" if "stage2b" in str(path) else "stage2a")
    monkeypatch.setattr(locks, "changed_snapshot_files", lambda _left, _right: [])
    monkeypatch.setattr(locks, "git_status_clean", lambda _root: True)
    lock = {
        "source_tree_sha256": "source",
        "config_bundle_sha256": "config",
        "stage2a_detector_artifact_sha256": "stage2a",
        "stage2b_no_go_artifact_sha256": "stage2b",
        "source_file_hashes": {"a": "b"},
        "development_go": True,
        "update_definition_version": "projected_gain_stage2c_v1",
        "stress_parameters": json.loads(json.dumps(stress)),
        "selected_attenuation_alpha": 0.25,
        "alpha_selection_table": [{"attenuation_alpha": 0.25, "selected": True}],
    }
    return lock


def test_update_lock_rejects_stress_or_historical_artifact_mismatch(tmp_path, monkeypatch):
    lock = _lock_fixture(tmp_path, monkeypatch)
    checks = locks.verify_update_lock(tmp_path, lock)
    assert all(value for key, value in checks.items() if key != "changed_files")
    lock["stress_parameters"] = {"tampered": True}
    with pytest.raises(RuntimeError, match="stress_parameters_matched"):
        locks.verify_update_lock(tmp_path, lock)


def test_lock_creation_refuses_development_no_go(tmp_path):
    run = tmp_path / "results/weak_update_stage2c/development/no_go"
    (run / "manifests").mkdir(parents=True)
    (run / "manifests/development_manifest.json").write_text(
        json.dumps({"status": "DEVELOPMENT_NO_GO", "development_go": False}),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="DEVELOPMENT_NO_GO"):
        lock_update_analysis(tmp_path, run)
