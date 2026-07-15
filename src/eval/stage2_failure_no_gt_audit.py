"""Strict static and runtime no-GT audits for the Day 8/Day 9 online path."""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, Dict, List, MutableSequence, Optional, Sequence, Tuple

import numpy as np

from eval.analysis_lock import sha256_file
from eval.stage2_failure_day9 import (
    compute_window_records,
    run_stage2_failure_day9,
)
from eval.stage2_failure_logging import Stage2FailureOnlineLogger
from eval.stage2_failure_schema import (
    FRAME_KEY_FIELDS,
    ONLINE_FIELDS,
    write_online_csv,
)
from eval.stage2_failure_window_schema import (
    SIGNAL_FLOAT_SUFFIXES,
    WINDOW_FIELDS,
    write_window_csv,
)
from eval.stage2_failure_window_stats import WindowStatisticConfig
from eval.synthetic_pipeline_common import write_json
from minibench.map_lio import run_map_lio


NO_GT_AUDIT_SCHEMA_VERSION = "stage2_failure_no_gt_audit_v1"
GT_FIELD_NAMES = ("pose_gt", "axis_per_frame")
RUNTIME_VARIANTS = (
    "gt_present_control",
    "gt_removed",
    "gt_access_sentinel",
    "gt_poisoned",
    "gt_permuted",
)
ONLINE_CONTINUOUS_RESULT_FIELDS = (
    "prior_poses",
    "poses",
    "applied_deltas",
    "full_deltas",
    "covariances",
)
ONLINE_DISCRETE_RESULT_FIELDS = (
    "detector_triggered",
    "primary_direction_stable",
    "actionable_direction",
    "solver_failure",
)
ONLINE_EQUIVALENCE_FIELDS = (
    "variant",
    "method",
    "field",
    "field_type",
    "shape_control",
    "shape_variant",
    "dtype_control",
    "dtype_variant",
    "max_abs_difference",
    "exact_array_equal",
    "control_sha256",
    "variant_sha256",
    "finite_control",
    "finite_variant",
    "pass",
)
WINDOW_EQUIVALENCE_FIELDS = (
    "variant",
    "method",
    "control_row_count",
    "variant_row_count",
    "frame_keys_equal",
    "records_equal",
    "control_sha256",
    "variant_sha256",
    "pass",
)

STATIC_AUDIT_FILES = (
    "src/eval/stage2_failure_logging.py",
    "src/eval/stage2_failure_window_stats.py",
    "src/eval/stage2_failure_window_schema.py",
    "src/eval/stage2_failure_day9.py",
    "src/minibench/map_lio.py",
)
_STATIC_API_TARGETS = {
    "src/eval/stage2_failure_logging.py": {
        "Stage2FailureOnlineLogger.__init__",
        "Stage2FailureOnlineLogger.log_frame",
    },
    "src/eval/stage2_failure_day9.py": {
        "compute_window_records",
        "run_stage2_failure_day9",
    },
    "src/minibench/map_lio.py": {"run_map_lio"},
}
_FORBIDDEN_IMPORT_MARKERS = (
    "stage2_failure_gt_metrics",
    "update_metrics",
    "oracle_evaluator",
    "evaluate_gt_frame_records",
)
_FORBIDDEN_SIGNATURE_PARAMETERS = {
    "pose_gt",
    "axis_per_frame",
    "gt_axis",
    "oracle_axis",
    "scene_label",
}
_FORBIDDEN_SCHEMA_TOKEN_SEQUENCES = (
    ("gt",),
    ("oracle",),
    ("pose", "gt"),
    ("axis", "per", "frame"),
    ("prior", "axis", "error"),
    ("posterior", "axis", "error"),
    ("error", "reduction"),
    ("scene", "label"),
)
_INVALID_DIRECTION_FLOAT_FIELDS = (
    "weak_direction_raw_world_x",
    "weak_direction_raw_world_y",
    "weak_direction_raw_world_z",
    "weak_direction_logged_world_x",
    "weak_direction_logged_world_y",
    "weak_direction_logged_world_z",
    "weak_score_gradient_raw",
    "weak_score_information_raw",
    "weak_innovation_z_raw",
    "weak_score_gradient_huber",
    "weak_score_information_huber",
    "weak_innovation_z_huber",
    "full_update_weak_signed_m",
    "full_update_weak_abs_m",
    "full_update_strong_x",
    "full_update_strong_y",
    "full_update_strong_z",
    "full_update_strong_norm_m",
    "applied_update_weak_signed_m",
    "applied_update_weak_abs_m",
    "applied_update_strong_x",
    "applied_update_strong_y",
    "applied_update_strong_z",
    "applied_update_strong_norm_m",
)


