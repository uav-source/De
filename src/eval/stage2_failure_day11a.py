"""Day 11A protocol revision and deterministic diagnostic case locking."""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import numpy as np
import scipy
import yaml

from eval.stage2_failure_deterministic_case import (
    DAY11B_REPLAY_STRESS_REGIMES,
    HISTORICAL_TEST_EXECUTED_STRESS_REGIMES,
    LEGACY_STAGE2B_STRESS_NAME,
    REQUIRED_METHODS,
    SELECTION_ALGORITHM_VERSION,
    STAGE2C_ALLOWED_STRESS_REGIMES,
    build_candidate_pool,
    deterministic_case_index,
    select_case,
    selected_case_record,
    validate_stage2c_source_consistency,
)
from eval.stage2_failure_day11a_schema import (
    CANDIDATE_POOL_FIELDS,
    DAY11A_CONFIG_SCHEMA_VERSION,
    DAY11A_PROTOCOL_SCHEMA_VERSION,
    DAY11A_RUN_SCHEMA_VERSION,
    validate_candidate_pool_rows,
    validate_case_lock,
    validate_protocol_revision_manifest,
)


DAY10_CHECKPOINT = "checkpoint/day10-no-gt-audit-pass"
EXPECTED_DAY10_COMMIT = "04be262f91ffd67addcd2f24c1dd9a6904d5b2ef"
EXPECTED_STAGE2C_COMMIT = "ae90aaad51e72aa53ee0344047f9475fb51650a9"
EXPECTED_TEST_MANIFEST_SHA256 = (
    "355c4bcd82bb737462911bdc31156f087a65dd2043517a8cf5d225f17794ffde"
)
EXPECTED_UPDATE_LOCK_SHA256 = (
    "e19a1d9b84a597aeb6071cd8d8c3fa904829f9b671eff2e3bf031cc905e82fb1"
)
EXPECTED_RECOVERY_AUDIT_SHA256 = (
    "2d517ac3520c91f862fb48aadf8b0aadd5ce7cf3785b9661b1cddfcb1fb475b9"
)
HISTORICAL_ARTIFACT_PATHS = (
    "artifacts/current/detector_stage2a",
    "artifacts/history/stage2b_column_scaling_no_go",
    "artifacts/current/weak_update_stage2c",
)
DAY11A_SOURCE_PATHS = (
    "src/eval/stage2_failure_deterministic_case.py",
    "src/eval/stage2_failure_day11a.py",
    "src/eval/stage2_failure_day11a_schema.py",
    "scripts/35_run_stage2_failure_day11a.py",
)
FORBIDDEN_IMPORT_TOKENS = (
    "map_lio",
    "update_strategies",
    "stage2_failure_logging",
    "stage2_failure_gt_metrics",
    "stage2_failure_window_stats",
    "matplotlib",
    "sklearn",
    "weak_update_stage2c",
)
FORBIDDEN_SELECTION_NAMES = (
    "axis_rmse",
    "trajectory_rmse",
    "orientation_rmse",
    "strong_translation_rmse",
    "weak_innovation",
    "cusum",
    "run_length",
    "gt_error",
    "plot_score",
    "manual_seed",
    "manual_override",
    "oracle",
)
FORBIDDEN_RUNTIME_CALL_NAMES = (
    "run_map_lio",
    "Stage2FailureOnlineLogger",
    "evaluate_stage2_failure_gt",
    "compute_window_records",
    "run_stage2c",
)


