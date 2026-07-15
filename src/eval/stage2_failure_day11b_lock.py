"""Independent verification of the frozen Day 11A deterministic case lock."""

from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from eval.analysis_lock import sha256_file
from eval.stage2_failure_day11a_schema import (
    validate_candidate_pool_rows,
    validate_case_lock,
    validate_protocol_revision_manifest,
)
from eval.synthetic_pipeline_common import load_yaml


DAY11A_CHECKPOINT = "checkpoint/day11a-deterministic-case-lock-pass"
STAGE2C_TAG = "archive/stage2c-projected-gain-no-go"
EXPECTED_DAY11A_COMMIT = "4f229e4152da84f2a7fafe1f0e21fd4d43fcbc7f"
EXPECTED_STAGE2C_COMMIT = "ae90aaad51e72aa53ee0344047f9475fb51650a9"
EXPECTED_CANDIDATE_POOL_SHA256 = (
    "ad43d50c07c9c56e8d87e40e80abc17faf2a8e7b38724959ac4e2e641567207f"
)
EXPECTED_CASE_LOCK_SHA256 = (
    "c80faeea2656d6725dee7a6dc238d940d7492e417fd3968adbe3c78c5b8c90a2"
)
EXPECTED_PROTOCOL_SHA256 = (
    "02a43d7afcf076fe61d7acc2e5da6b9a919cc89c830d7adb13d5e6279d6beb6d"
)
EXPECTED_STAGE2C_HASHES = {
    "stage2c_test_manifest": "355c4bcd82bb737462911bdc31156f087a65dd2043517a8cf5d225f17794ffde",
    "stage2c_update_lock": "e19a1d9b84a597aeb6071cd8d8c3fa904829f9b671eff2e3bf031cc905e82fb1",
    "stage2c_common_config": "9661d3b8e39cf74c23c4903bfd2552c391e376a5b4f79ce87f8769c1074669d2",
    "stage2c_test_config": "022cbea53d8b1c84723e1ce4e80ff670fd946c6e6c0c7e3e2849a622fa39d986",
    "stage2c_stress_config": "f241ab437ab30e87d802787211e2c560f46b9b0302c50546fe45e210e279dcf4",
}
EXPECTED_CASES = {
    "geometry": {"level": "L4", "geometry_seed": 4003, "sensor_seed": 111, "process_seed": 6015},
    "observation": {"level": "O4", "geometry_seed": 5147, "sensor_seed": 99, "process_seed": 6009},
}