class ForbiddenGTAccessError(RuntimeError):
    """Raised immediately when an online path explicitly requests a GT field."""


class GTAccessSentinelMapping(Mapping):
    """Read-only observation mapping that hides and guards every offline GT field."""

    def __init__(self, observations: Mapping[str, Any]):
        self._observations = observations
        self._accessed_fields: MutableSequence[str] = []
        self._online_fields = tuple(
            name for name in observations if name not in GT_FIELD_NAMES
        )

    def __getitem__(self, key: str) -> Any:
        if key in GT_FIELD_NAMES:
            self._forbid(key)
        return self._observations[key]

    def get(self, key: str, default: Any = None) -> Any:
        if key in GT_FIELD_NAMES:
            self._forbid(key)
        return self._observations.get(key, default)

    def __iter__(self) -> Iterator[str]:
        return iter(self._online_fields)

    def __len__(self) -> int:
        return len(self._online_fields)

    def __contains__(self, key: object) -> bool:
        if key in GT_FIELD_NAMES:
            self._forbid(str(key))
        return key in self._online_fields

    @property
    def accessed_fields(self) -> Tuple[str, ...]:
        return tuple(self._accessed_fields)

    @property
    def access_attempt_count(self) -> int:
        return len(self._accessed_fields)

    def _forbid(self, key: str) -> None:
        self._accessed_fields.append(str(key))
        raise ForbiddenGTAccessError(f"online path attempted forbidden GT access: {key}")


def make_runtime_variants(
    observations: Mapping[str, Any],
    poison_value: float = 1.0e30,
) -> Mapping[str, Mapping[str, Any]]:
    """Build all variants from one fixture without resampling or mutating it."""

    return {
        "gt_present_control": observations,
        "gt_removed": {
            name: value
            for name, value in observations.items()
            if name not in GT_FIELD_NAMES
        },
        "gt_access_sentinel": GTAccessSentinelMapping(observations),
        "gt_poisoned": poison_gt_observations(observations, poison_value),
        "gt_permuted": permute_gt_observations(observations),
    }


def poison_gt_observations(
    observations: Mapping[str, Any],
    poison_value: float,
) -> Mapping[str, Any]:
    poisoned = dict(observations)
    for name in GT_FIELD_NAMES:
        source = np.asarray(observations[name])
        poisoned[name] = np.full(source.shape, poison_value, dtype=float)
    return poisoned


def permute_gt_observations(observations: Mapping[str, Any]) -> Mapping[str, Any]:
    permuted = dict(observations)
    for name in GT_FIELD_NAMES:
        permuted[name] = np.asarray(observations[name])[::-1].copy()
    return permuted


