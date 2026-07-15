"""Quick-only Day 9 pipeline for causal weak-innovation window statistics."""

from __future__ import annotations

import csv
import json
import math
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import numpy as np
import scipy

from eval.analysis_lock import (
    compute_directory_hash,
    compute_source_tree_hash,
    git_commit,
    git_status_clean,
    sha256_file,
)
from eval.stage2_failure_schema import (
    FRAME_KEY_FIELDS,
    ONLINE_FIELDS,
    ONLINE_SCHEMA_VERSION,
)
from eval.stage2_failure_window_schema import (
    SIGNAL_FLOAT_SUFFIXES,
    SIGNAL_INTEGER_SUFFIXES,
    WINDOW_SCHEMA_VERSION,
    validate_window_record,
    window_frame_key,
    write_window_csv,
)
from eval.stage2_failure_window_stats import (
    CausalInnovationWindow,
    SignalWindowStatistics,
    WindowStatisticConfig,
)
from eval.synthetic_pipeline_common import load_yaml, write_json


DAY9_GROUP_FIELDS = FRAME_KEY_FIELDS[:-2]
HISTORICAL_ARTIFACT_PATHS = (
    "artifacts/current/detector_stage2a",
    "artifacts/history/stage2b_column_scaling_no_go",
    "artifacts/current/weak_update_stage2c",
)