def run_stage2_failure_day11a(
    root: Path,
    run_id: str,
    output_root: Path,
    overwrite: bool = False,
    config_path: Path = None,
) -> Mapping[str, Any]:
    """Create the Day 11A lock without executing an estimator or experiment."""

    root = Path(root).resolve()
    clean_at_start = git_status_clean(root)
    if not clean_at_start:
        raise RuntimeError("Day 11A refuses to run from a dirty Git worktree")
    config_path = (
        root / "configs/stage2_failure/day11a_case_lock.yaml"
        if config_path is None
        else Path(config_path).resolve()
    )
    config = load_yaml(config_path)
    validate_day11a_config(config)
    day10 = validate_day10_preconditions(root)
    recovery = validate_recovery_evidence(root)
    stage2c = validate_stage2c_sources(root, config)

    result_dir = Path(output_root).resolve() / str(run_id)
    if result_dir.exists():
        if not overwrite:
            raise FileExistsError(f"Day 11A output already exists: {result_dir}; use --overwrite")
        shutil.rmtree(result_dir)
    result_dir.mkdir(parents=True)

    historical_before = historical_artifact_hashes(root)
    source = stage2c["source_consistency"]
    geometry_base = build_candidate_pool(
        "geometry",
        config["geometry_candidate_levels"],
        source["test_geometry_seeds"],
        source["test_sensor_seeds"],
        source["test_process_seeds"],
    )
    observation_base = build_candidate_pool(
        "observation",
        config["observation_candidate_levels"],
        source["test_geometry_seeds"],
        source["test_sensor_seeds"],
        source["test_process_seeds"],
    )
    geometry_digest, geometry_index, geometry_rows = select_case(
        geometry_base,
        config["geometry_hash_label"],
    )
    observation_digest, observation_index, observation_rows = select_case(
        observation_base,
        config["observation_hash_label"],
    )
    candidate_rows = geometry_rows + observation_rows
    candidate_validation = validate_candidate_pool_rows(
        candidate_rows,
        len(geometry_rows),
        len(observation_rows),
    )
    expected_geometry_count = (
        len(config["geometry_candidate_levels"])
        * len(source["test_geometry_seeds"])
        * len(source["test_sensor_seeds"])
        * len(source["test_process_seeds"])
    )
    expected_observation_count = (
        len(config["observation_candidate_levels"])
        * len(source["test_geometry_seeds"])
        * len(source["test_sensor_seeds"])
        * len(source["test_process_seeds"])
    )
    if len(geometry_rows) != expected_geometry_count:
        raise RuntimeError("Geometry candidate count differs from the frozen seed product")
    if len(observation_rows) != expected_observation_count:
        raise RuntimeError("Observation candidate count differs from the frozen seed product")

    reversed_geometry = build_candidate_pool(
        "geometry",
        list(reversed(config["geometry_candidate_levels"])),
        list(reversed(source["test_geometry_seeds"])),
        list(reversed(source["test_sensor_seeds"])),
        list(reversed(source["test_process_seeds"])),
    )
    reversed_observation = build_candidate_pool(
        "observation",
        list(reversed(config["observation_candidate_levels"])),
        list(reversed(source["test_geometry_seeds"])),
        list(reversed(source["test_sensor_seeds"])),
        list(reversed(source["test_process_seeds"])),
    )
    order_independence = (
        geometry_base == reversed_geometry and observation_base == reversed_observation
    )
    reproducibility = (
        deterministic_case_index(config["geometry_hash_label"], len(geometry_rows))
        == (geometry_digest, geometry_index)
        and deterministic_case_index(
            config["observation_hash_label"], len(observation_rows)
        )
        == (observation_digest, observation_index)
    )

    candidate_pool_path = result_dir / "candidate_pool.csv"
    write_candidate_pool(candidate_pool_path, candidate_rows)
    reread_rows = read_candidate_pool(candidate_pool_path)
    validate_candidate_pool_rows(
        reread_rows,
        len(geometry_rows),
        len(observation_rows),
    )
    candidate_pool_sha256 = sha256_file(candidate_pool_path)

    protocol_manifest = build_protocol_revision_manifest(recovery)
    validate_protocol_revision_manifest(protocol_manifest)
    protocol_path = result_dir / "protocol_revision_manifest.json"
    write_json(protocol_path, protocol_manifest)

    dependency_audit = audit_forbidden_dependencies(root)
    dependency_path = result_dir / "day11a_forbidden_dependency_audit.json"
    write_json(dependency_path, dependency_audit)

    geometry_selected = geometry_rows[geometry_index]
    observation_selected = observation_rows[observation_index]
    source_tree_sha256 = compute_source_tree_sha256(root)
    clean_at_lock = git_status_clean(root)
    lock = {
        "schema_version": DAY11A_CONFIG_SCHEMA_VERSION,
        "lock_type": "preregistered_deterministic_diagnostic_cases",
        "selection_algorithm_version": SELECTION_ALGORITHM_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "protocol_revision_reason": "historical Stage 2C trial-level provenance was not retained",
        "history_recovery_pass": False,
        "history_trial_tables_available": False,
        "historical_representativeness_claim_allowed": False,
        "stage2c_tag": str(config["stage2c_tag"]),
        "stage2c_commit": str(config["expected_stage2c_commit"]),
        "stage2c_test_manifest_path": stage2c["test_manifest_path"],
        "stage2c_test_manifest_sha256": stage2c["test_manifest_sha256"],
        "stage2c_update_lock_path": stage2c["update_lock_path"],
        "stage2c_update_lock_sha256": stage2c["update_lock_sha256"],
        "stage2c_common_config_path": stage2c["common_config_path"],
        "stage2c_common_config_sha256": stage2c["common_config_sha256"],
        "stage2c_test_config_path": stage2c["test_config_path"],
        "stage2c_test_config_sha256": stage2c["test_config_sha256"],
        "stage2c_stress_config_path": stage2c["stress_config_path"],
        "stage2c_stress_config_sha256": stage2c["stress_config_sha256"],
        "seed_source_consistency_pass": True,
        "stress_source_validation_pass": True,
        "test_geometry_seeds": source["test_geometry_seeds"],
        "test_sensor_seeds": source["test_sensor_seeds"],
        "test_process_seeds": source["test_process_seeds"],
        "stage2c_allowed_stress_regimes": list(STAGE2C_ALLOWED_STRESS_REGIMES),
        "historical_test_executed_stress_regimes": list(
            HISTORICAL_TEST_EXECUTED_STRESS_REGIMES
        ),
        "day11b_replay_stress_regimes": list(DAY11B_REPLAY_STRESS_REGIMES),
        "gross_outlier_control_replayed": False,
        "stress_name_alias_used": False,
        "legacy_stage2b_stress_name_used": False,
        "geometry_candidate_levels": list(config["geometry_candidate_levels"]),
        "geometry_candidate_count": len(geometry_rows),
        "geometry_hash_label": str(config["geometry_hash_label"]),
        "geometry_hash_digest_hex": geometry_digest,
        "geometry_hash_integer_decimal": str(
            int.from_bytes(bytes.fromhex(geometry_digest), "big", signed=False)
        ),
        "geometry_selected_index": geometry_index,
        "geometry_selected_case": selected_case_record(geometry_selected),
        "observation_candidate_levels": list(config["observation_candidate_levels"]),
        "observation_candidate_count": len(observation_rows),
        "observation_hash_label": str(config["observation_hash_label"]),
        "observation_hash_digest_hex": observation_digest,
        "observation_hash_integer_decimal": str(
            int.from_bytes(bytes.fromhex(observation_digest), "big", signed=False)
        ),
        "observation_selected_index": observation_index,
        "observation_selected_case": selected_case_record(observation_selected),
        "required_methods": list(REQUIRED_METHODS),
        "required_stress_regimes": list(DAY11B_REPLAY_STRESS_REGIMES),
        "required_replay_stress_regimes": list(DAY11B_REPLAY_STRESS_REGIMES),
        "expected_day11b_method_replay_count": 8,
        "candidate_pool_path": "candidate_pool.csv",
        "candidate_pool_sha256": candidate_pool_sha256,
        "selection_used_metrics": False,
        "selection_used_innovation": False,
        "selection_used_cusum": False,
        "selection_used_gt_error": False,
        "selection_used_plot_visibility": False,
        "selection_used_manual_override": False,
        "selection_used_random_sampling": False,
        "replay_performed": False,
        "figures_generated": False,
        "threshold_created": False,
        "auroc_computed": False,
        "fpr_computed": False,
        "f1_computed": False,
        "fast_lio2_integrated": False,
        "git_branch": git_branch(root),
        "git_commit_at_lock": git_commit(root),
        "git_status_clean_at_lock": clean_at_lock,
        "source_tree_sha256": source_tree_sha256,
        "day11a_config_sha256": sha256_file(config_path),
    }
    lock_path = result_dir / "deterministic_diagnostic_case_lock.json"
    write_json(lock_path, lock)
    lock_bytes_before_validation = lock_path.read_bytes()
    reread_lock = read_json(lock_path)
    validate_case_lock(reread_lock, reread_rows, candidate_pool_sha256, config)
    clean_after_lock_write = git_status_clean(root)
    if not clean_after_lock_write or clean_after_lock_write != clean_at_lock:
        raise RuntimeError("Day 11A worktree changed while writing the case lock")
    lock_roundtrip_pass = lock_path.read_bytes() == lock_bytes_before_validation

    historical_after = historical_artifact_hashes(root)
    historical_unchanged = historical_before == historical_after
    metrics = {
        "git_status_clean_at_start": clean_at_start,
        "git_status_clean_at_lock": clean_at_lock,
        **day10,
        "stage2c_source_verified": bool(stage2c["stage2c_source_verified"]),
        "recovery_audit_pass": False,
        "history_trial_tables_available": False,
        "seed_source_consistency_pass": True,
        "stress_source_validation_pass": True,
        "day11b_replay_matches_historical_test_stress": (
            list(DAY11B_REPLAY_STRESS_REGIMES)
            == list(HISTORICAL_TEST_EXECUTED_STRESS_REGIMES)
        ),
        "expected_day11b_method_replay_count": 8,
        "candidate_duplicate_count": candidate_validation["candidate_duplicate_count"],
        "geometry_selected_row_count": candidate_validation[
            "geometry_selected_row_count"
        ],
        "observation_selected_row_count": candidate_validation[
            "observation_selected_row_count"
        ],
        "lock_roundtrip_pass": lock_roundtrip_pass,
        "selection_reproducibility_pass": reproducibility,
        "candidate_order_independence_pass": order_independence,
        "forbidden_dependency_audit_pass": bool(dependency_audit["audit_pass"]),
        "ast_parse_failure_count": int(dependency_audit["ast_parse_failure_count"]),
        "forbidden_import_count": len(dependency_audit["forbidden_imports"]),
        "forbidden_selection_parameter_count": len(
            dependency_audit["forbidden_selection_parameters"]
        ),
        "forbidden_runtime_call_count": len(
            dependency_audit["forbidden_runtime_calls"]
        ),
        "selection_used_metrics": False,
        "selection_used_innovation": False,
        "selection_used_cusum": False,
        "selection_used_gt_error": False,
        "selection_used_plot_visibility": False,
        "selection_used_manual_override": False,
        "selection_used_random_sampling": False,
        "stress_name_alias_used": False,
        "legacy_stage2b_stress_name_used": False,
        "gross_outlier_control_replayed": False,
        "replay_performed": False,
        "estimator_imported": False,
        "gt_evaluator_imported": False,
        "window_statistics_imported": False,
        "figures_generated": False,
        "threshold_created": False,
        "auroc_computed": False,
        "fpr_computed": False,
        "f1_computed": False,
        "fast_lio2_integrated": False,
        "historical_artifacts_unchanged": historical_unchanged,
    }
    day11a_pass = evaluate_day11a_gate(metrics)
    summary = {
        "run_id": str(run_id),
        "schema_version": DAY11A_RUN_SCHEMA_VERSION,
        **metrics,
        "geometry_candidate_count": len(geometry_rows),
        "observation_candidate_count": len(observation_rows),
        "geometry_selected_index": geometry_index,
        "observation_selected_index": observation_index,
        "geometry_selected_case": selected_case_record(geometry_selected),
        "observation_selected_case": selected_case_record(observation_selected),
        "stage2c_allowed_stress_regimes": list(STAGE2C_ALLOWED_STRESS_REGIMES),
        "historical_test_executed_stress_regimes": list(
            HISTORICAL_TEST_EXECUTED_STRESS_REGIMES
        ),
        "day11b_replay_stress_regimes": list(DAY11B_REPLAY_STRESS_REGIMES),
        "DAY11A_CASE_LOCK_PASS": day11a_pass,
        "DAY11B_DETERMINISTIC_REPLAY_AUTHORIZED": day11a_pass,
        "STAGE2C_HISTORY_RECOVERY_PASS": False,
        "DAY11_REPLAY_PASS": False,
        "DAY12_DIAGNOSTIC_FIGURES_AUTHORIZED": False,
        "STAGE2_GATE": "INCOMPLETE",
        "STAGE3_GATE": "NOT_STARTED",
        "COHERENT_BIAS_DETECTABLE": "UNDETERMINED",
        "RISK_WARNING_AUTHORIZED": False,
        "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
        "PUBLIC_DISCLOSURE_AUTHORIZED": False,
    }
    summary_path = result_dir / "day11a_summary.json"
    write_json(summary_path, summary)
    manifest = {
        **summary,
        "task": "Stage 2 Failure-Mechanism Diagnosis — Day 11A",
        "git_branch": git_branch(root),
        "git_commit": git_commit(root),
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "day10_checkpoint_commit": day10["day10_checkpoint_commit"],
        "stage2c_tag": str(config["stage2c_tag"]),
        "stage2c_commit": str(config["expected_stage2c_commit"]),
        "candidate_pool_sha256": candidate_pool_sha256,
        "case_lock_sha256": sha256_file(lock_path),
        "protocol_revision_manifest_sha256": sha256_file(protocol_path),
        "forbidden_dependency_audit_sha256": sha256_file(dependency_path),
        "historical_artifact_hashes_before": historical_before,
        "historical_artifact_hashes_after": historical_after,
        "recovery_audit_archive_present": recovery[
            "recovery_audit_archive_present"
        ],
        "recovery_audit_archive_hash_verified": recovery[
            "recovery_audit_archive_hash_verified"
        ],
        "source_tree_sha256": source_tree_sha256,
        "day11a_config_sha256": sha256_file(config_path),
    }
    write_json(result_dir / "run_manifest.json", manifest)
    return manifest