def execute_online_variant(
    observations: Mapping[str, Any],
    motion: Mapping[str, Any],
    detector_config: Mapping[str, Any],
    update_config: Mapping[str, Any],
    methods: Sequence[str],
    online_odi_threshold: float,
    attenuation_alpha: float,
    context: Mapping[str, Any],
    directional_information_epsilon: float,
) -> Mapping[str, Mapping[str, Any]]:
    """Run the same non-Oracle online estimator and logger for every method."""

    runs: Dict[str, Mapping[str, Any]] = {}
    for method in methods:
        method_context = dict(context)
        method_context["method"] = str(method)
        logger = Stage2FailureOnlineLogger(
            method_context,
            directional_information_epsilon,
        )
        result = run_map_lio(
            observations,
            motion,
            detector_config,
            update_config,
            str(method),
            online_odi_threshold,
            attenuation_alpha,
            failure_logger=logger,
        )
        records = list(logger.records)
        frame_count = int(np.asarray(result["poses"]).shape[0])
        stable = np.zeros(frame_count, dtype=bool)
        solver_failure = np.zeros(frame_count, dtype=bool)
        for record in records:
            index = int(record["frame_index"])
            stable[index] = bool(record["primary_direction_stable"])
            solver_failure[index] = bool(record["solver_failure"])
        comparison_fields = {
            name: np.asarray(result[name])
            for name in ONLINE_CONTINUOUS_RESULT_FIELDS
        }
        comparison_fields.update(
            {
                "detector_triggered": np.asarray(result["detector_triggered"]),
                "primary_direction_stable": stable,
                "actionable_direction": np.asarray(result["actionable_direction"]),
                "solver_failure": solver_failure,
            }
        )
        runs[str(method)] = {
            "result": result,
            "records": records,
            "comparison_fields": comparison_fields,
        }
    return runs


def array_sha256(value: np.ndarray) -> str:
    """Hash dtype, shape, and C-contiguous bytes without stringifying values."""

    array = np.asarray(value)
    contiguous = np.ascontiguousarray(array)
    digest = hashlib.sha256()
    digest.update(array.dtype.str.encode("ascii"))
    digest.update(b"\0")
    digest.update(json.dumps(list(array.shape), separators=(",", ":")).encode("ascii"))
    digest.update(b"\0")
    digest.update(contiguous.tobytes(order="C"))
    return digest.hexdigest()


def compare_array_field(
    variant: str,
    method: str,
    field: str,
    field_type: str,
    control: np.ndarray,
    candidate: np.ndarray,
    tolerance: float,
    require_exact_checksum: bool = True,
) -> Mapping[str, Any]:
    first = np.asarray(control)
    second = np.asarray(candidate)
    shape_equal = first.shape == second.shape
    dtype_equal = first.dtype == second.dtype
    finite_first = _array_is_finite(first)
    finite_second = _array_is_finite(second)
    maximum = _maximum_array_difference(first, second)
    exact = bool(shape_equal and np.array_equal(first, second))
    first_hash = array_sha256(first)
    second_hash = array_sha256(second)
    checksum_equal = first_hash == second_hash
    expected_dtype = (
        np.issubdtype(first.dtype, np.floating)
        and np.issubdtype(second.dtype, np.floating)
        if field_type == "continuous"
        else first.dtype == np.dtype(bool) and second.dtype == np.dtype(bool)
    )
    passed = bool(
        shape_equal
        and dtype_equal
        and expected_dtype
        and finite_first
        and finite_second
        and maximum <= float(tolerance)
        and (field_type != "discrete" or exact)
        and (not require_exact_checksum or checksum_equal)
    )
    return {
        "variant": str(variant),
        "method": str(method),
        "field": str(field),
        "field_type": str(field_type),
        "shape_control": _shape_text(first.shape),
        "shape_variant": _shape_text(second.shape),
        "dtype_control": str(first.dtype),
        "dtype_variant": str(second.dtype),
        "max_abs_difference": maximum,
        "exact_array_equal": exact,
        "control_sha256": first_hash,
        "variant_sha256": second_hash,
        "finite_control": finite_first,
        "finite_variant": finite_second,
        "pass": passed,
    }