def run_stage2_failure_day9(
    root: Path,
    online_log_path: Path,
    source_manifest_path: Path,
    run_id: str,
    output_root: Path,
    overwrite: bool = False,
    config_path: Path = None,
) -> Mapping[str, Any]:
    """Compute Day 9 statistics from one Day 8 online CSV and its manifest."""

    root = Path(root).resolve()
    online_log_path = Path(online_log_path).resolve()
    source_manifest_path = Path(source_manifest_path).resolve()
    config_path = (
        root / "configs/stage2_failure/day9_quick.yaml"
        if config_path is None
        else Path(config_path).resolve()
    )
    config_mapping = load_yaml(config_path)
    _validate_day9_quick_config(config_mapping)
    statistic_config = window_config_from_mapping(config_mapping)
    clean_at_start = git_status_clean(root)
    source_manifest = validate_source_manifest(
        source_manifest_path,
        online_log_path,
    )
    input_rows = read_online_csv(online_log_path)
    if int(source_manifest.get("online_log_row_count", -1)) != len(input_rows):
        raise ValueError("source manifest online row count does not match the CSV")

    result_dir = Path(output_root).resolve() / str(run_id)
    if result_dir.exists():
        if not overwrite:
            raise FileExistsError(f"Day 9 output already exists: {result_dir}; use --overwrite")
        shutil.rmtree(result_dir)
    result_dir.mkdir(parents=True)

    historical_before = _historical_hashes(root)
    output_rows = compute_window_records(input_rows, statistic_config)
    input_keys = [_normalized_frame_key(row) for row in input_rows]
    output_keys = [window_frame_key(row) for row in output_rows]
    duplicate_key_count = len(input_keys) - len(set(input_keys))
    ordering_violation_count = 0
    frame_key_one_to_one = input_keys == output_keys
    group_count = len({_normalized_group_key(row) for row in input_rows})
    causal_prefix_pass = audit_causal_prefix_equivalence(
        input_rows,
        statistic_config,
        output_rows,
    )
    group_isolation_pass = audit_group_isolation(
        input_rows,
        statistic_config,
        output_rows,
    )
    raw_huber_isolated = audit_raw_huber_state_isolation(
        input_rows,
        statistic_config,
        output_rows,
    )
    for record in output_rows:
        validate_window_record(record)
    nonfinite_violation_count = 0

    valid_count = sum(int(bool(row["stat_input_valid"])) for row in output_rows)
    invalid_count = len(output_rows) - valid_count
    ready_count = sum(int(bool(row["window_ready"])) for row in output_rows)
    raw_autocorrelation_valid_count = _finite_field_count(
        output_rows,
        "raw_lag1_autocorrelation",
    )
    raw_skewness_valid_count = _finite_field_count(output_rows, "raw_skewness")
    huber_autocorrelation_valid_count = _finite_field_count(
        output_rows,
        "huber_lag1_autocorrelation",
    )
    huber_skewness_valid_count = _finite_field_count(output_rows, "huber_skewness")

    output_path = result_dir / "frame_window_statistics.csv"
    manifest_path = result_dir / "run_manifest.json"
    summary_path = result_dir / "day9_quick_summary.json"
    write_window_csv(output_path, output_rows)
    historical_after = _historical_hashes(root)
    historical_unchanged = historical_before == historical_after
    day9_pass = bool(
        clean_at_start
        and len(input_rows) > 0
        and len(input_rows) == len(output_rows)
        and duplicate_key_count == 0
        and ordering_violation_count == 0
        and frame_key_one_to_one
        and nonfinite_violation_count == 0
        and valid_count > 0
        and ready_count > 0
        and causal_prefix_pass
        and group_isolation_pass
        and raw_huber_isolated
        and historical_unchanged
    )

    summary = {
        "run_id": str(run_id),
        "DAY9_WINDOW_STATS_PASS": day9_pass,
        "STAGE2_GATE": "INCOMPLETE",
        "STAGE3_GATE": "NOT_STARTED",
        "COHERENT_BIAS_DETECTABLE": "UNDETERMINED",
        "RISK_WARNING_AUTHORIZED": False,
        "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
        "PUBLIC_DISCLOSURE_AUTHORIZED": False,
        "git_status_clean_at_start": clean_at_start,
        "input_row_count": len(input_rows),
        "output_row_count": len(output_rows),
        "group_count": group_count,
        "duplicate_key_count": duplicate_key_count,
        "ordering_violation_count": ordering_violation_count,
        "frame_key_one_to_one": frame_key_one_to_one,
        "valid_input_row_count": valid_count,
        "invalid_reset_count": invalid_count,
        "window_ready_row_count": ready_count,
        "raw_autocorrelation_valid_count": raw_autocorrelation_valid_count,
        "raw_skewness_valid_count": raw_skewness_valid_count,
        "huber_autocorrelation_valid_count": huber_autocorrelation_valid_count,
        "huber_skewness_valid_count": huber_skewness_valid_count,
        "nonfinite_violation_count": nonfinite_violation_count,
        "causal_prefix_equivalence_pass": causal_prefix_pass,
        "group_isolation_pass": group_isolation_pass,
        "raw_huber_state_isolated": raw_huber_isolated,
        "historical_artifacts_unchanged": historical_unchanged,
        "gt_file_read": False,
        "gt_field_read": False,
        "reserved_test_run_performed": False,
        "formal_stage2c_rerun_performed": False,
        "representative_stage2c_seed_replayed": False,
        "detection_threshold_created": False,
        "auroc_computed": False,
        "fpr_computed": False,
    }
    write_json(summary_path, summary)

    manifest = {
        **summary,
        "task": "Stage 2 Failure-Mechanism Diagnosis — Day 9",
        "schema_version": WINDOW_SCHEMA_VERSION,
        "git_branch": _git_branch(root),
        "git_commit": git_commit(root),
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_day8_manifest_path": str(source_manifest_path),
        "source_day8_manifest_sha256": sha256_file(source_manifest_path),
        "source_online_log_path": str(online_log_path),
        "source_online_log_sha256": sha256_file(online_log_path),
        "source_online_schema_version": ONLINE_SCHEMA_VERSION,
        "config_path": str(config_path),
        "config_sha256": sha256_file(config_path),
        "source_tree_sha256": compute_source_tree_hash(
            [
                root / "src/eval/stage2_failure_window_stats.py",
                root / "src/eval/stage2_failure_window_schema.py",
                root / "src/eval/stage2_failure_day9.py",
                root / "scripts/33_run_stage2_failure_day9.py",
            ]
        ),
        "frame_window_statistics_sha256": sha256_file(output_path),
        "window_size": int(statistic_config.window_size),
        "cusum_reference_sigma": float(statistic_config.cusum_reference_sigma),
        "sign_zero_epsilon": float(statistic_config.sign_zero_epsilon),
        "moment_epsilon": float(statistic_config.moment_epsilon),
        "historical_artifact_hashes_before": historical_before,
        "historical_artifact_hashes_after": historical_after,
    }
    write_json(manifest_path, manifest)
    return manifest