def validate_day11a_config(config: Mapping[str, Any]) -> None:
    expected = {
        "mode": "day11a_deterministic_case_lock",
        "schema_version": DAY11A_CONFIG_SCHEMA_VERSION,
        "stage2c_tag": "archive/stage2c-projected-gain-no-go",
        "expected_stage2c_commit": EXPECTED_STAGE2C_COMMIT,
        "history_recovery_pass": False,
        "selection_algorithm_version": SELECTION_ALGORITHM_VERSION,
        "geometry_hash_label": (
            "Degen-LIO-Day11R1|ae90aaad51e72aa53ee0344047f9475fb51650a9|geometry"
        ),
        "observation_hash_label": (
            "Degen-LIO-Day11R1|ae90aaad51e72aa53ee0344047f9475fb51650a9|observation"
        ),
        "geometry_candidate_levels": ["L3", "L4"],
        "observation_candidate_levels": ["O3", "O4"],
        "required_methods": list(REQUIRED_METHODS),
        "required_replay_stress_regimes": list(DAY11B_REPLAY_STRESS_REGIMES),
        "allowed_stage2c_stress_regimes": list(STAGE2C_ALLOWED_STRESS_REGIMES),
        "expected_day11b_method_replay_count": 8,
        "selection_uses_metrics": False,
        "selection_uses_innovation": False,
        "selection_uses_cusum": False,
        "selection_uses_gt_error": False,
        "selection_uses_plot_visibility": False,
        "selection_uses_manual_override": False,
        "run_replay": False,
        "generate_figures": False,
        "create_detection_threshold": False,
        "compute_auroc": False,
        "compute_fpr": False,
        "compute_f1": False,
        "fast_lio2_integrated": False,
    }
    missing = sorted(set(expected) - set(config))
    extra = sorted(set(config) - set(expected))
    if missing or extra:
        raise ValueError(f"Day 11A config fields are frozen: missing={missing}, extra={extra}")
    for field, expected_value in expected.items():
        value = config.get(field)
        if value != expected_value or type(value) is not type(expected_value):
            raise ValueError(f"Day 11A freezes {field}={expected_value!r}")
    if LEGACY_STAGE2B_STRESS_NAME in json.dumps(config, sort_keys=True):
        raise ValueError("legacy Stage 2B stress name is forbidden in Day 11A")
    replay_count = (
        2
        * len(config["required_replay_stress_regimes"])
        * len(config["required_methods"])
    )
    if replay_count != int(config["expected_day11b_method_replay_count"]):
        raise ValueError("Day 11B replay matrix must contain exactly eight method replays")