def compare_online_runs(
    variant: str,
    control_runs: Mapping[str, Mapping[str, Any]],
    candidate_runs: Mapping[str, Mapping[str, Any]],
    tolerance: float,
    require_exact_checksum: bool = True,
    require_exact_records: bool = True,
) -> List[Mapping[str, Any]]:
    rows: List[Mapping[str, Any]] = []
    for method in control_runs:
        control = control_runs[method]
        candidate = candidate_runs[method]
        for field in ONLINE_CONTINUOUS_RESULT_FIELDS:
            rows.append(
                compare_array_field(
                    variant,
                    method,
                    field,
                    "continuous",
                    control["comparison_fields"][field],
                    candidate["comparison_fields"][field],
                    tolerance,
                    require_exact_checksum,
                )
            )
        for field in ONLINE_DISCRETE_RESULT_FIELDS:
            rows.append(
                compare_array_field(
                    variant,
                    method,
                    field,
                    "discrete",
                    control["comparison_fields"][field],
                    candidate["comparison_fields"][field],
                    tolerance,
                    require_exact_checksum,
                )
            )
        record_result = compare_record_sequences(
            control["records"],
            candidate["records"],
            ONLINE_FIELDS,
            require_exact_records,
        )
        rows.append(
            {
                "variant": str(variant),
                "method": str(method),
                "field": "online_records",
                "field_type": "record_sequence",
                "shape_control": _shape_text((record_result["control_row_count"],)),
                "shape_variant": _shape_text((record_result["variant_row_count"],)),
                "dtype_control": "record",
                "dtype_variant": "record",
                "max_abs_difference": 0.0 if record_result["records_equal"] else float("inf"),
                "exact_array_equal": bool(record_result["records_equal"]),
                "control_sha256": record_result["control_sha256"],
                "variant_sha256": record_result["variant_sha256"],
                "finite_control": True,
                "finite_variant": True,
                "pass": bool(record_result["pass"]),
            }
        )
    return rows


def canonical_record_sha256(
    records: Sequence[Mapping[str, Any]],
    fields: Sequence[str],
) -> str:
    """Hash records with fixed field order and explicit scalar type encodings."""

    digest = hashlib.sha256()
    for record in records:
        digest.update(b"record\0")
        for field in fields:
            digest.update(field.encode("utf-8"))
            digest.update(b"\0")
            if field not in record:
                digest.update(b"missing\0")
            else:
                digest.update(_canonical_scalar(record[field]))
                digest.update(b"\0")
        for field in sorted(set(record) - set(fields)):
            digest.update(b"extra\0")
            digest.update(field.encode("utf-8"))
            digest.update(b"\0")
            digest.update(_canonical_scalar(record[field]))
            digest.update(b"\0")
    return digest.hexdigest()


def compare_record_sequences(
    control: Sequence[Mapping[str, Any]],
    candidate: Sequence[Mapping[str, Any]],
    fields: Sequence[str],
    require_exact_checksum: bool = True,
) -> Mapping[str, Any]:
    same_length = len(control) == len(candidate)
    schemas_equal = bool(
        same_length
        and all(
            set(first) == set(fields) and set(second) == set(fields)
            for first, second in zip(control, candidate)
        )
    )
    frame_keys_equal = bool(
        same_length
        and all(
            tuple(first.get(name) for name in FRAME_KEY_FIELDS)
            == tuple(second.get(name) for name in FRAME_KEY_FIELDS)
            for first, second in zip(control, candidate)
        )
    )
    records_equal = bool(
        schemas_equal
        and all(
            all(_scalar_values_equal(first[name], second[name]) for name in fields)
            for first, second in zip(control, candidate)
        )
    )
    first_hash = canonical_record_sha256(control, fields)
    second_hash = canonical_record_sha256(candidate, fields)
    checksum_equal = first_hash == second_hash
    return {
        "control_row_count": len(control),
        "variant_row_count": len(candidate),
        "schemas_equal": schemas_equal,
        "frame_keys_equal": frame_keys_equal,
        "records_equal": records_equal,
        "control_sha256": first_hash,
        "variant_sha256": second_hash,
        "pass": bool(
            same_length
            and schemas_equal
            and frame_keys_equal
            and records_equal
            and (not require_exact_checksum or checksum_equal)
        ),
    }


def compare_window_runs(
    variant: str,
    method: str,
    control: Sequence[Mapping[str, Any]],
    candidate: Sequence[Mapping[str, Any]],
    require_exact_checksum: bool = True,
) -> Mapping[str, Any]:
    comparison = compare_record_sequences(
        control,
        candidate,
        WINDOW_FIELDS,
        require_exact_checksum,
    )
    return {
        "variant": str(variant),
        "method": str(method),
        "control_row_count": comparison["control_row_count"],
        "variant_row_count": comparison["variant_row_count"],
        "frame_keys_equal": comparison["frame_keys_equal"],
        "records_equal": comparison["records_equal"],
        "control_sha256": comparison["control_sha256"],
        "variant_sha256": comparison["variant_sha256"],
        "pass": comparison["pass"],
    }