def window_config_from_mapping(config: Mapping[str, Any]) -> WindowStatisticConfig:
    return WindowStatisticConfig(
        window_size=int(config["window_size"]),
        cusum_reference_sigma=float(config["cusum_reference_sigma"]),
        sign_zero_epsilon=float(config["sign_zero_epsilon"]),
        moment_epsilon=float(config["moment_epsilon"]),
    )


def read_online_csv(path: Path) -> List[Mapping[str, Any]]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"Day 8 online CSV is missing: {source}")
    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ONLINE_FIELDS:
            raise ValueError("Day 9 requires the exact Day 8 online CSV schema")
        rows = [dict(row) for row in reader]
    if not rows:
        raise ValueError("Day 8 online CSV is empty")
    return rows


def validate_source_manifest(
    source_manifest_path: Path,
    online_log_path: Path,
) -> Mapping[str, Any]:
    source = Path(source_manifest_path)
    if not source.is_file():
        raise FileNotFoundError(f"Day 8 source manifest is missing: {source}")
    value = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Day 8 source manifest must contain a mapping")
    required = {
        "DAY8_LOGGING_PASS": True,
        "reserved_test_run_performed": False,
        "formal_stage2c_rerun_performed": False,
        "gt_used_by_online_logger": False,
    }
    for name, expected in required.items():
        if value.get(name) is not expected:
            raise ValueError(f"Day 8 source manifest has unsafe {name}")
    expected_hash = str(value.get("online_log_sha256", ""))
    actual_hash = sha256_file(Path(online_log_path))
    if not expected_hash or expected_hash != actual_hash:
        raise ValueError("Day 8 online CSV SHA-256 does not match its manifest")
    return value


def compute_window_records(
    online_rows: Sequence[Mapping[str, Any]],
    config: WindowStatisticConfig,
) -> List[Mapping[str, Any]]:
    """Process rows in their observed order with one state pair per group."""

    states: Dict[tuple, Tuple[CausalInnovationWindow, CausalInnovationWindow]] = {}
    previous: Dict[tuple, Tuple[int, float]] = {}
    seen_frame_keys = set()
    output = []
    for source in online_rows:
        row = _normalize_online_row(source)
        frame_key = tuple(row[name] for name in FRAME_KEY_FIELDS)
        if frame_key in seen_frame_keys:
            raise ValueError(f"duplicate Day 8 frame key: {frame_key}")
        seen_frame_keys.add(frame_key)
        group = tuple(row[name] for name in DAY9_GROUP_FIELDS)
        if group in previous:
            prior_frame, prior_timestamp = previous[group]
            if int(row["frame_index"]) <= prior_frame:
                raise ValueError("frame_index must be strictly increasing within each group")
            if float(row["timestamp"]) <= prior_timestamp:
                raise ValueError("timestamp must be strictly increasing within each group")
        previous[group] = (int(row["frame_index"]), float(row["timestamp"]))
        if group not in states:
            states[group] = (
                CausalInnovationWindow(config),
                CausalInnovationWindow(config),
            )
        raw_monitor, huber_monitor = states[group]
        valid, reset_reason = statistic_input_state(row)
        raw_value = float(row["weak_innovation_z_raw"])
        huber_value = float(row["weak_innovation_z_huber"])
        raw_stats = raw_monitor.update(raw_value, valid)
        huber_stats = huber_monitor.update(huber_value, valid)
        if (
            raw_stats.window_count != huber_stats.window_count
            or raw_stats.window_ready != huber_stats.window_ready
            or raw_stats.consecutive_valid_count != huber_stats.consecutive_valid_count
        ):
            raise RuntimeError("raw and Huber common window state diverged")
        record = {
            "schema_version": WINDOW_SCHEMA_VERSION,
            "source_online_schema_version": str(row["schema_version"]),
            **{name: row[name] for name in FRAME_KEY_FIELDS},
            "weak_direction_valid": bool(row["weak_direction_valid"]),
            "weak_innovation_valid": bool(row["weak_innovation_valid"]),
            "primary_direction_stable": bool(row["primary_direction_stable"]),
            "degeneracy_triggered": bool(row["degeneracy_triggered"]),
            "actionable_direction": bool(row["actionable_direction"]),
            "odi_trans": float(row["odi_trans"]),
            "primary_eigengap_ratio": float(row["primary_eigengap_ratio"]),
            "stat_input_valid": valid,
            "stat_reset_reason": reset_reason,
            "window_size": int(config.window_size),
            "window_count": int(raw_stats.window_count),
            "window_ready": bool(raw_stats.window_ready),
            "consecutive_valid_count": int(raw_stats.consecutive_valid_count),
            "weak_innovation_z_raw": (
                raw_value if math.isfinite(raw_value) else float("nan")
            ),
            "weak_innovation_z_huber": (
                huber_value if math.isfinite(huber_value) else float("nan")
            ),
            **_prefixed_statistics("raw", raw_stats),
            **_prefixed_statistics("huber", huber_stats),
        }
        validate_window_record(record)
        output.append(record)
    return output