def verify_day11a_case_lock(root: Path, case_lock_path: Path) -> Mapping[str, Any]:
    """Recompute every lock, candidate, source, and selection invariant."""

    root = Path(root).resolve()
    lock_path = Path(case_lock_path).resolve()
    if not lock_path.is_file():
        raise FileNotFoundError(f"Day 11A case lock is missing: {lock_path}")
    run_dir = lock_path.parent
    pool_path = run_dir / "candidate_pool.csv"
    protocol_path = run_dir / "protocol_revision_manifest.json"
    config_path = root / "configs/stage2_failure/day11a_case_lock.yaml"
    required = (pool_path, protocol_path, config_path)
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Day 11A verification inputs are missing: {missing}")

    actual_hashes = {
        "candidate_pool_sha256": sha256_file(pool_path),
        "day11a_case_lock_sha256": sha256_file(lock_path),
        "protocol_revision_manifest_sha256": sha256_file(protocol_path),
    }
    expected_primary = {
        "candidate_pool_sha256": EXPECTED_CANDIDATE_POOL_SHA256,
        "day11a_case_lock_sha256": EXPECTED_CASE_LOCK_SHA256,
        "protocol_revision_manifest_sha256": EXPECTED_PROTOCOL_SHA256,
    }
    primary_mismatches = [
        name for name, expected in expected_primary.items() if actual_hashes[name] != expected
    ]
    if primary_mismatches:
        raise ValueError(f"Day 11A artifact hash mismatch: {primary_mismatches}")

    stage2c_paths = {
        "stage2c_test_manifest": root / "artifacts/current/weak_update_stage2c/test_manifest.json",
        "stage2c_update_lock": root / "artifacts/current/weak_update_stage2c/locked/update_lock.json",
        "stage2c_common_config": root / "configs/update/stage2c_common.yaml",
        "stage2c_test_config": root / "configs/update/stage2c_test.yaml",
        "stage2c_stress_config": root / "configs/update/stage2c_stress.yaml",
    }
    source_hashes = {name: sha256_file(path) for name, path in stage2c_paths.items()}
    source_mismatches = [
        name for name, expected in EXPECTED_STAGE2C_HASHES.items() if source_hashes[name] != expected
    ]
    if source_mismatches:
        raise ValueError(f"frozen Stage 2C source hash mismatch: {source_mismatches}")

    checkpoint_commit = _git_output(root, "rev-parse", f"{DAY11A_CHECKPOINT}^{{}}")
    stage2c_commit = _git_output(root, "rev-parse", f"{STAGE2C_TAG}^{{}}")
    head_commit = _git_output(root, "rev-parse", "HEAD")
    if checkpoint_commit != EXPECTED_DAY11A_COMMIT:
        raise ValueError("Day 11A checkpoint commit changed")
    if stage2c_commit != EXPECTED_STAGE2C_COMMIT:
        raise ValueError("frozen Stage 2C tag commit changed")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", DAY11A_CHECKPOINT, "HEAD"],
        cwd=str(root),
        check=False,
    ).returncode == 0
    if not ancestor:
        raise ValueError("HEAD does not descend from the Day 11A checkpoint")

    lock = _read_json(lock_path)
    protocol = _read_json(protocol_path)
    config = load_yaml(config_path)
    rows = _read_candidate_pool(pool_path)
    counts = validate_candidate_pool_rows(rows, 800, 800)
    validate_case_lock(lock, rows, actual_hashes["candidate_pool_sha256"], config)
    validate_protocol_revision_manifest(protocol)
    for name, path_field, hash_field in (
        ("stage2c_test_manifest", "stage2c_test_manifest_path", "stage2c_test_manifest_sha256"),
        ("stage2c_update_lock", "stage2c_update_lock_path", "stage2c_update_lock_sha256"),
        ("stage2c_common_config", "stage2c_common_config_path", "stage2c_common_config_sha256"),
        ("stage2c_test_config", "stage2c_test_config_path", "stage2c_test_config_sha256"),
        ("stage2c_stress_config", "stage2c_stress_config_path", "stage2c_stress_config_sha256"),
    ):
        if (root / str(lock[path_field])).resolve() != stage2c_paths[name].resolve():
            raise ValueError(f"case lock source path mismatch: {path_field}")
        if str(lock[hash_field]) != source_hashes[name]:
            raise ValueError(f"case lock source hash mismatch: {hash_field}")
    if str(lock["stage2c_commit"]) != stage2c_commit:
        raise ValueError("case lock Stage 2C commit mismatch")

    for sweep, expected in EXPECTED_CASES.items():
        actual = dict(lock[f"{sweep}_selected_case"])
        if any(actual.get(field) != value for field, value in expected.items()):
            raise ValueError(f"locked {sweep} case changed")
    conservative = {
        "history_recovery_pass": False,
        "history_trial_tables_available": False,
        "historical_representativeness_claim_allowed": False,
        "gross_outlier_control_replayed": False,
        "stress_name_alias_used": False,
        "legacy_stage2b_stress_name_used": False,
        "replay_performed": False,
    }
    for field, expected in conservative.items():
        if lock.get(field) is not expected:
            raise ValueError(f"unsafe Day 11A lock field: {field}")

    return {
        "schema_version": "stage2_failure_day11b_lock_verification_v1",
        "verification_pass": True,
        "head_commit": head_commit,
        "day11a_checkpoint_commit": checkpoint_commit,
        "head_descends_from_day11a_checkpoint": ancestor,
        "stage2c_tag": STAGE2C_TAG,
        "stage2c_commit": stage2c_commit,
        **actual_hashes,
        **{f"{name}_sha256": value for name, value in source_hashes.items()},
        "candidate_pool_row_count": len(rows),
        "geometry_candidate_count": 800,
        "observation_candidate_count": 800,
        **counts,
        "case_lock_field_mismatch_count": 0,
        "case_lock_hash_mismatch_count": 0,
        "case_selection_reproducibility_pass": True,
        "selected_geometry_case": dict(lock["geometry_selected_case"]),
        "selected_observation_case": dict(lock["observation_selected_case"]),
        "method_list": list(lock["required_methods"]),
        "replay_stress_list": list(lock["day11b_replay_stress_regimes"]),
        "allowed_stage2c_stress_list": list(lock["stage2c_allowed_stress_regimes"]),
        "expected_replay_count": int(lock["expected_day11b_method_replay_count"]),
    }


def _read_candidate_pool(path: Path) -> Sequence[Dict[str, Any]]:
    rows = []
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        for source in csv.DictReader(handle):
            row: Dict[str, Any] = dict(source)
            for field in ("candidate_index", "geometry_seed", "sensor_seed", "process_seed"):
                row[field] = int(row[field])
            selected = str(row["selected"]).strip().lower()
            if selected not in {"true", "false"}:
                raise ValueError("candidate pool selected field is not boolean")
            row["selected"] = selected == "true"
            rows.append(row)
    return rows


def _read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON mapping: {path}")
    return value


def _git_output(root: Path, *arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=str(root), text=True).strip()