def audit_static_dependencies(
    root: Path,
    source_overrides: Optional[Mapping[str, str]] = None,
    online_schema_fields: Optional[Sequence[str]] = None,
    window_schema_fields: Optional[Sequence[str]] = None,
) -> Mapping[str, Any]:
    """Audit online imports, selected API signatures, and online schemas via AST."""

    root = Path(root).resolve()
    overrides = {} if source_overrides is None else dict(source_overrides)
    parse_failures: List[Mapping[str, str]] = []
    forbidden_imports: List[Mapping[str, str]] = []
    forbidden_parameters: List[Mapping[str, str]] = []
    found_targets = set()
    expected_targets = {
        f"{path}:{name}"
        for path, names in _STATIC_API_TARGETS.items()
        for name in names
    }
    for relative in STATIC_AUDIT_FILES:
        try:
            source = overrides.get(relative, (root / relative).read_text(encoding="utf-8"))
            tree = ast.parse(source, filename=relative)
        except (OSError, SyntaxError, UnicodeError) as error:
            parse_failures.append({"file": relative, "error": str(error)})
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""] + [alias.name for alias in node.names]
            else:
                continue
            for imported in names:
                if any(marker in imported for marker in _FORBIDDEN_IMPORT_MARKERS):
                    forbidden_imports.append(
                        {"file": relative, "line": int(node.lineno), "import": imported}
                    )
        target_names = _qualified_function_arguments(tree)
        for target in _STATIC_API_TARGETS.get(relative, set()):
            if target not in target_names:
                continue
            found_targets.add(f"{relative}:{target}")
            for parameter in target_names[target]:
                if parameter in _FORBIDDEN_SIGNATURE_PARAMETERS:
                    forbidden_parameters.append(
                        {
                            "file": relative,
                            "api": target,
                            "parameter": parameter,
                        }
                    )
    missing_targets = sorted(expected_targets - found_targets)
    schema_fields = list(ONLINE_FIELDS if online_schema_fields is None else online_schema_fields)
    schema_fields.extend(
        WINDOW_FIELDS if window_schema_fields is None else window_schema_fields
    )
    forbidden_schema_fields = sorted(
        {field for field in schema_fields if _schema_field_is_forbidden(field)}
    )
    passed = bool(
        not parse_failures
        and not forbidden_imports
        and not forbidden_parameters
        and not forbidden_schema_fields
        and not missing_targets
    )
    return {
        "audited_files": list(STATIC_AUDIT_FILES),
        "parse_failures": parse_failures,
        "forbidden_imports": forbidden_imports,
        "forbidden_signature_parameters": forbidden_parameters,
        "forbidden_online_schema_fields": forbidden_schema_fields,
        "missing_audited_apis": missing_targets,
        "online_module_gt_dependency_detected": not passed,
        "audit_pass": passed,
    }