def statistic_input_state(record: Mapping[str, Any]) -> Tuple[bool, str]:
    if not bool(record["weak_direction_valid"]):
        return False, "invalid_direction"
    if not bool(record["weak_innovation_valid"]):
        return False, "invalid_innovation"
    if not bool(record["primary_direction_stable"]):
        return False, "unstable_direction"
    raw = float(record["weak_innovation_z_raw"])
    huber = float(record["weak_innovation_z_huber"])
    if not math.isfinite(raw) or not math.isfinite(huber):
        return False, "nonfinite_signal"
    return True, "none"


def audit_causal_prefix_equivalence(
    input_rows: Sequence[Mapping[str, Any]],
    config: WindowStatisticConfig,
    full_records: Sequence[Mapping[str, Any]],
) -> bool:
    if len(input_rows) != len(full_records):
        return False
    for prefix_length in range(1, len(input_rows) + 1):
        prefix_records = compute_window_records(
            input_rows[:prefix_length],
            config,
        )
        if not _record_sequences_equal(
            prefix_records,
            full_records[:prefix_length],
        ):
            return False
    return True


def audit_group_isolation(
    input_rows: Sequence[Mapping[str, Any]],
    config: WindowStatisticConfig,
    full_records: Sequence[Mapping[str, Any]],
) -> bool:
    expected = {window_frame_key(record): record for record in full_records}
    grouped: Dict[tuple, List[Mapping[str, Any]]] = {}
    for row in input_rows:
        grouped.setdefault(_normalized_group_key(row), []).append(row)
    for rows in grouped.values():
        isolated = compute_window_records(rows, config)
        for record in isolated:
            if not _records_equal(record, expected[window_frame_key(record)]):
                return False
    return True