def validate_day10_preconditions(root: Path) -> Mapping[str, Any]:
    root = Path(root).resolve()
    run_dir = root / (
        "results/stage2_failure_analysis/day10_quick/"
        "stage2_failure_day10_quick_v2"
    )
    manifest_path = run_dir / "run_manifest.json"
    summary_path = run_dir / "day10_quick_summary.json"
    if not manifest_path.is_file() or not summary_path.is_file():
        raise FileNotFoundError("Day 11A requires the passing Day 10 v2 evidence")
    manifest = read_json(manifest_path)
    summary = read_json(summary_path)
    required = {
        "DAY10_NO_GT_AUDIT_PASS": True,
        "day9_precondition_pass": True,
        "head_descends_from_day9_checkpoint": True,
        "non_oracle_method_list_pass": True,
        "static_audit_pass": True,
        "gt_field_access_attempt_count": 0,
        "online_equivalence_failure_count": 0,
        "window_equivalence_failure_count": 0,
        "frame_diagnostics_failure_count": 0,
        "solver_failure_count_control": 0,
        "solver_failure_count_variant_total": 0,
        "filesystem_sandbox_pass": True,
        "invalid_reset_end_to_end_pass": True,
        "output_schema_pass": True,
        "reserved_test_run_performed": False,
        "formal_stage2c_rerun_performed": False,
        "representative_stage2c_seed_replayed": False,
        "detection_threshold_created": False,
        "auroc_computed": False,
        "fpr_computed": False,
        "fast_lio2_integrated": False,
    }
    failures = []
    for filename, value in (("manifest", manifest), ("summary", summary)):
        for field, expected in required.items():
            if value.get(field) != expected or type(value.get(field)) is not type(expected):
                failures.append(f"{filename}.{field}")
    checkpoint_commit = git_ref_commit(root, DAY10_CHECKPOINT)
    if checkpoint_commit != EXPECTED_DAY10_COMMIT:
        failures.append("Day 10 checkpoint commit")
    descends = git_is_ancestor(root, checkpoint_commit, git_commit(root))
    if not descends:
        failures.append("HEAD ancestry")
    if failures:
        raise RuntimeError("Day 10 precondition validation failed: " + ", ".join(failures))
    return {
        "day10_precondition_pass": True,
        "head_descends_from_day10_checkpoint": descends,
        "day10_checkpoint_commit": checkpoint_commit,
    }