def run_filesystem_sandbox_audit(
    root: Path,
    temporary_root: Path,
    online_log_path: Path,
    source_manifest_path: Path,
) -> Mapping[str, Any]:
    """Run Day 9 twice from a clean runner with absent and fake GT files."""

    root = Path(root).resolve()
    temporary_root = Path(temporary_root).resolve()
    if temporary_root.exists():
        shutil.rmtree(temporary_root)
    temporary_root.mkdir(parents=True)
    runner = temporary_root / "day10_runner_repo"
    _create_clean_day9_runner(root, runner)
    no_gt = temporary_root / "day10_no_gt_sandbox"
    fake_gt = temporary_root / "day10_fake_gt_sandbox"
    for sandbox in (no_gt, fake_gt):
        sandbox.mkdir()
        shutil.copy2(online_log_path, sandbox / "frame_diagnostics_online.csv")
        shutil.copy2(source_manifest_path, sandbox / "source_run_manifest.json")
        shutil.copy2(
            root / "configs/stage2_failure/day9_quick.yaml",
            sandbox / "day9_quick.yaml",
        )
    (fake_gt / "frame_diagnostics_gt.csv").write_text(
        "THIS FILE IS INTENTIONALLY INVALID AND MUST NOT BE READ\n",
        encoding="utf-8",
    )
    no_gt_run = _run_day9_sandbox(runner, no_gt, "day10_no_gt_sandbox")
    fake_gt_run = _run_day9_sandbox(runner, fake_gt, "day10_fake_gt_sandbox")
    no_gt_output = (
        no_gt
        / "output/day10_no_gt_sandbox/frame_window_statistics.csv"
    )
    fake_gt_output = (
        fake_gt
        / "output/day10_fake_gt_sandbox/frame_window_statistics.csv"
    )
    no_gt_hash = sha256_file(no_gt_output) if no_gt_output.is_file() else ""
    fake_gt_hash = sha256_file(fake_gt_output) if fake_gt_output.is_file() else ""
    identical = bool(
        no_gt_output.is_file()
        and fake_gt_output.is_file()
        and no_gt_output.read_bytes() == fake_gt_output.read_bytes()
    )
    no_gt_pass = _sandbox_summary_pass(
        no_gt / "output/day10_no_gt_sandbox/day9_quick_summary.json"
    )
    fake_gt_pass = _sandbox_summary_pass(
        fake_gt / "output/day10_fake_gt_sandbox/day9_quick_summary.json"
    )
    sandbox_pass = bool(
        no_gt_run.returncode == 0
        and fake_gt_run.returncode == 0
        and no_gt_pass
        and fake_gt_pass
        and identical
    )
    return {
        "no_gt_subprocess_return_code": int(no_gt_run.returncode),
        "fake_gt_subprocess_return_code": int(fake_gt_run.returncode),
        "no_gt_output_sha256": no_gt_hash,
        "fake_gt_output_sha256": fake_gt_hash,
        "output_byte_identical": identical,
        "gt_file_required": False,
        "fake_gt_file_affected_output": not identical,
        "sandbox_pass": sandbox_pass,
    }


def build_invalid_reset_online_records(
    template: Mapping[str, Any],
) -> List[Mapping[str, Any]]:
    raw_values = [1.0] * 5 + [float("nan")] + [-1.0] * 5
    huber_values = [0.8] * 5 + [float("nan")] + [-0.8] * 5
    records: List[Mapping[str, Any]] = []
    for offset, (raw, huber) in enumerate(zip(raw_values, huber_values), start=1):
        record = dict(template)
        record.update(
            {
                "run_id": "day10_invalid_reset_fixture",
                "sequence_id": "day10_valid_invalid_valid",
                "sweep": "day10_quick",
                "level": "unit",
                "stress": "engineering_reset_fixture",
                "method": "huber_full",
                "frame_index": offset,
                "timestamp": offset * 0.1,
                "weak_innovation_z_raw": raw,
                "weak_innovation_z_huber": huber,
            }
        )
        if offset == 6:
            record["weak_direction_valid"] = False
            record["weak_direction_sign_flipped"] = False
            record["weak_innovation_valid"] = False
            record["primary_direction_stable"] = False
            record["actionable_direction"] = False
            for name in _INVALID_DIRECTION_FLOAT_FIELDS:
                record[name] = float("nan")
        records.append(record)
    return records