def audit_raw_huber_state_isolation(
    input_rows: Sequence[Mapping[str, Any]],
    config: WindowStatisticConfig,
    full_records: Sequence[Mapping[str, Any]],
) -> bool:
    expected = {window_frame_key(record): record for record in full_records}
    grouped: Dict[tuple, List[Mapping[str, Any]]] = {}
    for row in input_rows:
        grouped.setdefault(_normalized_group_key(row), []).append(row)
    for rows in grouped.values():
        raw_monitor = CausalInnovationWindow(config)
        huber_monitor = CausalInnovationWindow(config)
        if raw_monitor is huber_monitor:
            return False
        for source in rows:
            row = _normalize_online_row(source)
            valid, _ = statistic_input_state(row)
            raw_stats = raw_monitor.update(float(row["weak_innovation_z_raw"]), valid)
            huber_stats = huber_monitor.update(float(row["weak_innovation_z_huber"]), valid)
            record = expected[tuple(row[name] for name in FRAME_KEY_FIELDS)]
            if not _statistics_match_prefix(record, "raw", raw_stats):
                return False
            if not _statistics_match_prefix(record, "huber", huber_stats):
                return False
    return True


def _normalize_online_row(source: Mapping[str, Any]) -> Mapping[str, Any]:
    required = [
        "schema_version",
        *FRAME_KEY_FIELDS,
        "weak_direction_valid",
        "weak_innovation_valid",
        "primary_direction_stable",
        "degeneracy_triggered",
        "actionable_direction",
        "odi_trans",
        "primary_eigengap_ratio",
        "weak_innovation_z_raw",
        "weak_innovation_z_huber",
    ]
    missing = [name for name in required if name not in source]
    if missing:
        raise ValueError(f"Day 8 online row is missing fields: {missing}")
    if str(source["schema_version"]) != ONLINE_SCHEMA_VERSION:
        raise ValueError("Day 8 online row schema version mismatch")
    return {
        "schema_version": str(source["schema_version"]),
        "run_id": str(source["run_id"]),
        "sequence_id": str(source["sequence_id"]),
        "sweep": str(source["sweep"]),
        "level": str(source["level"]),
        "stress": str(source["stress"]),
        "geometry_seed": _parse_int(source["geometry_seed"], "geometry_seed"),
        "sensor_seed": _parse_int(source["sensor_seed"], "sensor_seed"),
        "process_seed": _parse_int(source["process_seed"], "process_seed"),
        "method": str(source["method"]),
        "frame_index": _parse_int(source["frame_index"], "frame_index"),
        "timestamp": _parse_float(source["timestamp"], "timestamp"),
        "weak_direction_valid": _parse_bool(
            source["weak_direction_valid"],
            "weak_direction_valid",
        ),
        "weak_innovation_valid": _parse_bool(
            source["weak_innovation_valid"],
            "weak_innovation_valid",
        ),
        "primary_direction_stable": _parse_bool(
            source["primary_direction_stable"],
            "primary_direction_stable",
        ),
        "degeneracy_triggered": _parse_bool(
            source["degeneracy_triggered"],
            "degeneracy_triggered",
        ),
        "actionable_direction": _parse_bool(
            source["actionable_direction"],
            "actionable_direction",
        ),
        "odi_trans": _parse_float(source["odi_trans"], "odi_trans"),
        "primary_eigengap_ratio": _parse_float(
            source["primary_eigengap_ratio"],
            "primary_eigengap_ratio",
        ),
        "weak_innovation_z_raw": _parse_float(
            source["weak_innovation_z_raw"],
            "weak_innovation_z_raw",
        ),
        "weak_innovation_z_huber": _parse_float(
            source["weak_innovation_z_huber"],
            "weak_innovation_z_huber",
        ),
    }


def _prefixed_statistics(
    prefix: str,
    statistics: SignalWindowStatistics,
) -> Mapping[str, Any]:
    return {
        f"{prefix}_{name}": getattr(statistics, name)
        for name in SIGNAL_FLOAT_SUFFIXES + SIGNAL_INTEGER_SUFFIXES
    }


def _statistics_match_prefix(
    record: Mapping[str, Any],
    prefix: str,
    statistics: SignalWindowStatistics,
) -> bool:
    expected = _prefixed_statistics(prefix, statistics)
    return all(_values_equal(record[name], value) for name, value in expected.items())


