"""Quick-only Day 10 orchestration for the strict no-GT online audit."""

from __future__ import annotations

import math
import platform
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

import numpy as np
import scipy

from eval.analysis_lock import (
    compute_directory_hash,
    compute_source_tree_hash,
    git_commit,
    git_status_clean,
    sha256_file,
)
from eval.stage2_failure_day8 import DAY8_FIXTURE_ID, build_day8_unit_fixture
from eval.stage2_failure_day9 import window_config_from_mapping
from eval.stage2_failure_no_gt_audit import (
    NO_GT_AUDIT_SCHEMA_VERSION,
    ONLINE_CONTINUOUS_RESULT_FIELDS,
    ONLINE_DISCRETE_RESULT_FIELDS,
    ONLINE_EQUIVALENCE_FIELDS,
    RUNTIME_VARIANTS,
    WINDOW_EQUIVALENCE_FIELDS,
    GTAccessSentinelMapping,
    audit_static_dependencies,
    compare_online_runs,
    compare_window_runs,
    compute_window_records,
    execute_online_variant,
    make_runtime_variants,
    run_filesystem_sandbox_audit,
    run_invalid_reset_end_to_end,
    write_fixed_audit_csv,
)
from eval.synthetic_pipeline_common import load_yaml, write_json


HISTORICAL_ARTIFACT_PATHS = (
    "artifacts/current/detector_stage2a",
    "artifacts/history/stage2b_column_scaling_no_go",
    "artifacts/current/weak_update_stage2c",
)
DAY9_CHECKPOINT = "checkpoint/day9-window-stats-pass"