def run_invalid_reset_end_to_end(
    root: Path,
    temporary_root: Path,
    template: Mapping[str, Any],
) -> Tuple[Mapping[str, Any], Path]:
    """Write an online CSV, run the complete Day 9 file flow, and audit reset state."""

    temporary_root = Path(temporary_root).resolve()
    if temporary_root.exists():
        shutil.rmtree(temporary_root)
    temporary_root.mkdir(parents=True)
    online_path = temporary_root / "invalid_reset_online.csv"
    source_manifest_path = temporary_root / "source_run_manifest.json"
    records = build_invalid_reset_online_records(template)
    write_online_csv(online_path, records)
    source_manifest = {
        "DAY8_LOGGING_PASS": True,
        "reserved_test_run_performed": False,
        "formal_stage2c_rerun_performed": False,
        "gt_used_by_online_logger": False,
        "online_log_row_count": len(records),
        "online_log_sha256": sha256_file(online_path),
    }
    write_json(source_manifest_path, source_manifest)
    run_stage2_failure_day9(
        root,
        online_path,
        source_manifest_path,
        "day10_invalid_reset_e2e",
        temporary_root / "day9_output",
    )
    output_path = (
        temporary_root
        / "day9_output/day10_invalid_reset_e2e/frame_window_statistics.csv"
    )
    with output_path.open("r", encoding="utf-8", newline="") as handle:
        output_rows = list(csv.DictReader(handle))
    counts = [int(row["window_count"]) for row in output_rows]
    ready = [str(row["window_ready"]).lower() == "true" for row in output_rows]
    expected_counts = [1, 2, 3, 4, 5, 0, 1, 2, 3, 4, 5]
    expected_ready = [False, False, False, False, True, False, False, False, False, False, True]
    invalid = output_rows[5]
    restarted = output_rows[6]
    invalid_floats_are_nan = all(
        math.isnan(float(invalid[f"{prefix}_{suffix}"]))
        for prefix in ("raw", "huber")
        for suffix in SIGNAL_FLOAT_SUFFIXES
    )
    invalid_state_reset = bool(
        str(invalid["stat_input_valid"]).lower() == "false"
        and invalid["stat_reset_reason"] == "invalid_direction"
        and int(invalid["consecutive_valid_count"]) == 0
        and not ready[5]
        and invalid_floats_are_nan
    )
    restarted_from_empty = bool(
        int(restarted["window_count"]) == 1
        and math.isclose(float(restarted["raw_window_mean"]), -1.0, abs_tol=1.0e-12)
        and math.isclose(float(restarted["huber_window_mean"]), -0.8, abs_tol=1.0e-12)
    )
    cusum_reset = bool(
        math.isclose(float(restarted["raw_cusum_positive"]), 0.0, abs_tol=1.0e-12)
        and math.isclose(float(restarted["raw_cusum_negative"]), 0.5, abs_tol=1.0e-12)
    )
    invalid_reset_count = sum(
        int(row["stat_reset_reason"] != "none") for row in output_rows
    )
    expected_counts_match = counts == expected_counts and ready == expected_ready
    passed = bool(
        len(output_rows) == 11
        and invalid_reset_count == 1
        and expected_counts_match
        and invalid_state_reset
        and restarted_from_empty
        and cusum_reset
    )
    audit = {
        "fixture_row_count": len(output_rows),
        "invalid_reset_count": invalid_reset_count,
        "expected_window_counts": expected_counts,
        "observed_window_counts": counts,
        "expected_window_ready": expected_ready,
        "observed_window_ready": ready,
        "invalid_reset_expected_counts_match": expected_counts_match,
        "invalid_frame_state_reset": invalid_state_reset,
        "post_invalid_window_restarted": restarted_from_empty,
        "invalid_reset_cusum_reset_match": cusum_reset,
        "invalid_reset_end_to_end_pass": passed,
    }
    return audit, output_path


def write_fixed_audit_csv(
    path: Path,
    fields: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
) -> None:
    for row in rows:
        if set(row) != set(fields):
            raise ValueError("audit CSV row does not match its fixed schema")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _maximum_array_difference(first: np.ndarray, second: np.ndarray) -> float:
    left = np.asarray(first)
    right = np.asarray(second)
    if left.shape != right.shape:
        return float("inf")
    if not _array_is_finite(left) or not _array_is_finite(right):
        return float("inf")
    if left.size == 0:
        return 0.0
    try:
        return float(np.max(np.abs(left.astype(float) - right.astype(float))))
    except (TypeError, ValueError):
        return float("inf")


def _array_is_finite(value: np.ndarray) -> bool:
    try:
        return bool(np.all(np.isfinite(np.asarray(value))))
    except TypeError:
        return False


def _shape_text(shape: Sequence[int]) -> str:
    return "x".join(str(int(value)) for value in shape) if shape else "scalar"


