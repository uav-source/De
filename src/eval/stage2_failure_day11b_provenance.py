"""Read-only provenance audits for the locked Stage 2 Day 11B v2 replay."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence, Tuple

import numpy as np


CANONICAL_NDARRAY_MAGIC = b"degen-lio-canonical-ndarray-v1\x00"
CANONICAL_SEQUENCE_MAGIC = b"degen-lio-canonical-array-sequence-v1\x00"
ALLOWED_METHODS = ("huber_full", "huber_projected_gain")

STRATEGY_CHAIN_AUDIT_FIELDS = (
    "case_id", "plan_method", "case_manifest_method", "trajectory_metrics_strategy",
    "logging_disabled_strategy", "logging_enabled_strategy",
    "online_applied_strategy_unique", "allowed_method", "all_equal", "pass",
)
AXIAL_SUPPORT_AUDIT_FIELDS = (
    "case_id", "frame_index", "stress", "contaminated_measurement_count",
    "axial_support_measurement_count", "contaminated_axial_support_count",
    "contaminated_non_axial_support_count", "axial_support_mask_checksum",
    "contamination_mask_checksum", "axial_only_frame_pass",
)
BASE_OBSERVATION_PAIRING_AUDIT_FIELDS = (
    "group_type", "sweep", "level", "stress", "geometry_seed", "sensor_seed",
    "process_seed", "method", "checksum_field", "member_count", "checksum_match", "pass",
)
V1_V2_EQUIVALENCE_AUDIT_FIELDS = (
    "source", "case_id", "field", "field_type", "comparison_count",
    "key_mismatch_count", "max_numeric_difference", "pass",
)
V1_V2_NON_SCIENTIFIC_CSV_FIELDS = frozenset({"run_id"})


def canonical_ndarray_sha256(array: np.ndarray) -> str:
    """Hash dtype, rank, shape, and C-order bytes using a versioned encoding."""

    value = np.asarray(array)
    if value.dtype.hasobject:
        raise TypeError("object dtype is not supported by the canonical ndarray checksum")
    contiguous = np.ascontiguousarray(value)
    dtype_bytes = contiguous.dtype.str.encode("utf-8")
    digest = hashlib.sha256()
    digest.update(CANONICAL_NDARRAY_MAGIC)
    digest.update(struct.pack(">Q", len(dtype_bytes)))
    digest.update(dtype_bytes)
    digest.update(struct.pack(">Q", contiguous.ndim))
    for dimension in contiguous.shape:
        digest.update(struct.pack(">q", int(dimension)))
    digest.update(contiguous.tobytes(order="C"))
    return digest.hexdigest()


def canonical_array_sequence_sha256(arrays: Sequence[np.ndarray]) -> str:
    """Hash an ordered sequence of arrays without losing frame boundaries."""

    values = list(arrays)
    digest = hashlib.sha256()
    digest.update(CANONICAL_SEQUENCE_MAGIC)
    digest.update(struct.pack(">Q", len(values)))
    for value in values:
        digest.update(bytes.fromhex(canonical_ndarray_sha256(np.asarray(value))))
    return digest.hexdigest()


def base_observation_provenance(observations: Mapping[str, Any]) -> Mapping[str, Any]:
    """Compute separate checksums from the unstressed trial-builder observations."""

    fields = {
        "points_lidar": ("points_lidar_base_checksum", "points_lidar_frame_count"),
        "normals_world": ("normals_world_base_checksum", "normals_world_frame_count"),
        "R_diag_list": ("R_diag_list_checksum", "R_diag_frame_count"),
        "plane_points_world": (
            "plane_points_world_base_checksum", "plane_points_world_frame_count"
        ),
    }
    output: Dict[str, Any] = {}
    counts = []
    for source, (target, count_field) in fields.items():
        array = np.asarray(observations[source])
        if array.ndim == 0:
            raise ValueError(f"base observation field has no frame axis: {source}")
        output[target] = canonical_array_sequence_sha256([array[index] for index in range(array.shape[0])])
        output[count_field] = int(array.shape[0])
        counts.append(int(array.shape[0]))
    if len(set(counts)) != 1 or counts[0] <= 0:
        raise ValueError("base observation frame counts differ")
    return output


def stressed_plane_checksum(observations: Mapping[str, Any]) -> str:
    planes = np.asarray(observations["plane_points_world"])
    return canonical_array_sequence_sha256([planes[index] for index in range(planes.shape[0])])


def build_strategy_chain_audit(
    case_id: str,
    plan_method: str,
    case_manifest_method: str,
    trajectory_metrics: Mapping[str, Any],
    disabled_result: Mapping[str, Any],
    enabled_result: Mapping[str, Any],
    online_records: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any]:
    """Verify the method identity from the plan through both runtime results."""

    online_values = sorted({str(row.get("applied_strategy", "")) for row in online_records})
    online_unique = online_values[0] if len(online_values) == 1 else "|".join(online_values)
    values = (
        str(plan_method), str(case_manifest_method), str(trajectory_metrics.get("strategy", "")),
        str(disabled_result.get("strategy", "")), str(enabled_result.get("strategy", "")),
        online_unique,
    )
    allowed = str(plan_method) in ALLOWED_METHODS and "oracle" not in str(plan_method).lower()
    all_equal = len(set(values)) == 1
    return {
        "case_id": str(case_id),
        "plan_method": values[0],
        "case_manifest_method": values[1],
        "trajectory_metrics_strategy": values[2],
        "logging_disabled_strategy": values[3],
        "logging_enabled_strategy": values[4],
        "online_applied_strategy_unique": values[5],
        "allowed_method": bool(allowed),
        "all_equal": bool(all_equal),
        "pass": bool(allowed and all_equal and len(online_values) == 1),
    }


def audit_axial_support(
    case_id: str,
    stress: str,
    online_records: Sequence[Mapping[str, Any]],
    observations: Mapping[str, Any],
) -> Tuple[Sequence[Mapping[str, Any]], Mapping[str, Any]]:
    """Derive axial-only evidence from the real masks, never from the stress name alone."""

    axial_all = np.asarray(observations["is_axial_support"], dtype=bool)
    contamination_all = np.asarray(observations["contamination_mask"], dtype=bool)
    if axial_all.shape != contamination_all.shape or axial_all.ndim != 2:
        raise ValueError("axial-support and contamination masks must be matching frame matrices")
    rows = []
    for online in online_records:
        frame = int(online["frame_index"])
        axial = axial_all[frame]
        contaminated = contamination_all[frame]
        contaminated_count = int(np.count_nonzero(contaminated))
        axial_count = int(np.count_nonzero(axial))
        contaminated_axial = int(np.count_nonzero(contaminated & axial))
        contaminated_non_axial = int(np.count_nonzero(contaminated & ~axial))
        logical_pass = bool(np.all(np.logical_or(~contaminated, axial)))
        if stress == "clean":
            frame_pass = logical_pass and contaminated_count == 0
        elif stress == "coherent_subhuber_slip":
            frame_pass = logical_pass and contaminated_axial == contaminated_count
        else:
            frame_pass = False
        rows.append({
            "case_id": str(case_id), "frame_index": frame, "stress": str(stress),
            "contaminated_measurement_count": contaminated_count,
            "axial_support_measurement_count": axial_count,
            "contaminated_axial_support_count": contaminated_axial,
            "contaminated_non_axial_support_count": contaminated_non_axial,
            "axial_support_mask_checksum": canonical_ndarray_sha256(axial),
            "contamination_mask_checksum": canonical_ndarray_sha256(contaminated),
            "axial_only_frame_pass": bool(frame_pass),
        })
    total = int(np.count_nonzero(contamination_all))
    axial_total = int(np.count_nonzero(contamination_all & axial_all))
    non_axial_total = int(np.count_nonzero(contamination_all & ~axial_all))
    if stress == "clean":
        case_pass = total == axial_total == non_axial_total == 0
    elif stress == "coherent_subhuber_slip":
        case_pass = total > 0 and axial_total == total and non_axial_total == 0
    else:
        case_pass = False
    case_pass = bool(case_pass and rows and all(bool(row["axial_only_frame_pass"]) for row in rows))
    summary = {
        "case_id": str(case_id), "stress": str(stress),
        "frame_comparison_count": len(rows),
        "contaminated_measurement_count": total,
        "contaminated_axial_support_count": axial_total,
        "contaminated_non_axial_support_count": non_axial_total,
        "axial_support_mask_list_checksum": canonical_array_sequence_sha256(
            [axial_all[index] for index in range(axial_all.shape[0])]
        ),
        "contamination_mask_list_checksum": canonical_array_sequence_sha256(
            [contamination_all[index] for index in range(contamination_all.shape[0])]
        ),
        "axial_only": case_pass,
        "pass": case_pass,
    }
    return rows, summary


def build_base_observation_pairing_audit(
    case_manifests: Sequence[Mapping[str, Any]],
) -> Tuple[Sequence[Mapping[str, Any]], Mapping[str, int]]:
    """Audit method and clean/stress pairs using independently stored checksums."""

    method_fields = (
        "points_lidar_base_checksum", "normals_world_base_checksum", "R_diag_list_checksum",
        "plane_points_world_base_checksum", "plane_points_world_stressed_checksum",
        "initial_state_checksum", "initial_covariance_checksum", "process_noise_checksum",
        "scene_checksum", "stress_checksum",
    )
    stress_fields = (
        "points_lidar_base_checksum", "normals_world_base_checksum", "R_diag_list_checksum",
        "plane_points_world_base_checksum", "initial_state_checksum",
        "initial_covariance_checksum", "process_noise_checksum", "scene_checksum",
    )
    rows = []
    method_groups: Dict[tuple, list] = {}
    stress_groups: Dict[tuple, list] = {}
    for item in case_manifests:
        method_key = tuple(item[field] for field in (
            "sweep", "level", "stress", "geometry_seed", "sensor_seed", "process_seed"
        ))
        method_groups.setdefault(method_key, []).append(item)
        stress_key = tuple(item[field] for field in (
            "sweep", "level", "geometry_seed", "sensor_seed", "process_seed", "method"
        ))
        stress_groups.setdefault(stress_key, []).append(item)
    for key, values in sorted(method_groups.items()):
        members_valid = {str(item["method"]) for item in values} == set(ALLOWED_METHODS)
        for field in method_fields:
            match = len({str(item.get(field, "")) for item in values}) == 1
            rows.append(_pairing_row("method_pair", key, "", field, values, match, members_valid))
    for key, values in sorted(stress_groups.items()):
        members_valid = {str(item["stress"]) for item in values} == {"clean", "coherent_subhuber_slip"}
        display_key = key[:2] + ("clean|coherent_subhuber_slip",) + key[2:5]
        for field in stress_fields:
            match = len({str(item.get(field, "")) for item in values}) == 1
            rows.append(_pairing_row(
                "clean_stress_pair", display_key, str(key[5]), field, values, match, members_valid
            ))
    counts = {}
    for prefix, group_type in (("method_pair", "method_pair"), ("clean_stress", "clean_stress_pair")):
        for name, field in (
            ("points_lidar", "points_lidar_base_checksum"),
            ("normals_world", "normals_world_base_checksum"),
            ("R_diag", "R_diag_list_checksum"),
        ):
            counts[f"{name}_{prefix}_mismatch_count"] = sum(
                int(not bool(row["pass"]))
                for row in rows
                if row["group_type"] == group_type and row["checksum_field"] == field
            )
    return rows, counts


def compare_v1_v2_scientific_outputs(
    v1_run: Path, v2_run: Path, tolerance: float = 1.0e-12
) -> Tuple[Sequence[Mapping[str, Any]], Mapping[str, Any]]:
    """Compare every v1 scientific value with its v2 counterpart."""

    v1_run = Path(v1_run)
    v2_run = Path(v2_run)
    v1_cases = {path.name: path for path in (v1_run / "cases").iterdir() if path.is_dir()}
    v2_cases = {path.name: path for path in (v2_run / "cases").iterdir() if path.is_dir()}
    case_key_mismatches = len(set(v1_cases) ^ set(v2_cases))
    rows = []
    for case_id in sorted(set(v1_cases) & set(v2_cases)):
        for filename, keys in (
            ("frame_diagnostics_online.csv", ("frame_index",)),
            ("frame_diagnostics_gt.csv", ("frame_index",)),
            ("frame_window_statistics.csv", ("frame_index",)),
        ):
            rows.extend(_compare_csv(
                v1_cases[case_id] / filename, v2_cases[case_id] / filename,
                f"cases/{filename}", case_id, keys, tolerance,
            ))
        rows.extend(_compare_json_scalars(
            v1_cases[case_id] / "trajectory_metrics.json",
            v2_cases[case_id] / "trajectory_metrics.json",
            "cases/trajectory_metrics.json", case_id, tolerance,
        ))
    rows.extend(_compare_csv(
        v1_run / "replay_case_summary.csv", v2_run / "replay_case_summary.csv",
        "replay_case_summary.csv", "", ("case_id",), tolerance,
    ))
    rows.extend(_compare_csv(
        v1_run / "replay_frame_diagnostics_merged.csv",
        v2_run / "replay_frame_diagnostics_merged.csv",
        "replay_frame_diagnostics_merged.csv", "", ("case_id", "frame_index"), tolerance,
    ))
    key_mismatches = case_key_mismatches + sum(int(row["key_mismatch_count"]) for row in rows)
    failures = sum(int(not bool(row["pass"])) for row in rows)
    numeric = [float(row["max_numeric_difference"]) for row in rows]
    maximum = max(numeric, default=0.0)
    summary = {
        "v1_v2_case_comparison_count": len(set(v1_cases) & set(v2_cases)),
        "v1_v2_field_comparison_count": sum(int(row["comparison_count"]) for row in rows),
        "v1_v2_failure_count": failures + int(case_key_mismatches > 0),
        "v1_v2_max_numeric_difference": maximum,
        "v1_v2_key_mismatch_count": key_mismatches,
    }
    return rows, summary


def result_tree_manifest(root: Path, run_dir: Path) -> bytes:
    """Return sha256sum-compatible, path-stable bytes for a result tree."""

    root = Path(root).resolve()
    run_dir = Path(run_dir).resolve()
    lines = []
    for path in sorted(item for item in run_dir.rglob("*") if item.is_file()):
        relative = path.relative_to(root)
        lines.append(f"{_sha256_file(path)}  {relative}\n")
    return "".join(lines).encode("utf-8")


def write_v1_immutable_after_evidence(
    root: Path,
    v1_run: Path,
    before_manifest_path: Path,
    after_manifest_path: Path,
    after_digest_path: Path,
) -> Mapping[str, Any]:
    before = Path(before_manifest_path).read_bytes()
    after = result_tree_manifest(root, v1_run)
    Path(after_manifest_path).write_bytes(after)
    digest = hashlib.sha256(after).hexdigest()
    Path(after_digest_path).write_text(f"{digest}  {Path(after_manifest_path)}\n", encoding="utf-8")
    return {
        "v1_result_tree_digest_before": hashlib.sha256(before).hexdigest(),
        "v1_result_tree_digest_after": digest,
        "day11b_v1_result_tree_unchanged": before == after,
    }


def _pairing_row(
    group_type: str, key: tuple, method: str, field: str,
    values: Sequence[Mapping[str, Any]], match: bool, members_valid: bool,
) -> Mapping[str, Any]:
    return {
        "group_type": group_type, "sweep": key[0], "level": key[1], "stress": key[2],
        "geometry_seed": key[3], "sensor_seed": key[4], "process_seed": key[5],
        "method": method, "checksum_field": field, "member_count": len(values),
        "checksum_match": bool(match), "pass": bool(match and members_valid and len(values) == 2),
    }


def _compare_csv(
    first_path: Path, second_path: Path, source: str, case_id: str,
    key_fields: Sequence[str], tolerance: float,
) -> Sequence[Mapping[str, Any]]:
    first_fields, first_rows = _read_csv(first_path)
    second_fields, second_rows = _read_csv(second_path)
    missing_fields = [field for field in first_fields if field not in second_fields]
    if missing_fields:
        return [{
            "source": source, "case_id": case_id, "field": field,
            "field_type": "missing", "comparison_count": 0,
            "key_mismatch_count": 0, "max_numeric_difference": float("inf"), "pass": False,
        } for field in missing_fields]
    first_index, first_duplicates = _index_csv(first_rows, key_fields)
    second_index, second_duplicates = _index_csv(second_rows, key_fields)
    key_mismatches = len(set(first_index) ^ set(second_index)) + first_duplicates + second_duplicates
    common_keys = sorted(set(first_index) & set(second_index))
    output = []
    for field in first_fields:
        if field in V1_V2_NON_SCIENTIFIC_CSV_FIELDS:
            continue
        comparisons = [_compare_scalar(first_index[key][field], second_index[key][field]) for key in common_keys]
        maximum = max((value[1] for value in comparisons), default=0.0)
        passed = key_mismatches == 0 and all(value[0] for value in comparisons)
        field_type = "numeric" if comparisons and all(value[2] for value in comparisons) else "discrete"
        output.append({
            "source": source, "case_id": case_id, "field": field, "field_type": field_type,
            "comparison_count": len(comparisons), "key_mismatch_count": key_mismatches,
            "max_numeric_difference": maximum, "pass": bool(passed),
        })
    return output


def _compare_json_scalars(
    first_path: Path, second_path: Path, source: str, case_id: str, tolerance: float,
) -> Sequence[Mapping[str, Any]]:
    first = json.loads(Path(first_path).read_text(encoding="utf-8"))
    second = json.loads(Path(second_path).read_text(encoding="utf-8"))
    output = []
    for field, first_value in first.items():
        if field not in second:
            passed, difference, numeric = False, float("inf"), False
        else:
            passed, difference, numeric = _compare_scalar(first_value, second[field])
        if numeric and math.isfinite(difference):
            passed = bool(passed and difference <= tolerance)
        output.append({
            "source": source, "case_id": case_id, "field": field,
            "field_type": "numeric" if numeric else "discrete", "comparison_count": 1,
            "key_mismatch_count": 0, "max_numeric_difference": difference, "pass": passed,
        })
    return output


def _read_csv(path: Path) -> Tuple[Sequence[str], Sequence[Mapping[str, str]]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return tuple(reader.fieldnames or ()), list(reader)


def _index_csv(
    rows: Sequence[Mapping[str, str]], key_fields: Sequence[str]
) -> Tuple[Mapping[tuple, Mapping[str, str]], int]:
    output = {}
    duplicates = 0
    for index, row in enumerate(rows):
        key = tuple(row[field] for field in key_fields) if key_fields else (str(index),)
        if key in output:
            duplicates += 1
        output[key] = row
    return output, duplicates


def _compare_scalar(first: Any, second: Any) -> Tuple[bool, float, bool]:
    left_numeric, left = _numeric_value(first)
    right_numeric, right = _numeric_value(second)
    if left_numeric and right_numeric:
        if math.isnan(left) and math.isnan(right):
            return True, 0.0, True
        if math.isnan(left) or math.isnan(right) or math.isinf(left) or math.isinf(right):
            return False, float("inf"), True
        difference = abs(left - right)
        return difference <= 1.0e-12, difference, True
    if left_numeric != right_numeric:
        return False, float("inf"), False
    return first == second, 0.0 if first == second else float("inf"), False


def _numeric_value(value: Any) -> Tuple[bool, float]:
    if isinstance(value, (bool, np.bool_)):
        return False, 0.0
    if isinstance(value, str) and value.strip().lower() in {"true", "false", ""}:
        return False, 0.0
    try:
        return True, float(value)
    except (TypeError, ValueError):
        return False, 0.0


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
