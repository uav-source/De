"""Schemas, joins, equivalence checks, and gate logic for Stage 2 Day 11B."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence, Tuple

import numpy as np

from eval.stage2_failure_day11b_stress_trace import STRESS_TRACE_FIELDS
from eval.stage2_failure_no_gt_audit import (
    FRAME_DIAGNOSTIC_FIELDS,
    ONLINE_CONTINUOUS_RESULT_FIELDS,
    array_sha256,
    compare_array_field,
    compare_record_sequences,
)
from eval.stage2_failure_schema import (
    FRAME_KEY_FIELDS,
    GT_FIELDS,
    ONLINE_FIELDS,
    frame_key,
    validate_gt_frame_record,
    validate_online_frame_record,
)
from eval.stage2_failure_window_schema import WINDOW_FIELDS, validate_window_record


DAY11B_RUN_SCHEMA_VERSION = "stage2_failure_day11b_run_v1"
LOGGING_AUDIT_FIELDS = (
    "case_id", "field", "field_type", "shape_disabled", "shape_enabled",
    "dtype_disabled", "dtype_enabled", "max_abs_difference", "exact_array_equal",
    "disabled_sha256", "enabled_sha256", "finite_disabled", "finite_enabled", "pass",
)
PAIRING_AUDIT_FIELDS = (
    "group_type", "sweep", "level", "stress", "geometry_seed", "sensor_seed",
    "process_seed", "method_count", "scene_checksum_match", "base_observation_checksum_match",
    "stressed_observation_checksum_match", "stress_checksum_match",
    "process_noise_checksum_match", "initial_state_checksum_match",
    "initial_covariance_checksum_match", "pairing_valid",
)
STRESS_MECHANISM_AUDIT_FIELDS = (
    "sweep", "level", "stress", "geometry_seed", "sensor_seed", "process_seed",
    "scene_checksum", "base_observation_checksum", "stressed_observation_checksum",
    "stress_checksum", "process_noise_checksum", "initial_state_checksum",
    "initial_covariance_checksum", "contaminated_measurement_count", "stress_active_frame_count",
    "selected_patch_count", "external_stress_valid",
)
CASE_SUMMARY_FIELDS = (
    "case_id", "sweep", "level", "stress", "geometry_seed", "sensor_seed",
    "process_seed", "method", "frame_count", "valid_innovation_frame_count",
    "window_ready_frame_count", "stress_active_frame_count", "axis_rmse", "axis_mae",
    "strong_translation_rmse", "orientation_rmse_rad", "trajectory_rmse_3d",
    "final_axis_error_abs", "median_abs_weak_innovation_z_huber",
    "median_huber_window_mean", "max_abs_huber_cusum_signed",
    "max_huber_same_sign_run_length", "median_full_update_weak_abs_m",
    "median_applied_update_weak_abs_m", "median_axis_abs_error_reduction_m",
    "fraction_axis_error_reduced", "median_huber_outlier_ratio",
    "median_contaminated_subhuber_ratio",
    "median_contaminated_huber_downweighted_ratio",
)


def _ordered_union(*groups: Sequence[str]) -> Tuple[str, ...]:
    values = []
    for group in groups:
        for field in group:
            if field not in values:
                values.append(field)
    return tuple(values)


_ONLINE_PAYLOAD = tuple(field for field in ONLINE_FIELDS if field != "schema_version")
_GT_PAYLOAD = tuple(field for field in GT_FIELDS if field not in {"schema_version", *FRAME_KEY_FIELDS})
_WINDOW_PAYLOAD = tuple(
    field
    for field in WINDOW_FIELDS
    if field not in {"schema_version", "source_online_schema_version", *FRAME_KEY_FIELDS}
)
_STRESS_PAYLOAD = tuple(
    field for field in STRESS_TRACE_FIELDS if field not in {"schema_version", *FRAME_KEY_FIELDS}
)
MERGED_FIELDS = _ordered_union(
    ("schema_version", "case_id"),
    _ONLINE_PAYLOAD,
    _GT_PAYLOAD,
    _WINDOW_PAYLOAD,
    _STRESS_PAYLOAD,
)


def compare_logging_runs(
    case_id: str,
    disabled: Mapping[str, Any],
    enabled: Mapping[str, Any],
    logger_records: Sequence[Mapping[str, Any]],
    tolerance: float = 1.0e-12,
) -> Mapping[str, Any]:
    """Compare every estimator output that is invariant to logger attachment."""

    rows = []
    maxima = {field: 0.0 for field in ONLINE_CONTINUOUS_RESULT_FIELDS}
    checksum_mismatches = 0
    for field in ONLINE_CONTINUOUS_RESULT_FIELDS:
        audit = compare_array_field(
            "logging_enabled", str(case_id), field, "continuous",
            np.asarray(disabled[field]), np.asarray(enabled[field]), tolerance, True,
        )
        maxima[field] = float(audit["max_abs_difference"])
        checksum_mismatches += int(audit["control_sha256"] != audit["variant_sha256"])
        rows.append(_logging_row(case_id, audit))
    discrete = {
        "detector_triggered": (disabled["detector_triggered"], enabled["detector_triggered"]),
        "actionable_direction": (disabled["actionable_direction"], enabled["actionable_direction"]),
        "primary_direction_stable": (
            _diagnostic_boolean_array(disabled, "primary_direction_stable"),
            _diagnostic_boolean_array(enabled, "primary_direction_stable"),
        ),
        "solver_failure": (
            _solver_failure_array(disabled),
            _solver_failure_array(enabled),
        ),
    }
    for field, (first, second) in discrete.items():
        audit = compare_array_field(
            "logging_enabled", str(case_id), field, "discrete",
            np.asarray(first), np.asarray(second), tolerance, True,
        )
        checksum_mismatches += int(audit["control_sha256"] != audit["variant_sha256"])
        rows.append(_logging_row(case_id, audit))
    diagnostics = compare_record_sequences(
        disabled["frame_diagnostics"], enabled["frame_diagnostics"],
        FRAME_DIAGNOSTIC_FIELDS, True,
    )
    rows.append(_record_logging_row(case_id, "frame_diagnostics", diagnostics))
    checksum_mismatches += int(diagnostics["control_sha256"] != diagnostics["variant_sha256"])
    logger_integrity = compare_record_sequences(
        enabled["failure_frame_records"], logger_records, ONLINE_FIELDS, True
    )
    rows.append(_record_logging_row(case_id, "failure_frame_records_vs_logger", logger_integrity))
    checksum_mismatches += int(
        logger_integrity["control_sha256"] != logger_integrity["variant_sha256"]
    )
    for field in ("solver_failure_count", "strategy"):
        first = disabled[field]
        second = enabled[field]
        expected = 0 if field == "solver_failure_count" else str(enabled["strategy"])
        passed = first == second == expected
        first_hash = _scalar_sha(first)
        second_hash = _scalar_sha(second)
        checksum_mismatches += int(first_hash != second_hash)
        rows.append({
            "case_id": str(case_id), "field": field, "field_type": "scalar",
            "shape_disabled": "scalar", "shape_enabled": "scalar",
            "dtype_disabled": type(first).__name__, "dtype_enabled": type(second).__name__,
            "max_abs_difference": 0.0 if passed else float("inf"),
            "exact_array_equal": bool(first == second), "disabled_sha256": first_hash,
            "enabled_sha256": second_hash, "finite_disabled": True,
            "finite_enabled": True, "pass": bool(passed),
        })
    return {
        "rows": rows,
        "pass": all(bool(row["pass"]) for row in rows),
        "failure_count": sum(int(not bool(row["pass"])) for row in rows),
        "checksum_mismatch_count": checksum_mismatches,
        "max_trajectory_difference": maxima["poses"],
        "max_covariance_difference": maxima["covariances"],
        "max_applied_delta_difference": maxima["applied_deltas"],
        "max_full_delta_difference": maxima["full_deltas"],
    }


def merge_frame_records(
    case_id: str,
    online_rows: Sequence[Mapping[str, Any]],
    gt_rows: Sequence[Mapping[str, Any]],
    window_rows: Sequence[Mapping[str, Any]],
    stress_rows: Sequence[Mapping[str, Any]],
) -> Sequence[Mapping[str, Any]]:
    """Perform a strict one-to-one four-table join on the frozen frame key."""

    for row in online_rows:
        validate_online_frame_record(row)
    for row in gt_rows:
        validate_gt_frame_record(row)
    for row in window_rows:
        validate_window_record(row)
    sources = [online_rows, gt_rows, window_rows, stress_rows]
    indices = []
    for rows in sources:
        index: Dict[tuple, Mapping[str, Any]] = {}
        for row in rows:
            key = frame_key(row)
            if key in index:
                raise ValueError("duplicate Day 11B frame key")
            index[key] = row
        indices.append(index)
    keys = [list(index) for index in indices]
    if not keys[0] or any(set(value) != set(keys[0]) for value in keys[1:]):
        raise ValueError("Day 11B frame tables have missing or extra keys")
    output = []
    for key in keys[0]:
        online, gt, window, stress = (index[key] for index in indices)
        merged: Dict[str, Any] = {
            "schema_version": DAY11B_RUN_SCHEMA_VERSION,
            "case_id": str(case_id),
        }
        _merge_payload(merged, online, {"schema_version"})
        _merge_payload(merged, gt, {"schema_version", *FRAME_KEY_FIELDS})
        _merge_payload(
            merged, window, {"schema_version", "source_online_schema_version", *FRAME_KEY_FIELDS}
        )
        _merge_payload(merged, stress, {"schema_version", *FRAME_KEY_FIELDS})
        if set(merged) != set(MERGED_FIELDS):
            raise ValueError("Day 11B merged frame schema changed")
        if any(math.isinf(float(value)) for value in merged.values() if _numeric(value)):
            raise ValueError("Day 11B merged frame contains infinity")
        output.append(merged)
    return output


def build_pairing_audit(case_manifests: Sequence[Mapping[str, Any]]) -> Sequence[Mapping[str, Any]]:
    rows = []
    grouped: Dict[tuple, list] = {}
    for item in case_manifests:
        key = tuple(item[field] for field in (
            "sweep", "level", "stress", "geometry_seed", "sensor_seed", "process_seed"
        ))
        grouped.setdefault(key, []).append(item)
    checksum_fields = (
        "scene_checksum", "base_observation_checksum", "stressed_observation_checksum",
        "stress_checksum", "process_noise_checksum", "initial_state_checksum",
        "initial_covariance_checksum",
    )
    for key, values in sorted(grouped.items()):
        checks = {field: len({str(row[field]) for row in values}) == 1 for field in checksum_fields}
        rows.append({
            "group_type": "method_pair", **dict(zip(
                ("sweep", "level", "stress", "geometry_seed", "sensor_seed", "process_seed"), key
            )), "method_count": len(values),
            **{f"{field}_match": checks[field] for field in checksum_fields},
            "pairing_valid": bool(len(values) == 2 and all(checks.values())),
        })
    by_sweep: Dict[tuple, list] = {}
    for item in case_manifests:
        if item["method"] != "huber_full":
            continue
        key = tuple(item[field] for field in (
            "sweep", "level", "geometry_seed", "sensor_seed", "process_seed"
        ))
        by_sweep.setdefault(key, []).append(item)
    for key, values in sorted(by_sweep.items()):
        invariant = (
            "scene_checksum", "base_observation_checksum", "process_noise_checksum",
            "initial_state_checksum", "initial_covariance_checksum",
        )
        checks = {field: len({str(row[field]) for row in values}) == 1 for field in invariant}
        values_by_stress = {str(row["stress"]): row for row in values}
        valid = bool(
            set(values_by_stress) == {"clean", "coherent_subhuber_slip"}
            and all(checks.values())
            and int(values_by_stress["clean"]["contaminated_measurement_count"]) == 0
            and int(values_by_stress["coherent_subhuber_slip"]["contaminated_measurement_count"]) > 0
            and int(values_by_stress["coherent_subhuber_slip"]["stress_active_frame_count"]) > 0
        )
        row = {
            "group_type": "stress_pair",
            "sweep": key[0], "level": key[1], "stress": "clean|coherent_subhuber_slip",
            "geometry_seed": key[2], "sensor_seed": key[3], "process_seed": key[4],
            "method_count": 2,
            "scene_checksum_match": checks["scene_checksum"],
            "base_observation_checksum_match": checks["base_observation_checksum"],
            "stressed_observation_checksum_match": len({
                str(item["stressed_observation_checksum"]) for item in values
            }) == 1,
            "stress_checksum_match": len({str(item["stress_checksum"]) for item in values}) == 1,
            "process_noise_checksum_match": checks["process_noise_checksum"],
            "initial_state_checksum_match": checks["initial_state_checksum"],
            "initial_covariance_checksum_match": checks["initial_covariance_checksum"],
            "pairing_valid": valid,
        }
        rows.append(row)
    return rows


def evaluate_day11b_gate(values: Mapping[str, Any]) -> bool:
    required_true = (
        "git_status_clean_at_start", "head_descends_from_day11a_checkpoint",
        "case_lock_verification_pass", "case_selection_reproducibility_pass",
        "historical_artifacts_unchanged", "replay_for_diagnosis_only",
    )
    required_false = (
        "online_estimator_received_gt", "window_statistics_read_gt",
        "gross_outlier_control_replayed", "stress_name_alias_used",
        "legacy_stage2b_stress_name_used", "historical_trial_tables_available",
        "historical_metric_equivalence_performed", "new_seed_used",
        "full_reserved_test_suite_rerun", "new_reserved_test_namespace_consumed",
        "replay_is_independent_test", "replay_is_representative",
        "replay_used_for_threshold_selection", "replay_used_for_stage2_gate",
        "figures_generated", "threshold_created", "auroc_computed", "fpr_computed",
        "f1_computed", "detection_delay_computed", "fast_lio2_integrated",
    )
    zero_fields = (
        "case_lock_field_mismatch_count", "case_lock_hash_mismatch_count",
        "gt_field_access_attempt_count", "logging_equivalence_failure_count",
        "logging_checksum_mismatch_count", "pairing_violation_count",
        "duplicate_frame_key_count", "missing_frame_key_count",
        "nonfinite_violation_count", "solver_failure_count",
        "clean_contaminated_measurement_count", "incomplete_sequence_count",
        "stress_mechanism_failure_count",
    )
    if not all(values.get(field) is True for field in required_true):
        return False
    if not all(values.get(field) is False for field in required_false):
        return False
    if not all(int(values.get(field, -1)) == 0 for field in zero_fields):
        return False
    if list(values.get("method_list", [])) != ["huber_full", "huber_projected_gain"]:
        return False
    if list(values.get("replay_stress_list", [])) != ["clean", "coherent_subhuber_slip"]:
        return False
    if int(values.get("expected_replay_count", -1)) != 8:
        return False
    if int(values.get("completed_replay_count", -1)) != 8:
        return False
    if int(values.get("logging_equivalence_comparison_count", -1)) != 8:
        return False
    if int(values.get("case_summary_row_count", -1)) != 8:
        return False
    if int(values.get("pairing_group_count", 0)) <= 0:
        return False
    if int(values.get("coherent_contaminated_measurement_count", 0)) <= 0:
        return False
    if int(values.get("coherent_stress_active_frame_count", 0)) <= 0:
        return False
    counts = [int(values.get(field, -1)) for field in (
        "online_row_count", "gt_row_count", "window_row_count",
        "stress_trace_row_count", "merged_row_count",
    )]
    if counts[0] <= 0 or len(set(counts)) != 1:
        return False
    fixed_status = {
        "STAGE2_GATE": "INCOMPLETE",
        "STAGE3_GATE": "NOT_STARTED",
        "COHERENT_BIAS_DETECTABLE": "UNDETERMINED",
        "RISK_WARNING_AUTHORIZED": False,
        "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
        "PUBLIC_DISCLOSURE_AUTHORIZED": False,
    }
    if any(values.get(field) != expected for field, expected in fixed_status.items()):
        return False
    for field in (
        "logging_max_trajectory_difference", "logging_max_covariance_difference",
        "logging_max_applied_delta_difference", "logging_max_full_delta_difference",
    ):
        value = float(values.get(field, float("inf")))
        if not math.isfinite(value) or value > 1.0e-12:
            return False
    return True


def write_fixed_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _logging_row(case_id: str, row: Mapping[str, Any]) -> Mapping[str, Any]:
    return {
        "case_id": str(case_id), "field": row["field"], "field_type": row["field_type"],
        "shape_disabled": row["shape_control"], "shape_enabled": row["shape_variant"],
        "dtype_disabled": row["dtype_control"], "dtype_enabled": row["dtype_variant"],
        "max_abs_difference": row["max_abs_difference"],
        "exact_array_equal": row["exact_array_equal"],
        "disabled_sha256": row["control_sha256"], "enabled_sha256": row["variant_sha256"],
        "finite_disabled": row["finite_control"], "finite_enabled": row["finite_variant"],
        "pass": row["pass"],
    }


def _record_logging_row(case_id: str, field: str, result: Mapping[str, Any]) -> Mapping[str, Any]:
    passed = bool(result["pass"])
    return {
        "case_id": str(case_id), "field": field, "field_type": "record_sequence",
        "shape_disabled": str(result["control_row_count"]),
        "shape_enabled": str(result["variant_row_count"]),
        "dtype_disabled": "record", "dtype_enabled": "record",
        "max_abs_difference": 0.0 if passed else float("inf"),
        "exact_array_equal": result["records_equal"],
        "disabled_sha256": result["control_sha256"],
        "enabled_sha256": result["variant_sha256"],
        "finite_disabled": True, "finite_enabled": True, "pass": passed,
    }


def _diagnostic_boolean_array(result: Mapping[str, Any], field: str) -> np.ndarray:
    output = np.zeros(np.asarray(result["poses"]).shape[0], dtype=bool)
    for row in result["frame_diagnostics"]:
        output[int(row["frame_index"])] = bool(row[field])
    return output


def _solver_failure_array(result: Mapping[str, Any]) -> np.ndarray:
    if int(result["solver_failure_count"]) != 0:
        return np.ones(np.asarray(result["poses"]).shape[0], dtype=bool)
    return np.zeros(np.asarray(result["poses"]).shape[0], dtype=bool)


def _scalar_sha(value: Any) -> str:
    import hashlib
    payload = f"{type(value).__name__}:{value!r}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _merge_payload(target: Dict[str, Any], source: Mapping[str, Any], excluded: set) -> None:
    for field, value in source.items():
        if field in excluded:
            continue
        if field in target and not _equal(target[field], value):
            raise ValueError(f"Day 11B join field differs across sources: {field}")
        target.setdefault(field, value)


def _equal(first: Any, second: Any) -> bool:
    try:
        left = float(first)
        right = float(second)
    except (TypeError, ValueError):
        return first == second
    if math.isnan(left) and math.isnan(right):
        return True
    return left == right


def _numeric(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return False
    try:
        float(value)
    except (TypeError, ValueError):
        return False
    return True