def _canonical_scalar(value: Any) -> bytes:
    if isinstance(value, (bool, np.bool_)):
        return b"bool:true" if bool(value) else b"bool:false"
    if isinstance(value, (int, np.integer)):
        return f"int:{int(value)}".encode("ascii")
    if isinstance(value, (float, np.floating)):
        number = float(value)
        if math.isnan(number):
            return b"float:nan"
        if math.isinf(number):
            return b"float:+inf" if number > 0 else b"float:-inf"
        return f"float:{number.hex()}".encode("ascii")
    if isinstance(value, str):
        return b"str:" + value.encode("utf-8")
    if value is None:
        return b"none"
    raise TypeError(f"unsupported canonical record value: {type(value).__name__}")


def _scalar_values_equal(first: Any, second: Any) -> bool:
    if isinstance(first, (bool, np.bool_)) or isinstance(second, (bool, np.bool_)):
        return isinstance(first, (bool, np.bool_)) and isinstance(
            second, (bool, np.bool_)
        ) and bool(first) == bool(second)
    if isinstance(first, (float, np.floating)) or isinstance(second, (float, np.floating)):
        try:
            left = float(first)
            right = float(second)
        except (TypeError, ValueError):
            return False
        if math.isnan(left) or math.isnan(right):
            return math.isnan(left) and math.isnan(right)
        return left == right
    return first == second


def _qualified_function_arguments(tree: ast.AST) -> Mapping[str, Sequence[str]]:
    found: Dict[str, Sequence[str]] = {}
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found[node.name] = _argument_names(node)
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    found[f"{node.name}.{child.name}"] = _argument_names(child)
    return found


def _argument_names(node: Any) -> Sequence[str]:
    arguments = list(getattr(node.args, "posonlyargs", []))
    arguments.extend(node.args.args)
    arguments.extend(node.args.kwonlyargs)
    names = [argument.arg for argument in arguments]
    if node.args.vararg is not None:
        names.append(node.args.vararg.arg)
    if node.args.kwarg is not None:
        names.append(node.args.kwarg.arg)
    return names


def _schema_field_is_forbidden(field: str) -> bool:
    tokens = tuple(
        token for token in str(field).lower().replace("-", "_").split("_") if token
    )
    for forbidden in _FORBIDDEN_SCHEMA_TOKEN_SEQUENCES:
        width = len(forbidden)
        if any(tokens[index : index + width] == forbidden for index in range(len(tokens) - width + 1)):
            return True
    return False


def _create_clean_day9_runner(root: Path, runner: Path) -> None:
    shutil.copytree(
        root / "src",
        runner / "src",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )
    (runner / "scripts").mkdir(parents=True)
    (runner / "configs/stage2_failure").mkdir(parents=True)
    shutil.copy2(
        root / "scripts/33_run_stage2_failure_day9.py",
        runner / "scripts/33_run_stage2_failure_day9.py",
    )
    shutil.copy2(
        root / "configs/stage2_failure/day9_quick.yaml",
        runner / "configs/stage2_failure/day9_quick.yaml",
    )
    if (root / ".gitignore").is_file():
        shutil.copy2(root / ".gitignore", runner / ".gitignore")
    subprocess.run(["git", "init", "-q"], cwd=runner, check=True)
    subprocess.run(["git", "add", "."], cwd=runner, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Day10 Audit",
            "-c",
            "user.email=day10-audit@example.invalid",
            "commit",
            "-q",
            "-m",
            "day10 clean sandbox runner",
        ],
        cwd=runner,
        check=True,
    )


def _run_day9_sandbox(
    runner: Path,
    sandbox: Path,
    run_id: str,
) -> subprocess.CompletedProcess:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [
            sys.executable,
            "scripts/33_run_stage2_failure_day9.py",
            "--quick",
            "--online-log",
            str(sandbox / "frame_diagnostics_online.csv"),
            "--source-manifest",
            str(sandbox / "source_run_manifest.json"),
            "--run-id",
            str(run_id),
            "--output-root",
            str(sandbox / "output"),
        ],
        cwd=runner,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _sandbox_summary_pass(path: Path) -> bool:
    if not path.is_file():
        return False
    value = json.loads(path.read_text(encoding="utf-8"))
    return value.get("DAY9_WINDOW_STATS_PASS") is True