def _record_sequences_equal(
    left: Sequence[Mapping[str, Any]],
    right: Sequence[Mapping[str, Any]],
) -> bool:
    return len(left) == len(right) and all(
        _records_equal(first, second) for first, second in zip(left, right)
    )


def _records_equal(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return set(left) == set(right) and all(
        _values_equal(left[name], right[name]) for name in left
    )


def _values_equal(left: Any, right: Any) -> bool:
    if isinstance(left, (float, np.floating)) or isinstance(right, (float, np.floating)):
        first = float(left)
        second = float(right)
        if math.isnan(first) and math.isnan(second):
            return True
        return math.isfinite(first) and math.isfinite(second) and abs(first - second) <= 1.0e-12
    return left == right


def _normalized_frame_key(row: Mapping[str, Any]) -> tuple:
    normalized = _normalize_online_row(row)
    return tuple(normalized[name] for name in FRAME_KEY_FIELDS)


def _normalized_group_key(row: Mapping[str, Any]) -> tuple:
    normalized = _normalize_online_row(row)
    return tuple(normalized[name] for name in DAY9_GROUP_FIELDS)


def _parse_bool(value: Any, name: str) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
        return value.strip().lower() == "true"
    raise ValueError(f"{name} must be a strict boolean")


def _parse_int(value: Any, name: str) -> int:
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{name} must be an integer")
    parsed = int(value)
    if float(value) != float(parsed):
        raise ValueError(f"{name} must be an integer")
    return parsed


def _parse_float(value: Any, name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be numeric") from error


def _validate_day9_quick_config(config: Mapping[str, Any]) -> None:
    fixed_false = [
        "use_reserved_test",
        "formal_experiment",
        "replay_stage2c_representative_seed",
        "compute_detection_threshold",
        "compute_auroc",
        "compute_fpr",
    ]
    if config.get("mode") != "day9_quick":
        raise ValueError("Day 9 only supports mode=day9_quick")
    if config.get("schema_version") != WINDOW_SCHEMA_VERSION:
        raise ValueError("Day 9 schema version mismatch")
    if any(bool(config.get(name)) for name in fixed_false):
        raise ValueError("Day 9 Quick forbids formal, reserved, threshold, and ROC modes")
    if config.get("primary_signal") != "weak_innovation_z_huber":
        raise ValueError("Day 9 primary signal is frozen to Huber weak innovation")
    if config.get("diagnostic_signal") != "weak_innovation_z_raw":
        raise ValueError("Day 9 diagnostic signal is frozen to raw weak innovation")
    if int(config.get("window_size", -1)) != 5:
        raise ValueError("Day 9 Quick window size is frozen at five")
    if float(config.get("cusum_reference_sigma", -1.0)) != 0.5:
        raise ValueError("Day 9 Quick CUSUM reference is frozen at 0.5")
    if float(config.get("sign_zero_epsilon", -1.0)) != 1.0e-12:
        raise ValueError("Day 9 Quick sign-zero epsilon is frozen at 1.0e-12")
    if float(config.get("moment_epsilon", -1.0)) != 1.0e-12:
        raise ValueError("Day 9 Quick moment epsilon is frozen at 1.0e-12")
    if not bool(config.get("require_primary_direction_stable")):
        raise ValueError("Day 9 requires a stable primary direction")
    if not bool(config.get("reset_on_invalid_frame")):
        raise ValueError("Day 9 must reset on every invalid frame")
    if not bool(config.get("allow_partial_window_statistics")):
        raise ValueError("Day 9 Quick must expose partial-window statistics")


def _historical_hashes(root: Path) -> Mapping[str, str]:
    return {
        name: compute_directory_hash(root / name)
        for name in HISTORICAL_ARTIFACT_PATHS
    }


def _finite_field_count(rows: Sequence[Mapping[str, Any]], name: str) -> int:
    return sum(int(math.isfinite(float(row[name]))) for row in rows)


def _git_branch(root: Path) -> str:
    return subprocess.check_output(
        ["git", "branch", "--show-current"], cwd=root, text=True
    ).strip()