def validate_recovery_evidence(root: Path) -> Mapping[str, Any]:
    archive = Path("/tmp/Degen-LIO-Stage2C-recovery-audit.tar.gz")
    present = archive.is_file()
    verified = present and sha256_file(archive) == EXPECTED_RECOVERY_AUDIT_SHA256
    if present and not verified:
        raise RuntimeError("Stage 2C recovery audit archive hash mismatch")
    missing_paths = [
        root / "results/weak_update_stage2c/test/weak_update_stage2c_test_v1/tables/method_trial_summary.csv",
        root / "results/weak_update_stage2c/test/weak_update_stage2c_test_v1/tables/paired_method_differences.csv",
        root / "data/weak_update_stage2c/test/weak_update_stage2c_test_v1",
    ]
    if any(path.exists() for path in missing_paths):
        raise RuntimeError("historical Stage 2C trial-level source unexpectedly exists")
    return {
        "recovery_audit_performed": True,
        "recovery_audit_pass": False,
        "recovery_audit_archive_present": present,
        "recovery_audit_archive_sha256": sha256_file(archive) if present else None,
        "recovery_audit_archive_hash_verified": verified,
        "missing_files": [str(path.relative_to(root)) for path in missing_paths],
    }


def validate_stage2c_sources(
    root: Path,
    config: Mapping[str, Any],
) -> Mapping[str, Any]:
    root = Path(root).resolve()
    paths = {
        "test_manifest": root / "artifacts/current/weak_update_stage2c/test_manifest.json",
        "update_lock": root / "artifacts/current/weak_update_stage2c/locked/update_lock.json",
        "common_config": root / "configs/update/stage2c_common.yaml",
        "test_config": root / "configs/update/stage2c_test.yaml",
        "stress_config": root / "configs/update/stage2c_stress.yaml",
    }
    for name, path in paths.items():
        if not path.is_file():
            raise FileNotFoundError(f"frozen Stage 2C {name} is missing: {path}")
    stage2c_commit = git_ref_commit(root, str(config["stage2c_tag"]))
    if stage2c_commit != EXPECTED_STAGE2C_COMMIT:
        raise RuntimeError("frozen Stage 2C tag commit mismatch")
    if sha256_file(paths["test_manifest"]) != EXPECTED_TEST_MANIFEST_SHA256:
        raise RuntimeError("frozen Stage 2C Test manifest hash mismatch")
    if sha256_file(paths["update_lock"]) != EXPECTED_UPDATE_LOCK_SHA256:
        raise RuntimeError("frozen Stage 2C update lock hash mismatch")
    manifest = read_json(paths["test_manifest"])
    update_lock = read_json(paths["update_lock"])
    common = load_yaml(paths["common_config"])
    test_config = load_yaml(paths["test_config"])
    stress_config = load_yaml(paths["stress_config"])
    if not git_is_ancestor(root, str(manifest.get("git_commit", "")), stage2c_commit):
        raise RuntimeError("Stage 2C Test manifest commit is outside the frozen history")
    if not git_is_ancestor(
        root,
        str(update_lock.get("git_commit_at_lock", "")),
        stage2c_commit,
    ):
        raise RuntimeError("Stage 2C update lock commit is outside the frozen history")
    source_consistency = validate_stage2c_source_consistency(
        test_config,
        manifest,
        update_lock,
        stress_config,
    )
    if not set(REQUIRED_METHODS).issubset(set(common.get("method_list", []))):
        raise RuntimeError("Stage 2C common config lacks required methods")
    for name in ("common_config", "test_config", "stress_config"):
        relative = str(paths[name].relative_to(root))
        locked_hash = (update_lock.get("source_file_hashes") or {}).get(relative)
        if locked_hash != sha256_file(paths[name]):
            raise RuntimeError(f"Stage 2C frozen source hash mismatch: {relative}")
    output: Dict[str, Any] = {
        "stage2c_source_verified": True,
        "stage2c_commit": stage2c_commit,
        "source_consistency": source_consistency,
    }
    for name, path in paths.items():
        output[f"{name}_path"] = str(path.relative_to(root))
        output[f"{name}_sha256"] = sha256_file(path)
    return output