def run_stage2_failure_day10(
    root: Path,
    run_id: str,
    output_root: Path,
    overwrite: bool = False,
    config_path: Path = None,
) -> Mapping[str, Any]:
    """Run the deterministic Day 10 engineering-only no-GT audit."""

    root = Path(root).resolve()
    config_path = (
        root / "configs/stage2_failure/day10_quick.yaml"
        if config_path is None
        else Path(config_path).resolve()
    )
    config = load_yaml(config_path)
    validate_day10_quick_config(config)
    clean_at_start = git_status_clean(root)
    result_dir = Path(output_root).resolve() / str(run_id)
    if result_dir.exists():
        if not overwrite:
            raise FileExistsError(f"Day 10 output already exists: {result_dir}; use --overwrite")
        shutil.rmtree(result_dir)
    result_dir.mkdir(parents=True)

    historical_before = _historical_hashes(root)
    static_audit = audit_static_dependencies(root)
    observations, motion = build_day8_unit_fixture(int(config["frame_limit"]))
    day8_config_path = root / "configs/stage2_failure/day8_quick.yaml"
    day9_config_path = root / "configs/stage2_failure/day9_quick.yaml"
    day8_config = load_yaml(day8_config_path)
    day9_config = load_yaml(day9_config_path)
    methods = [str(method) for method in day8_config["methods"]]
    detector_config = load_yaml(root / "configs/detector/odi_stage2a.yaml")
    update_config = load_yaml(root / "configs/update/stage2c_common.yaml")
    context = {
        "run_id": str(run_id),
        "sequence_id": DAY8_FIXTURE_ID,
        "sweep": "day10_quick",
        "level": "unit",
        "stress": "strict_no_gt_dependency_audit",
        "geometry_seed": int(day8_config["geometry_seed"]),
        "sensor_seed": int(day8_config["sensor_seed"]),
        "process_seed": int(day8_config["process_seed"]),
    }
    variants = make_runtime_variants(observations)
    if tuple(variants) != tuple(config["runtime_variants"]):
        raise ValueError("runtime variant order differs from the frozen Day 10 config")
    runtime_runs: Dict[str, Mapping[str, Mapping[str, Any]]] = {}
    for variant in config["runtime_variants"]:
        runtime_runs[str(variant)] = execute_online_variant(
            variants[str(variant)],
            motion,
            detector_config,
            update_config,
            methods,
            float(day8_config["online_odi_threshold"]),
            float(day8_config["attenuation_alpha"]),
            context,
            float(day8_config["directional_information_epsilon"]),
        )

    control_runs = runtime_runs["gt_present_control"]
    online_rows = []
    for variant in config["runtime_variants"][1:]:
        online_rows.extend(
            compare_online_runs(
                str(variant),
                control_runs,
                runtime_runs[str(variant)],
                float(config["continuous_comparison_tolerance"]),
                bool(config["require_exact_array_checksum_match"]),
                bool(config["require_exact_online_record_match"]),
            )
        )
    online_path = result_dir / "online_equivalence_audit.csv"
    write_fixed_audit_csv(online_path, ONLINE_EQUIVALENCE_FIELDS, online_rows)

    window_config = window_config_from_mapping(day9_config)
    window_runs: Dict[str, Mapping[str, Sequence[Mapping[str, Any]]]] = {}
    for variant, runs in runtime_runs.items():
        window_runs[variant] = {
            method: compute_window_records(run["records"], window_config)
            for method, run in runs.items()
        }
    window_rows = []
    for variant in config["runtime_variants"][1:]:
        for method in methods:
            window_rows.append(
                compare_window_runs(
                    str(variant),
                    method,
                    window_runs["gt_present_control"][method],
                    window_runs[str(variant)][method],
                    bool(config["require_exact_window_record_match"]),
                )
            )
    window_path = result_dir / "window_equivalence_audit.csv"
    write_fixed_audit_csv(window_path, WINDOW_EQUIVALENCE_FIELDS, window_rows)
    write_json(result_dir / "static_dependency_audit.json", static_audit)

    day8_run = (
        root
        / "results/stage2_failure_analysis/day8_quick/stage2_failure_day8_quick_v2"
    )
    online_log_path = day8_run / "frame_diagnostics_online.csv"
    source_manifest_path = day8_run / "run_manifest.json"
    if not online_log_path.is_file() or not source_manifest_path.is_file():
        raise FileNotFoundError("Day 10 requires the passing Day 8 Quick v2 online evidence")
    with tempfile.TemporaryDirectory(prefix="degen_lio_day10_sandbox_") as temporary:
        filesystem_audit = run_filesystem_sandbox_audit(
            root,
            Path(temporary),
            online_log_path,
            source_manifest_path,
        )
    write_json(result_dir / "filesystem_sandbox_audit.json", filesystem_audit)

    template = control_runs[methods[0]]["records"][0]
    with tempfile.TemporaryDirectory(prefix="degen_lio_day10_reset_") as temporary:
        invalid_reset_audit, invalid_output_path = run_invalid_reset_end_to_end(
            root,
            Path(temporary),
            template,
        )
        shutil.copy2(invalid_output_path, result_dir / "invalid_reset_end_to_end.csv")
    write_json(result_dir / "invalid_reset_audit.json", invalid_reset_audit)

    sentinel = variants["gt_access_sentinel"]
    if not isinstance(sentinel, GTAccessSentinelMapping):
        raise RuntimeError("the GT access sentinel variant was not installed")
    array_rows = [
        row
        for row in online_rows
        if row["field_type"] in {"continuous", "discrete"}
    ]
    continuous_rows = [row for row in online_rows if row["field_type"] == "continuous"]
    discrete_rows = [row for row in online_rows if row["field_type"] == "discrete"]
    record_rows = [row for row in online_rows if row["field_type"] == "record_sequence"]
    historical_after = _historical_hashes(root)
    historical_unchanged = historical_before == historical_after
    maximums = _online_maximums(continuous_rows)
    online_failure_count = sum(int(not bool(row["pass"])) for row in online_rows)
    window_failure_count = sum(int(not bool(row["pass"])) for row in window_rows)
    nonfinite_violation_count = _runtime_nonfinite_violation_count(runtime_runs)
    online_checksum_mismatch_count = sum(
        int(row["control_sha256"] != row["variant_sha256"])
        for row in array_rows
    )
    online_record_checksum_mismatch_count = sum(
        int(row["control_sha256"] != row["variant_sha256"])
        for row in record_rows
    )
    window_record_checksum_mismatch_count = sum(
        int(row["control_sha256"] != row["variant_sha256"])
        for row in window_rows
    )
    metrics = {
        "git_status_clean_at_start": clean_at_start,
        "output_schema_pass": True,
        "nonfinite_violation_count": nonfinite_violation_count,
        "static_audit_pass": bool(static_audit["audit_pass"]),
        "forbidden_import_count": len(static_audit["forbidden_imports"]),
        "forbidden_signature_parameter_count": len(
            static_audit["forbidden_signature_parameters"]
        ),
        "forbidden_online_schema_field_count": len(
            static_audit["forbidden_online_schema_fields"]
        ),
        "ast_parse_failure_count": len(static_audit["parse_failures"]),
        "gt_removed_run_succeeded": "gt_removed" in runtime_runs,
        "gt_access_sentinel_run_succeeded": "gt_access_sentinel" in runtime_runs,
        "gt_poisoned_run_succeeded": "gt_poisoned" in runtime_runs,
        "gt_permuted_run_succeeded": "gt_permuted" in runtime_runs,
        "gt_field_access_attempt_count": sentinel.access_attempt_count,
        "online_equivalence_comparison_count": len(online_rows),
        "online_continuous_comparison_count": len(continuous_rows),
        "online_discrete_comparison_count": len(discrete_rows),
        "online_equivalence_failure_count": online_failure_count,
        **maximums,
        "online_checksum_mismatch_count": online_checksum_mismatch_count,
        "online_record_checksum_mismatch_count": online_record_checksum_mismatch_count,
        "window_equivalence_comparison_count": len(window_rows),
        "window_equivalence_failure_count": window_failure_count,
        "window_record_checksum_mismatch_count": window_record_checksum_mismatch_count,
        **filesystem_audit,
        "filesystem_sandbox_pass": filesystem_audit["sandbox_pass"],
        "invalid_reset_fixture_row_count": invalid_reset_audit["fixture_row_count"],
        "invalid_reset_count": invalid_reset_audit["invalid_reset_count"],
        "invalid_reset_expected_counts_match": invalid_reset_audit[
            "invalid_reset_expected_counts_match"
        ],
        "invalid_reset_cusum_reset_match": invalid_reset_audit[
            "invalid_reset_cusum_reset_match"
        ],
        "invalid_reset_end_to_end_pass": invalid_reset_audit[
            "invalid_reset_end_to_end_pass"
        ],
        "historical_artifact_hashes_before": historical_before,
        "historical_artifact_hashes_after": historical_after,
        "historical_artifacts_unchanged": historical_unchanged,
        "reserved_test_run_performed": False,
        "formal_stage2c_rerun_performed": False,
        "representative_stage2c_seed_replayed": False,
        "detection_threshold_created": False,
        "auroc_computed": False,
        "fpr_computed": False,
        "f1_computed": False,
        "detection_delay_computed": False,
        "fast_lio2_integrated": False,
    }
    day10_pass = evaluate_day10_gate(metrics)
    summary = {
        "run_id": str(run_id),
        **metrics,
        "DAY10_NO_GT_AUDIT_PASS": day10_pass,
        "STAGE2_GATE": "INCOMPLETE",
        "STAGE3_GATE": "NOT_STARTED",
        "COHERENT_BIAS_DETECTABLE": "UNDETERMINED",
        "RISK_WARNING_AUTHORIZED": False,
        "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
        "PUBLIC_DISCLOSURE_AUTHORIZED": False,
    }
    summary_path = result_dir / "day10_quick_summary.json"
    write_json(summary_path, summary)
    manifest = {
        **summary,
        "task": "Stage 2 Failure-Mechanism Diagnosis — Day 10",
        "schema_version": NO_GT_AUDIT_SCHEMA_VERSION,
        "git_branch": _git_branch(root),
        "git_commit": git_commit(root),
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "day9_checkpoint_commit": _git_commit_for_ref(root, DAY9_CHECKPOINT),
        "source_day8_config_sha256": sha256_file(day8_config_path),
        "source_day9_config_sha256": sha256_file(day9_config_path),
        "source_tree_sha256": compute_source_tree_hash(
            [
                root / "src/eval/stage2_failure_no_gt_audit.py",
                root / "src/eval/stage2_failure_day10.py",
                root / "src/eval/stage2_failure_logging.py",
                root / "src/eval/stage2_failure_window_stats.py",
                root / "src/eval/stage2_failure_window_schema.py",
                root / "src/eval/stage2_failure_day9.py",
                root / "src/minibench/map_lio.py",
                root / "scripts/34_run_stage2_failure_day10.py",
            ]
        ),
        "day10_config_sha256": sha256_file(config_path),
        "method_list": methods,
        "variant_list": list(config["runtime_variants"]),
        "frame_count": int(config["frame_limit"]),
        "online_equivalence_audit_sha256": sha256_file(online_path),
        "window_equivalence_audit_sha256": sha256_file(window_path),
        "static_dependency_audit_sha256": sha256_file(
            result_dir / "static_dependency_audit.json"
        ),
        "filesystem_sandbox_audit_sha256": sha256_file(
            result_dir / "filesystem_sandbox_audit.json"
        ),
        "invalid_reset_end_to_end_sha256": sha256_file(
            result_dir / "invalid_reset_end_to_end.csv"
        ),
        "invalid_reset_audit_sha256": sha256_file(
            result_dir / "invalid_reset_audit.json"
        ),
    }
    write_json(result_dir / "run_manifest.json", manifest)
    return manifest


