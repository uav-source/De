"""Strict read-only audit of the frozen Day 11B v2 plotting input."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

from eval.stage2_failure_day11b_provenance import result_tree_manifest
from eval.stage2_failure_day12_schema import (
    EXPECTED_METHODS,
    EXPECTED_STRESSES,
    EXPECTED_SWEEPS,
    INPUT_AUDIT_SCHEMA_VERSION,
)
from eval.stage2_failure_schema import ONLINE_SCHEMA_VERSION
from eval.stage2_failure_window_schema import (
    WINDOW_FIELDS,
    WINDOW_SCHEMA_VERSION,
    validate_window_record,
)


REQUIRED_TOP_LEVEL = (
    "case_lock_verification.json", "replay_plan.csv", "replay_plan.json",
    "logging_equivalence_audit.csv", "pairing_audit.csv", "stress_mechanism_audit.csv",
    "no_gt_audit.json", "strategy_chain_audit.csv", "axial_support_audit.csv",
    "axial_support_summary.json", "base_observation_pairing_audit.csv",
    "v1_v2_scientific_equivalence_audit.csv", "replay_case_summary.csv",
    "replay_frame_diagnostics_merged.csv", "day11b_v2_summary.json", "run_manifest.json",
)
REQUIRED_CASE_FILES = (
    "frame_diagnostics_online.csv", "frame_diagnostics_gt.csv",
    "frame_window_statistics.csv", "frame_stress_trace.csv", "trajectory_metrics.json",
    "case_manifest.json", "strategy_chain_audit.json",
)
PRIMARY_KEY = (
    "case_id", "sweep", "level", "stress", "geometry_seed", "sensor_seed",
    "process_seed", "method", "frame_index", "timestamp",
)
EXTERNAL_KEY = (
    "sweep", "level", "geometry_seed", "sensor_seed", "process_seed", "stress",
    "frame_index",
)
BASE_FIELDS = (
    "points_lidar_base_checksum", "normals_world_base_checksum", "R_diag_list_checksum",
    "plane_points_world_base_checksum", "plane_points_world_stressed_checksum",
)
HASH_FILES = {
    "day11b_manifest_sha256": "run_manifest.json",
    "day11b_summary_sha256": "day11b_v2_summary.json",
    "replay_plan_sha256": "replay_plan.csv",
    "replay_case_summary_sha256": "replay_case_summary.csv",
    "merged_csv_sha256": "replay_frame_diagnostics_merged.csv",
    "logging_equivalence_audit_sha256": "logging_equivalence_audit.csv",
    "pairing_audit_sha256": "pairing_audit.csv",
    "stress_mechanism_audit_sha256": "stress_mechanism_audit.csv",
    "no_gt_audit_sha256": "no_gt_audit.json",
    "strategy_chain_audit_sha256": "strategy_chain_audit.csv",
    "axial_support_audit_sha256": "axial_support_audit.csv",
    "axial_support_summary_sha256": "axial_support_summary.json",
    "base_observation_pairing_audit_sha256": "base_observation_pairing_audit.csv",
    "v1_v2_scientific_equivalence_audit_sha256": "v1_v2_scientific_equivalence_audit.csv",
}
LOCKED_DAY11B_SOURCE_FILES = {
    "day11b_manifest": ("day11b_manifest_path", "day11b_manifest_sha256", "run_manifest.json"),
    "day11b_summary": ("day11b_summary_path", "day11b_summary_sha256", "day11b_v2_summary.json"),
    "replay_plan": ("replay_plan_path", "replay_plan_sha256", "replay_plan.csv"),
    "replay_case_summary": (
        "replay_case_summary_path", "replay_case_summary_sha256", "replay_case_summary.csv",
    ),
    "merged_csv": ("merged_csv_path", "merged_csv_sha256", "replay_frame_diagnostics_merged.csv"),
    "logging_equivalence_audit": (
        "logging_equivalence_audit_path", "logging_equivalence_audit_sha256",
        "logging_equivalence_audit.csv",
    ),
    "pairing_audit": ("pairing_audit_path", "pairing_audit_sha256", "pairing_audit.csv"),
    "stress_mechanism_audit": (
        "stress_mechanism_audit_path", "stress_mechanism_audit_sha256",
        "stress_mechanism_audit.csv",
    ),
    "no_gt_audit": ("no_gt_audit_path", "no_gt_audit_sha256", "no_gt_audit.json"),
    "strategy_chain_audit": (
        "strategy_chain_audit_path", "strategy_chain_audit_sha256", "strategy_chain_audit.csv",
    ),
    "axial_support_audit": (
        "axial_support_audit_path", "axial_support_audit_sha256", "axial_support_audit.csv",
    ),
    "base_observation_pairing_audit": (
        "base_observation_pairing_audit_path", "base_observation_pairing_audit_sha256",
        "base_observation_pairing_audit.csv",
    ),
    "v1_v2_scientific_equivalence_audit": (
        "v1_v2_scientific_equivalence_audit_path",
        "v1_v2_scientific_equivalence_audit_sha256",
        "v1_v2_scientific_equivalence_audit.csv",
    ),
}
DAY11B_V2_CHECKPOINT_COMMIT = "480960def270d2739a21bfc4967990318d2ed3c3"


class LockedInputPathError(ValueError):
    """A locked path is unsafe or does not name the frozen file."""


class LockedInputMissingError(ValueError):
    """A locked source file is missing."""


class LockedInputSymlinkError(ValueError):
    """A locked source path contains a symbolic link."""


def resolve_locked_input_file(run_dir: Path, relative_path: str) -> Path:
    """Resolve a locked relative file without permitting escape or symlinks."""

    root = Path(run_dir).resolve()
    text = str(relative_path)
    candidate_relative = Path(text)
    if not text or candidate_relative.is_absolute():
        raise LockedInputPathError("locked source path must be relative")
    if ".." in candidate_relative.parts:
        raise LockedInputPathError("locked source path traversal is forbidden")
    candidate = root / candidate_relative
    current = candidate
    while current != root:
        if current.is_symlink():
            raise LockedInputSymlinkError(f"locked source path is a symlink: {text}")
        if current.parent == current:
            break
        current = current.parent
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise LockedInputPathError("locked source resolves outside its run directory") from exc
    if not candidate.exists():
        raise LockedInputMissingError(f"locked source file is missing: {text}")
    if not candidate.is_file():
        raise LockedInputPathError(f"locked source is not a regular file: {text}")
    return resolved


def verify_day11b_v2_plot_input(
    root: Path,
    run_dir: Path,
    frozen_tree_manifest_path: Optional[Path] = None,
) -> Mapping[str, Any]:
    root = Path(root).resolve()
    run_dir = Path(run_dir).resolve()
    checks = []

    def record(name: str, passed: bool, detail: Any = "") -> None:
        checks.append({"check": name, "pass": bool(passed), "detail": str(detail)})

    record("v2_path", run_dir.name == "stage2_failure_day11b_replay_v2" and "v1" not in run_dir.name)
    missing = [name for name in REQUIRED_TOP_LEVEL if not (run_dir / name).is_file()]
    record("required_top_level_files", not missing, ",".join(missing))
    if missing:
        return _failed_result(run_dir, checks, missing)

    manifest = _read_json(run_dir / "run_manifest.json")
    summary = _read_json(run_dir / "day11b_v2_summary.json")
    record("manifest_summary_equal", manifest == summary)
    record(
        "manifest_checkpoint_commit",
        manifest.get("git_commit") == DAY11B_V2_CHECKPOINT_COMMIT,
        manifest.get("git_commit"),
    )
    expected_values = {
        "DAY11B_V1_RUNTIME_RESULT": "PASS", "DAY11B_V1_PROVENANCE_COMPLETE": False,
        "DAY11B_V2_RUNTIME_RESULT": "PASS", "DAY11B_V2_PROVENANCE_COMPLETE": True,
        "DAY11B_V2_PROVENANCE_PASS": True, "DAY11B_DETERMINISTIC_REPLAY_PASS": True,
        "DAY11_REPLAY_PASS": True, "DAY12_DIAGNOSTIC_FIGURES_AUTHORIZED": True,
        "STAGE2_GATE": "INCOMPLETE", "STAGE3_GATE": "NOT_STARTED",
        "COHERENT_BIAS_DETECTABLE": "UNDETERMINED", "completed_replay_count": 8,
        "solver_failure_count": 0, "pairing_violation_count": 0,
        "logging_equivalence_failure_count": 0, "gt_field_access_attempt_count": 0,
        "duplicate_frame_key_count": 0, "missing_frame_key_count": 0,
        "nonfinite_violation_count": 0, "online_estimator_received_gt": False,
        "window_statistics_read_gt": False, "historical_artifacts_unchanged": True,
        "strategy_chain_mismatch_count": 0, "contaminated_non_axial_support_count": 0,
        "axial_only_audit_pass": True, "points_lidar_method_pair_mismatch_count": 0,
        "normals_world_method_pair_mismatch_count": 0, "R_diag_method_pair_mismatch_count": 0,
        "points_lidar_clean_stress_mismatch_count": 0,
        "normals_world_clean_stress_mismatch_count": 0,
        "R_diag_clean_stress_mismatch_count": 0, "v1_v2_failure_count": 0,
        "v1_v2_key_mismatch_count": 0,
    }
    for field, expected in expected_values.items():
        record(f"manifest_{field}", manifest.get(field) == expected, manifest.get(field))
    maximum = float(manifest.get("v1_v2_max_numeric_difference", float("inf")))
    record("v1_v2_numeric_tolerance", math.isfinite(maximum) and maximum <= 1.0e-12, maximum)

    frozen_path = Path(frozen_tree_manifest_path or Path.home() / "day11b_v2_result_sha256_before_day12.txt")
    frozen_ok = frozen_path.is_file() and frozen_path.read_bytes() == result_tree_manifest(root, run_dir)
    record("frozen_v2_tree", frozen_ok, frozen_path)
    hashes = {field: _sha256(run_dir / filename) for field, filename in HASH_FILES.items()}

    plan_fields, plan = _read_csv(run_dir / "replay_plan.csv")
    expected_matrix = [
        (sweep, stress, method)
        for sweep in EXPECTED_SWEEPS for stress in EXPECTED_STRESSES for method in EXPECTED_METHODS
    ]
    actual_matrix = [(row["sweep"], row["stress"], row["method"]) for row in plan]
    plan_ok = len(plan) == 8 and actual_matrix == expected_matrix and len({row["case_id"] for row in plan}) == 8
    plan_ok = plan_ok and not any(
        "oracle" in row["method"].lower() or row["stress"] in {"axial_correspondence_slip", "gross_outlier_control"}
        for row in plan
    )
    record("replay_plan_matrix", plan_ok, len(plan))
    plan_by_case = {row["case_id"]: row for row in plan}

    case_dirs = sorted(path for path in (run_dir / "cases").iterdir() if path.is_dir()) if (run_dir / "cases").is_dir() else []
    case_ids = [path.name for path in case_dirs]
    record("case_directory_set", set(case_ids) == set(plan_by_case), len(case_ids))
    strategy_mismatches = 0
    case_identity_mismatches = 0
    expected_rows = 0
    case_manifests: Dict[str, Mapping[str, Any]] = {}
    for case_dir in case_dirs:
        case_id = case_dir.name
        missing_case = [name for name in REQUIRED_CASE_FILES if not (case_dir / name).is_file()]
        if missing_case or case_id not in plan_by_case:
            strategy_mismatches += 1
            record(f"case_files_{case_id}", False, missing_case)
            continue
        case_manifest = _read_json(case_dir / "case_manifest.json")
        metrics = _read_json(case_dir / "trajectory_metrics.json")
        chain = _read_json(case_dir / "strategy_chain_audit.json")
        _, online = _read_csv(case_dir / "frame_diagnostics_online.csv")
        plan_row = plan_by_case[case_id]
        identity_ok = all(
            str(case_manifest.get(field)) == str(plan_row.get(field))
            for field in (
                "case_id", "sweep", "level", "stress", "geometry_seed",
                "sensor_seed", "process_seed", "method",
            )
        )
        case_identity_mismatches += int(not identity_ok)
        record(f"case_identity_{case_id}", identity_ok)
        online_methods = {row["applied_strategy"] for row in online}
        values = [
            plan_row["method"], case_manifest.get("method"), metrics.get("strategy"),
            metrics.get("strategy_logging_disabled"), metrics.get("strategy_logging_enabled"),
            next(iter(online_methods)) if len(online_methods) == 1 else "",
            chain.get("plan_method"), chain.get("case_manifest_method"),
            chain.get("trajectory_metrics_strategy"), chain.get("logging_disabled_strategy"),
            chain.get("logging_enabled_strategy"), chain.get("online_applied_strategy_unique"),
        ]
        strategy_ok = len(set(values)) == 1 and values[0] in EXPECTED_METHODS and chain.get("pass") is True
        strategy_mismatches += int(not strategy_ok)
        record(f"strategy_chain_{case_id}", strategy_ok, values)
        runtime_ok = (
            int(case_manifest.get("solver_failure_count", -1)) == 0
            and case_manifest.get("online_estimator_received_gt") is False
            and int(case_manifest.get("gt_field_access_attempt_count", -1)) == 0
            and len(online) == int(case_manifest.get("frame_count", -1))
        )
        record(f"case_runtime_{case_id}", runtime_ok)
        base_ok = all(field in case_manifest and field in metrics and case_manifest[field] == metrics[field] for field in BASE_FIELDS)
        record(f"base_checksums_{case_id}", base_ok)
        expected_rows += int(case_manifest.get("frame_count", -1))
        case_manifests[case_id] = case_manifest

    base_fields, base_rows = _read_csv(run_dir / "base_observation_pairing_audit.csv")
    base_failures = _recompute_base_pairing(case_manifests)
    base_csv_ok = bool(base_rows) and all(_bool(row.get("pass")) for row in base_rows)
    record("base_pairing_audit_rows", base_csv_ok, len(base_rows))
    for name, count in base_failures.items():
        record(f"base_pairing_{name}", count == 0, count)

    merged_fields, merged = _read_csv(run_dir / "replay_frame_diagnostics_merged.csv")
    summary_fields, summary_rows = _read_csv(run_dir / "replay_case_summary.csv")
    keys = [tuple(row[field] for field in PRIMARY_KEY) for row in merged]
    duplicate_count = len(keys) - len(set(keys))
    merged_case_ids = {row["case_id"] for row in merged}
    missing_key_count = 0
    for case_id, case_manifest in case_manifests.items():
        rows = [row for row in merged if row["case_id"] == case_id]
        if len(rows) != int(case_manifest["frame_count"]):
            missing_key_count += abs(len(rows) - int(case_manifest["frame_count"])) or 1
        frames = [int(row["frame_index"]) for row in rows]
        times = [float(row["timestamp"]) for row in rows]
        if frames != sorted(frames) or len(set(frames)) != len(frames):
            missing_key_count += 1
        if any(second <= first for first, second in zip(times, times[1:])):
            missing_key_count += 1
        plan_row = plan_by_case.get(case_id, {})
        for row in rows:
            if any(str(row[field]) != str(plan_row.get(field)) for field in (
                "sweep", "level", "stress", "geometry_seed", "sensor_seed", "process_seed", "method"
            )):
                missing_key_count += 1
    record("merged_row_count", len(merged) == expected_rows, f"{len(merged)}/{expected_rows}")
    record("summary_case_count", len(summary_rows) == 8 and {row["case_id"] for row in summary_rows} == set(plan_by_case))
    record("merged_case_set", merged_case_ids == set(plan_by_case))
    record("duplicate_primary_key", duplicate_count == 0, duplicate_count)
    record("missing_primary_key", missing_key_count == 0, missing_key_count)

    nonfinite_violations = _numeric_semantic_violations(merged)
    record("numeric_nan_semantics", nonfinite_violations == 0, nonfinite_violations)
    stress = _stress_audit(merged)
    for name, passed in stress["checks"].items():
        record(f"stress_{name}", passed, stress.get(name, ""))

    strategy_csv_fields, strategy_csv = _read_csv(run_dir / "strategy_chain_audit.csv")
    record("strategy_chain_csv", len(strategy_csv) == 8 and all(_bool(row["pass"]) for row in strategy_csv))
    axial = _read_json(run_dir / "axial_support_summary.json")
    record("axial_support_summary", axial.get("axial_only_audit_pass") is True and int(axial.get("contaminated_non_axial_support_count", -1)) == 0)
    equivalence_fields, equivalence = _read_csv(run_dir / "v1_v2_scientific_equivalence_audit.csv")
    record("v1_v2_equivalence_rows", bool(equivalence) and all(_bool(row["pass"]) for row in equivalence))

    audit_pass = all(bool(row["pass"]) for row in checks)
    return {
        "schema_version": INPUT_AUDIT_SCHEMA_VERSION,
        "DAY12_INPUT_AUDIT_PASS": audit_pass,
        "checks": checks,
        "missing_files": [],
        **hashes,
        "actual_case_count": len(case_ids), "expected_case_count": 8,
        "actual_merged_row_count": len(merged), "expected_merged_row_count": expected_rows,
        "case_ids": case_ids, "method_list": list(EXPECTED_METHODS),
        "stress_list": list(EXPECTED_STRESSES), "sweep_list": list(EXPECTED_SWEEPS),
        "strategy_chain_comparison_count": len(case_ids),
        "strategy_chain_mismatch_count": strategy_mismatches,
        "case_identity_mismatch_count": case_identity_mismatches,
        "duplicate_key_count": duplicate_count, "missing_key_count": missing_key_count,
        "nonfinite_violation_count": nonfinite_violations,
        "points_lidar_mismatch_count": base_failures["points_lidar"],
        "normals_world_mismatch_count": base_failures["normals_world"],
        "R_diag_mismatch_count": base_failures["R_diag"],
        **{key: value for key, value in stress.items() if key != "checks"},
    }


def _stress_audit(rows: Sequence[Mapping[str, str]]) -> Mapping[str, Any]:
    coherent = [row for row in rows if row["stress"] == "coherent_subhuber_slip"]
    clean = [row for row in rows if row["stress"] == "clean"]
    method_contamination = sum(int(row["contaminated_measurement_count"]) for row in coherent)
    method_active = sum(int(_bool(row["stress_active"])) for row in coherent)
    unique: Dict[tuple, Mapping[str, str]] = {}
    duplicate_consistent = True
    for row in coherent:
        key = tuple(row[field] for field in EXTERNAL_KEY)
        if key in unique:
            for field in (
                "contaminated_measurement_count", "stress_active",
                "contamination_offset_signed_mean_m", "contaminated_axial_support_count",
                "contaminated_non_axial_support_count",
            ):
                duplicate_consistent &= row[field] == unique[key][field]
        else:
            unique[key] = row
    unique_rows = list(unique.values())
    external_contamination = sum(int(row["contaminated_measurement_count"]) for row in unique_rows)
    external_active = sum(int(_bool(row["stress_active"])) for row in unique_rows)
    burst_lengths = []
    shared_sign = True
    offset_values = set()
    for sweep in EXPECTED_SWEEPS:
        active = sorted(
            (row for row in unique_rows if row["sweep"] == sweep and _bool(row["stress_active"])),
            key=lambda row: int(row["frame_index"]),
        )
        frames = [int(row["frame_index"]) for row in active]
        runs = []
        for frame in frames:
            if not runs or frame != runs[-1][-1] + 1:
                runs.append([frame])
            else:
                runs[-1].append(frame)
        burst_lengths.extend(len(run) for run in runs)
        shared_sign &= len(runs) == 1
        for run in runs:
            run_rows = [row for row in active if int(row["frame_index"]) in set(run)]
            signs = {
                1 if float(row["contamination_offset_signed_mean_m"]) > 0 else -1
                for row in run_rows
            }
            shared_sign &= len(signs) == 1
        offset_values.update(round(abs(float(row["contamination_offset_abs_mean_m"])), 12) for row in active)
    clean_external: Dict[tuple, Mapping[str, str]] = {}
    for row in clean:
        clean_external.setdefault(tuple(row[field] for field in EXTERNAL_KEY), row)
    clean_count = sum(int(row["contaminated_measurement_count"]) for row in clean_external.values())
    clean_active = sum(int(_bool(row["stress_active"])) for row in clean_external.values())
    non_axial = sum(int(row["contaminated_non_axial_support_count"]) for row in unique_rows)
    axial = sum(int(row["contaminated_axial_support_count"]) for row in unique_rows)
    offset = next(iter(offset_values)) if len(offset_values) == 1 else float("nan")
    checks = {
        "duplicate_method_rows_consistent": duplicate_consistent,
        "clean_zero": clean_count == 0 and clean_active == 0,
        "method_contamination": method_contamination == 872,
        "external_contamination": external_contamination == 436,
        "method_active": method_active == 80,
        "external_active": external_active == 40,
        "burst_lengths": burst_lengths == [20, 20],
        "offset": math.isfinite(offset) and abs(offset - 0.03) <= 1.0e-12,
        "shared_sign": shared_sign,
        "axial_only": non_axial == 0 and axial == external_contamination,
    }
    return {
        "checks": checks,
        "clean_external_contaminated_measurement_count": clean_count,
        "method_expanded_contaminated_measurement_count": method_contamination,
        "external_unique_contaminated_measurement_count": external_contamination,
        "method_expanded_stress_active_frame_count": method_active,
        "external_unique_stress_active_frame_count": external_active,
        "coherent_burst_count": len(burst_lengths), "coherent_burst_lengths": burst_lengths,
        "coherent_offset_abs_m": offset, "coherent_shared_sign_pass": shared_sign,
        "contaminated_non_axial_support_count": non_axial,
        "axial_only_audit_pass": checks["axial_only"],
    }


def _numeric_semantic_violations(rows: Sequence[Mapping[str, str]]) -> int:
    violations = 0
    numeric_skip = {
        "schema_version", "case_id", "run_id", "sequence_id", "sweep", "level",
        "stress", "method", "applied_strategy", "stat_reset_reason",
        "axial_support_mask_checksum", "contamination_mask_checksum",
    }
    for row in rows:
        for field, text in row.items():
            if field in numeric_skip or text in {"True", "False"}:
                continue
            try:
                value = float(text)
            except ValueError:
                continue
            if math.isinf(value):
                violations += 1
        if _bool(row["weak_innovation_valid"]):
            violations += int(not all(math.isfinite(float(row[field])) for field in (
                "weak_innovation_z_raw", "weak_innovation_z_huber"
            )))
        try:
            window_record = {
                name: (
                    WINDOW_SCHEMA_VERSION if name == "schema_version" else
                    ONLINE_SCHEMA_VERSION if name == "source_online_schema_version" else
                    _bool(row[name]) if name in {
                        "weak_direction_valid", "weak_innovation_valid",
                        "primary_direction_stable", "degeneracy_triggered",
                        "actionable_direction", "stat_input_valid", "window_ready",
                    } else row[name]
                )
                for name in WINDOW_FIELDS
            }
            validate_window_record(window_record)
        except (KeyError, TypeError, ValueError):
            violations += 1
        offline = _bool(row["offline_evaluation_only"])
        gt_values = [float(row[field]) for field in (
            "prior_axis_error_signed_m", "prior_axis_error_abs_m",
            "posterior_axis_error_signed_m", "posterior_axis_error_abs_m",
            "axis_abs_error_change_m", "axis_abs_error_reduction_m",
        )]
        if offline:
            violations += int(not all(math.isfinite(value) for value in gt_values))
        else:
            violations += int(not all(math.isnan(value) for value in gt_values))
        if row["stress"] == "clean" and int(row["contaminated_measurement_count"]) == 0:
            clean_nan_fields = (
                "contamination_offset_signed_mean_m", "contamination_offset_abs_mean_m",
                "contamination_offset_abs_max_m", "contaminated_normalized_residual_mean",
                "contaminated_normalized_residual_median",
                "contaminated_normalized_residual_abs_median",
                "contaminated_normalized_residual_abs_max",
                "contaminated_dominant_sign_ratio",
                "contaminated_huber_downweighted_ratio", "contaminated_subhuber_ratio",
            )
            violations += int(not all(math.isnan(float(row[field])) for field in clean_nan_fields))
        contaminated = int(row["contaminated_measurement_count"])
        violations += int(_bool(row["stress_active"]) != (contaminated > 0))
        violations += int(
            contaminated
            != int(row["contaminated_axial_support_count"])
            + int(row["contaminated_non_axial_support_count"])
        )
    return violations


def _recompute_base_pairing(
    case_manifests: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, int]:
    fields = {
        "points_lidar": "points_lidar_base_checksum",
        "normals_world": "normals_world_base_checksum",
        "R_diag": "R_diag_list_checksum",
    }
    failures = {name: 0 for name in fields}
    cases = list(case_manifests.values())
    groupings = (
        ("sweep", "level", "stress", "geometry_seed", "sensor_seed", "process_seed"),
        ("sweep", "level", "geometry_seed", "sensor_seed", "process_seed", "method"),
    )
    for group_fields in groupings:
        groups: Dict[tuple, list] = {}
        for case in cases:
            key = tuple(case.get(field) for field in group_fields)
            groups.setdefault(key, []).append(case)
        for members in groups.values():
            if len(members) != 2:
                for name in failures:
                    failures[name] += 1
                continue
            for name, field in fields.items():
                if len({member.get(field) for member in members}) != 1 or None in {
                    member.get(field) for member in members
                }:
                    failures[name] += 1
    return failures


def _failed_result(run_dir: Path, checks: Sequence[Mapping[str, Any]], missing: Sequence[str]) -> Mapping[str, Any]:
    return {
        "schema_version": INPUT_AUDIT_SCHEMA_VERSION, "DAY12_INPUT_AUDIT_PASS": False,
        "checks": list(checks), "missing_files": list(missing),
        "actual_case_count": 0, "expected_case_count": 8,
        "actual_merged_row_count": 0, "expected_merged_row_count": 0,
        "strategy_chain_comparison_count": 0, "strategy_chain_mismatch_count": 1,
        "duplicate_key_count": 0, "missing_key_count": 1, "nonfinite_violation_count": 0,
    }


def _read_csv(path: Path) -> Tuple[Sequence[str], Sequence[Mapping[str, str]]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return tuple(reader.fieldnames or ()), list(reader)


def _read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON mapping: {path}")
    return value


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if str(value) not in {"True", "False"}:
        raise ValueError(f"not a canonical boolean: {value}")
    return str(value) == "True"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