def audit_forbidden_dependencies(root: Path) -> Mapping[str, Any]:
    root = Path(root).resolve()
    parse_failures: List[str] = []
    forbidden_imports: List[str] = []
    forbidden_parameters: List[str] = []
    forbidden_calls: List[str] = []
    audited_files = []
    for relative in DAY11A_SOURCE_PATHS:
        path = root / relative
        audited_files.append(relative)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        except (OSError, SyntaxError) as exc:
            parse_failures.append(f"{relative}:{exc}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                modules = []
            for module in modules:
                if any(token in module for token in FORBIDDEN_IMPORT_TOKENS):
                    forbidden_imports.append(f"{relative}:{node.lineno}:{module}")
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                arguments = list(node.args.args) + list(node.args.kwonlyargs)
                if node.args.vararg is not None:
                    arguments.append(node.args.vararg)
                if node.args.kwarg is not None:
                    arguments.append(node.args.kwarg)
                for argument in arguments:
                    if argument.arg in FORBIDDEN_SELECTION_NAMES:
                        forbidden_parameters.append(
                            f"{relative}:{node.lineno}:{argument.arg}"
                        )
            if isinstance(node, ast.Call):
                call_name = _ast_call_name(node.func)
                if call_name.split(".")[-1] in FORBIDDEN_RUNTIME_CALL_NAMES:
                    forbidden_calls.append(f"{relative}:{node.lineno}:{call_name}")
    return {
        "audited_files": audited_files,
        "ast_parse_failure_count": len(parse_failures),
        "parse_failures": parse_failures,
        "forbidden_imports": forbidden_imports,
        "forbidden_selection_parameters": forbidden_parameters,
        "forbidden_runtime_calls": forbidden_calls,
        "audit_pass": not (
            parse_failures or forbidden_imports or forbidden_parameters or forbidden_calls
        ),
    }


def evaluate_day11a_gate(values: Mapping[str, Any]) -> bool:
    required_true = (
        "git_status_clean_at_start",
        "git_status_clean_at_lock",
        "day10_precondition_pass",
        "head_descends_from_day10_checkpoint",
        "stage2c_source_verified",
        "seed_source_consistency_pass",
        "stress_source_validation_pass",
        "day11b_replay_matches_historical_test_stress",
        "lock_roundtrip_pass",
        "selection_reproducibility_pass",
        "candidate_order_independence_pass",
        "forbidden_dependency_audit_pass",
        "historical_artifacts_unchanged",
    )
    required_false = (
        "recovery_audit_pass",
        "history_trial_tables_available",
        "selection_used_metrics",
        "selection_used_innovation",
        "selection_used_cusum",
        "selection_used_gt_error",
        "selection_used_plot_visibility",
        "selection_used_manual_override",
        "selection_used_random_sampling",
        "stress_name_alias_used",
        "legacy_stage2b_stress_name_used",
        "gross_outlier_control_replayed",
        "replay_performed",
        "estimator_imported",
        "gt_evaluator_imported",
        "window_statistics_imported",
        "figures_generated",
        "threshold_created",
        "auroc_computed",
        "fpr_computed",
        "f1_computed",
        "fast_lio2_integrated",
    )
    required_zero = (
        "ast_parse_failure_count",
        "forbidden_import_count",
        "forbidden_selection_parameter_count",
        "forbidden_runtime_call_count",
        "candidate_duplicate_count",
    )
    return bool(
        all(values.get(name) is True for name in required_true)
        and all(values.get(name) is False for name in required_false)
        and all(int(values.get(name, -1)) == 0 for name in required_zero)
        and int(values.get("geometry_selected_row_count", -1)) == 1
        and int(values.get("observation_selected_row_count", -1)) == 1
        and int(values.get("expected_day11b_method_replay_count", -1)) == 8
    )


def build_protocol_revision_manifest(
    recovery: Mapping[str, Any],
) -> Mapping[str, Any]:
    return {
        "schema_version": DAY11A_PROTOCOL_SCHEMA_VERSION,
        "revision_id": "stage2_day11r1_missing_trial_provenance",
        "previous_protocol": "historical representative seed replay",
        "revised_protocol": "preregistered deterministic diagnostic case replay",
        "reason": "historical Stage 2C trial-level outputs were not retained",
        "missing_files": list(recovery["missing_files"]),
        "recovery_audit_performed": True,
        "recovery_audit_pass": False,
        "recovery_audit_archive_present": bool(
            recovery["recovery_audit_archive_present"]
        ),
        "recovery_audit_archive_sha256": recovery[
            "recovery_audit_archive_sha256"
        ],
        "recovery_audit_archive_hash_verified": bool(
            recovery["recovery_audit_archive_hash_verified"]
        ),
        "historical_test_completed_claim": True,
        "historical_trial_level_results_available": False,
        "historical_aggregate_results_available": True,
        "trial_level_results_reconstructed": False,
        "trial_level_results_inferred": False,
        "representative_seed_claim_retained": False,
        "day11_case_claim": "mechanism-oriented deterministic diagnostic cases only",
        "day12_figure_claim": "diagnostic visualization only, not representative statistics",
        "day13_role": "primary new-seed multi-case statistical diagnosis",
        "STAGE2C_HISTORY_RECOVERY_PASS": False,
        "DAY11_REPLAY_PASS": False,
        "DAY12_DIAGNOSTIC_FIGURES_AUTHORIZED": False,
    }


def write_candidate_pool(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANDIDATE_POOL_FIELDS)
        writer.writeheader()
        for raw in rows:
            row = dict(raw)
            row["selected"] = "true" if bool(row["selected"]) else "false"
            writer.writerow(row)


def read_candidate_pool(path: Path) -> List[Dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def historical_artifact_hashes(root: Path) -> Mapping[str, str]:
    return {
        relative: compute_directory_sha256(Path(root) / relative)
        for relative in HISTORICAL_ARTIFACT_PATHS
    }


def compute_directory_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    for candidate in sorted(value for value in Path(path).rglob("*") if value.is_file()):
        relative = str(candidate.relative_to(path))
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(candidate).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def compute_source_tree_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for relative in sorted(
        list(DAY11A_SOURCE_PATHS)
        + [
            "configs/stage2_failure/day11a_case_lock.yaml",
            "docs/stage2_day11_protocol_revision_missing_trial_provenance.md",
            "docs/stage2_day11a_deterministic_case_lock_contract.md",
        ]
    ):
        path = Path(root) / relative
        if not path.is_file():
            raise FileNotFoundError(f"Day 11A source hash input is missing: {path}")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(path).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def scientific_lock_content(lock: Mapping[str, Any]) -> Mapping[str, Any]:
    output = dict(lock)
    output.pop("created_at", None)
    return output


def load_yaml(path: Path) -> Dict[str, Any]:
    value = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected YAML mapping in {path}")
    return value


def read_json(path: Path) -> Dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON mapping in {path}")
    return value


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_status_clean(root: Path) -> bool:
    return not subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=root, text=True
    ).strip()


def git_commit(root: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()


def git_branch(root: Path) -> str:
    return subprocess.check_output(
        ["git", "branch", "--show-current"], cwd=root, text=True
    ).strip()


def git_ref_commit(root: Path, reference: str) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", f"{reference}^{{}}"], cwd=root, text=True
    ).strip()


def git_is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode
        == 0
    )


def _ast_call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _ast_call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""