def validate_day10_quick_config(config: Mapping[str, Any]) -> None:
    expected_scalars = {
        "mode": "day10_quick",
        "schema_version": NO_GT_AUDIT_SCHEMA_VERSION,
        "use_reserved_test": False,
        "formal_experiment": False,
        "replay_stage2c_representative_seed": False,
        "create_detection_threshold": False,
        "compute_auroc": False,
        "compute_fpr": False,
        "compute_f1": False,
        "compute_detection_delay": False,
        "inherit_day8_methods": True,
        "frame_limit": 8,
        "continuous_comparison_tolerance": 1.0e-12,
        "require_exact_array_checksum_match": True,
        "require_exact_online_record_match": True,
        "require_exact_window_record_match": True,
        "run_filesystem_sandbox": True,
        "run_invalid_reset_end_to_end": True,
    }
    expected_fields = set(expected_scalars) | {
        "offline_field_names",
        "runtime_variants",
    }
    missing = sorted(expected_fields - set(config))
    extra = sorted(set(config) - expected_fields)
    if missing or extra:
        raise ValueError(
            f"Day 10 Quick config fields are frozen: missing={missing}, extra={extra}"
        )
    for name, expected in expected_scalars.items():
        actual = config.get(name)
        if isinstance(expected, float):
            matches = isinstance(actual, (int, float)) and not isinstance(actual, bool) and float(actual) == expected
        else:
            matches = actual == expected and type(actual) is type(expected)
        if not matches:
            raise ValueError(f"Day 10 Quick freezes {name}={expected!r}")
    if list(config.get("offline_field_names", [])) != ["pose_gt", "axis_per_frame"]:
        raise ValueError("Day 10 offline field names are frozen")
    if list(config.get("runtime_variants", [])) != list(RUNTIME_VARIANTS):
        raise ValueError("Day 10 runtime variants are frozen")
    forbidden_mode_names = {
        "development",
        "test",
        "reserved_test",
        "representative_seed",
        "threshold",
        "roc",
        "fpr",
        "auroc",
    }
    for name, value in config.items():
        normalized = str(name).lower().replace("-", "_")
        if any(token in normalized for token in forbidden_mode_names) and bool(value):
            if name not in expected_scalars:
                raise ValueError(f"Day 10 Quick forbids enabled option: {name}")


def evaluate_day10_gate(values: Mapping[str, Any]) -> bool:
    required_true = (
        "git_status_clean_at_start",
        "output_schema_pass",
        "static_audit_pass",
        "gt_removed_run_succeeded",
        "gt_access_sentinel_run_succeeded",
        "gt_poisoned_run_succeeded",
        "gt_permuted_run_succeeded",
        "filesystem_sandbox_pass",
        "output_byte_identical",
        "invalid_reset_expected_counts_match",
        "invalid_reset_cusum_reset_match",
        "invalid_reset_end_to_end_pass",
        "historical_artifacts_unchanged",
    )
    required_zero = (
        "nonfinite_violation_count",
        "forbidden_import_count",
        "forbidden_signature_parameter_count",
        "forbidden_online_schema_field_count",
        "ast_parse_failure_count",
        "gt_field_access_attempt_count",
        "online_equivalence_failure_count",
        "online_checksum_mismatch_count",
        "online_record_checksum_mismatch_count",
        "window_equivalence_failure_count",
        "window_record_checksum_mismatch_count",
        "no_gt_subprocess_return_code",
        "fake_gt_subprocess_return_code",
    )
    required_false = (
        "gt_file_required",
        "fake_gt_file_affected_output",
        "reserved_test_run_performed",
        "formal_stage2c_rerun_performed",
        "representative_stage2c_seed_replayed",
        "detection_threshold_created",
        "auroc_computed",
        "fpr_computed",
        "f1_computed",
        "detection_delay_computed",
        "fast_lio2_integrated",
    )
    maximum_fields = (
        "online_max_trajectory_difference",
        "online_max_covariance_difference",
        "online_max_applied_delta_difference",
        "online_max_full_delta_difference",
        "online_max_delta_difference",
    )
    return bool(
        all(values.get(name) is True for name in required_true)
        and all(int(values.get(name, -1)) == 0 for name in required_zero)
        and all(values.get(name) is False for name in required_false)
        and all(
            math.isfinite(float(values.get(name, float("inf"))))
            and float(values[name]) <= 1.0e-12
            for name in maximum_fields
        )
        and int(values.get("invalid_reset_fixture_row_count", -1)) == 11
        and int(values.get("invalid_reset_count", -1)) == 1
        and int(values.get("online_equivalence_comparison_count", 0)) > 0
        and int(values.get("window_equivalence_comparison_count", 0)) > 0
    )


def _online_maximums(rows: Sequence[Mapping[str, Any]]) -> Mapping[str, float]:
    def maximum(fields: Sequence[str]) -> float:
        values = [
            float(row["max_abs_difference"])
            for row in rows
            if row["field"] in fields
        ]
        return max(values) if values else float("inf")

    applied = maximum(["applied_deltas"])
    full = maximum(["full_deltas"])
    return {
        "online_max_trajectory_difference": maximum(["prior_poses", "poses"]),
        "online_max_covariance_difference": maximum(["covariances"]),
        "online_max_applied_delta_difference": applied,
        "online_max_full_delta_difference": full,
        "online_max_delta_difference": max(applied, full),
    }


def _runtime_nonfinite_violation_count(
    runtime_runs: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> int:
    count = 0
    for runs in runtime_runs.values():
        for run in runs.values():
            for field in ONLINE_CONTINUOUS_RESULT_FIELDS:
                count += int(
                    np.count_nonzero(
                        ~np.isfinite(np.asarray(run["comparison_fields"][field]))
                    )
                )
    return count


def _historical_hashes(root: Path) -> Mapping[str, str]:
    return {
        name: compute_directory_hash(root / name)
        for name in HISTORICAL_ARTIFACT_PATHS
    }


def _git_branch(root: Path) -> str:
    return subprocess.check_output(
        ["git", "branch", "--show-current"], cwd=root, text=True
    ).strip()


def _git_commit_for_ref(root: Path, ref: str) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", f"{ref}^{{commit}}"], cwd=root, text=True
    ).strip()
