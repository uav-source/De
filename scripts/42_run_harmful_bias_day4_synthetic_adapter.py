#!/usr/bin/env python3
"""Run the deterministic Day 4 observation-to-detector integration audit."""

from __future__ import annotations

import argparse
import copy
import csv
import json
import math
import struct
import sys
from pathlib import Path
from typing import Any, Iterable

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from degen_detector.odi_tracker import compute_metrics_for_frame  # noqa: E402
from fastlio2_adapter.detector_adapter import (  # noqa: E402
    evaluate_readonly_observation,
    load_production_detector_contract,
)
from fastlio2_adapter.detector_output_schema import (  # noqa: E402
    canonical_sha256,
    validate_readonly_detector_output,
)
from fastlio2_adapter.readonly_observation_schema import (  # noqa: E402
    validate_first_valid_observation_record,
)


FIXTURE_IDS = (
    "well_conditioned",
    "weak_x",
    "weak_rotated",
)
FAST_DAY3_COMMIT = "f19b4c42a77dc11793c912d67b9e56dcafa279dc"
_FNV_OFFSET = 14695981039346656037
_FNV_PRIME = 1099511628211
_UINT64_MASK = (1 << 64) - 1


def build_synthetic_observations() -> dict[str, dict[str, Any]]:
    """Create three fixed, non-random, schema-valid observation records."""

    root_two = math.sqrt(2.0)
    weak_scale = 1.0e-3
    strong_scale = math.sqrt(1.0 - weak_scale * weak_scale)
    rotated_weak = np.asarray([1.0 / root_two, 1.0 / root_two, 0.0])
    rotated_strong = np.asarray([1.0 / root_two, -1.0 / root_two, 0.0])

    normal_sets = {
        "well_conditioned": [
            [1.0, 0.0, 0.0],
            [-1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, -1.0, 0.0],
            [0.0, 0.0, 1.0],
            [0.0, 0.0, -1.0],
        ],
        "weak_x": [
            [weak_scale, strong_scale, 0.0],
            [weak_scale, -strong_scale, 0.0],
            [weak_scale, 0.0, strong_scale],
            [weak_scale, 0.0, -strong_scale],
        ],
        "weak_rotated": [
            (weak_scale * rotated_weak + strong_scale * rotated_strong).tolist(),
            (weak_scale * rotated_weak - strong_scale * rotated_strong).tolist(),
            (weak_scale * rotated_weak + np.asarray([0.0, 0.0, strong_scale])).tolist(),
            (weak_scale * rotated_weak - np.asarray([0.0, 0.0, strong_scale])).tolist(),
        ],
    }
    return {
        fixture_id: _build_record(fixture_id, index + 1, normals)
        for index, (fixture_id, normals) in enumerate(normal_sets.items())
    }


def run_pipeline(output_dir: Path, *, overwrite: bool = False) -> dict[str, Any]:
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()) and not overwrite:
        raise FileExistsError(
            f"output directory is not empty; pass --overwrite: {output_dir}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    if overwrite:
        for path in output_dir.iterdir():
            if path.is_file():
                path.unlink()

    fixtures = build_synthetic_observations()
    rows: list[dict[str, Any]] = []
    for fixture_id in FIXTURE_IDS:
        record = fixtures[fixture_id]
        validate_first_valid_observation_record(record)
        before = copy.deepcopy(record)
        input_sha_before = canonical_sha256(record)

        outputs = [evaluate_readonly_observation(record) for _ in range(3)]
        input_sha_after = canonical_sha256(record)
        input_immutable = input_sha_before == input_sha_after and record == before
        output_shas = [canonical_sha256(output) for output in outputs]
        deterministic = output_shas[0] == output_shas[1] == output_shas[2]
        output = outputs[0]
        validate_readonly_detector_output(output)

        direct = _direct_production_result(record)
        equivalence_error = _maximum_equivalence_error(output, direct)
        equivalence_pass = equivalence_error <= 1.0e-12

        _write_json(
            output_dir / f"synthetic_{fixture_id}_observation.json", record
        )
        _write_json(
            output_dir / f"synthetic_{fixture_id}_detector_output.json", output
        )
        rows.append(
            {
                "fixture_id": fixture_id,
                "valid_correspondence_count": record[
                    "valid_correspondence_count"
                ],
                "adapter_valid": output["valid"],
                "direct_equivalence_max_abs_error": equivalence_error,
                "direct_equivalence_pass": equivalence_pass,
                "input_immutability_pass": input_immutable,
                "determinism_pass": deterministic,
                "schema_validation_pass": True,
                "input_observation_checksum": input_sha_before,
                "detector_output_checksum": output["detector_output_checksum"],
                "canonical_output_sha256_1": output_shas[0],
                "canonical_output_sha256_2": output_shas[1],
                "canonical_output_sha256_3": output_shas[2],
            }
        )

    _write_results_csv(output_dir / "synthetic_adapter_results.csv", rows)
    summary = {
        "schema_version": "harmful-bias-multihyp-day4-synthetic-summary-v1",
        "synthetic_only": True,
        "real_data_used": False,
        "rosbag_run": False,
        "fixture_count": len(rows),
        "fixture_ids": list(FIXTURE_IDS),
        "adapter_success_count": sum(bool(row["adapter_valid"]) for row in rows),
        "direct_equivalence_pass_count": sum(
            bool(row["direct_equivalence_pass"]) for row in rows
        ),
        "input_immutability_pass_count": sum(
            bool(row["input_immutability_pass"]) for row in rows
        ),
        "determinism_pass_count": sum(
            bool(row["determinism_pass"]) for row in rows
        ),
        "schema_validation_pass_count": sum(
            bool(row["schema_validation_pass"]) for row in rows
        ),
        "maximum_direct_equivalence_abs_error": max(
            float(row["direct_equivalence_max_abs_error"]) for row in rows
        ),
    }
    _write_json(output_dir / "synthetic_adapter_summary.json", summary)
    _write_sha256sums(output_dir)
    return summary


def _build_record(
    fixture_id: str,
    scan_index: int,
    normals: list[list[float]],
) -> dict[str, Any]:
    rows: list[list[float]] = []
    planes: list[list[float]] = []
    for normal_index, normal_values in enumerate(normals):
        normal = np.asarray(normal_values, dtype=np.float64)
        normal = normal / float(np.sqrt(np.sum(normal * normal)))
        for rotation_axis in range(3):
            rotation = np.zeros(3, dtype=np.float64)
            rotation[rotation_axis] = 1.0
            rows.append(np.concatenate([rotation, normal]).tolist())
            rows.append(np.concatenate([-rotation, normal]).tolist())
            plane = normal.tolist() + [-0.1 * float(normal_index + 1)]
            planes.extend([plane, plane])

    row_count = len(rows)
    pd2 = [0.001 * float((index % 5) - 2) for index in range(row_count)]
    innovation = [-value for value in pd2]
    accepted = [1000 * scan_index + index for index in range(row_count)]
    proxies = [
        _fnv_bytes(f"{fixture_id}:{scan_index}:{index}".encode("utf-8"))
        for index in range(row_count)
    ]
    neighbors = [
        [
            [
                float(index) * 0.01 + float(offset) * 0.001,
                float((index + offset) % 7) * 0.02,
                float(offset - 2) * 0.01,
            ]
            for offset in range(5)
        ]
        for index in range(row_count)
    ]
    covariance = [
        [0.01 * float(row + 1) if row == column else 0.0 for column in range(6)]
        for row in range(6)
    ]
    native_rows = [row[3:6] + row[0:3] + [0.0] * 6 for row in rows]
    record = {
        "record_type": "first_valid_observation",
        "schema_version": "fastlio2-readonly-observation-v1",
        "synthetic_only": True,
        "scan_index": scan_index,
        "timestamp_begin": 1000.0 + float(scan_index),
        "timestamp_end": 1000.1 + float(scan_index),
        "timestamp_unit": "seconds",
        "measurement_call_index": 1,
        "record_version": "readonly_observation_v1",
        "prior_position_world": [0.0, 0.0, 0.0],
        "prior_position_frame": "world",
        "prior_position_unit": "meters",
        "prior_orientation_world_from_imu_xyzw": [0.0, 0.0, 0.0, 1.0],
        "prior_orientation_from_frame": "imu",
        "prior_orientation_to_frame": "world",
        "prior_orientation_representation": "quaternion_xyzw",
        "prior_covariance_detector_order": covariance,
        "prior_covariance_native_dimension": 23,
        "prior_covariance_order": "delta_theta_xyz_then_delta_position_xyz",
        "prior_covariance_unit_convention": "rotation_radians_then_translation_meters",
        "detector_pose_jacobian_rows": rows,
        "detector_pose_jacobian_column_order": "delta_theta_xyz_then_delta_position_xyz",
        "detector_pose_jacobian_unit_convention": "meters_per_rotation_radian_then_meters_per_translation_meter",
        "signed_geometric_residual_pd2": pd2,
        "formal_filter_innovation_h": innovation,
        "residual_unit": "meters",
        "measurement_weight_representation": "CONSTANT_SCALAR_VARIANCE",
        "measurement_variance_scalar_m2": 0.001,
        "measurement_variance_applies_to_all_rows": True,
        "accepted_source_indices": accepted,
        "correspondence_proxy_ids": proxies,
        "plane_parameters_world": planes,
        "plane_parameter_convention": "normalized_normal_xyz_and_offset_meters",
        "ordered_neighbor_coordinates_world": neighbors,
        "neighbor_coordinate_frame": "world",
        "neighbor_coordinate_unit": "meters",
        "valid_correspondence_count": row_count,
        "native_jacobian_column_count": 12,
        "detector_jacobian_column_count": 6,
        "checksum_algorithm": "FNV1A64_EXACT_BYTES_V1",
        "formal_native_jacobian_checksum": _checksum_matrix(native_rows),
        "detector_jacobian_checksum": _checksum_detector_rows(rows),
        "formal_innovation_checksum": _checksum_vector(innovation, "d"),
        "geometric_residual_checksum": _checksum_vector(pd2, "d"),
        "accepted_index_checksum": _checksum_vector(accepted, "Q"),
        "correspondence_proxy_checksum": _checksum_vector(proxies, "Q"),
        "prior_covariance_checksum": _checksum_covariance(covariance),
    }
    return record


def _direct_production_result(record: dict[str, Any]) -> dict[str, Any]:
    jacobian = np.asarray(record["detector_pose_jacobian_rows"], dtype=np.float64)
    variance = np.full(
        jacobian.shape[0],
        float(record["measurement_variance_scalar_m2"]),
        dtype=np.float64,
    )
    config, _ = load_production_detector_contract()
    metrics = compute_metrics_for_frame(jacobian, variance, config)
    return {
        "odi_trans": float(metrics["ODI_trans"]),
        "ais_trans": float(metrics["AIS_trans_normalized"]),
        "lambda_min_trans": float(metrics["lambda_min_trans_normalized"]),
        "condition_number_trans": float(metrics["condition_number_trans"]),
        "translation_eigenvalues_ascending": sorted(
            [
                float(metrics["trans_eig_1"]),
                float(metrics["trans_eig_2"]),
                float(metrics["trans_eig_3"]),
            ]
        ),
        "primary_weak_direction": [
            float(metrics["primary_weak_dir_x"]),
            float(metrics["primary_weak_dir_y"]),
            float(metrics["primary_weak_dir_z"]),
        ],
        "primary_eigengap_ratio": float(metrics["primary_eigengap_ratio"]),
        "primary_direction_stable": bool(metrics["primary_direction_stable"]),
        "degeneracy_triggered": bool(metrics["degeneracy_triggered"]),
        "actionable_direction": bool(metrics["actionable_direction"]),
    }


def _maximum_equivalence_error(
    adapter_output: dict[str, Any], direct_output: dict[str, Any]
) -> float:
    scalar_names = (
        "odi_trans",
        "ais_trans",
        "lambda_min_trans",
        "condition_number_trans",
        "primary_eigengap_ratio",
    )
    errors = [
        abs(float(adapter_output[name]) - float(direct_output[name]))
        for name in scalar_names
    ]
    for name in (
        "translation_eigenvalues_ascending",
        "primary_weak_direction",
    ):
        errors.extend(
            abs(float(left) - float(right))
            for left, right in zip(adapter_output[name], direct_output[name])
        )
    for name in (
        "primary_direction_stable",
        "degeneracy_triggered",
        "actionable_direction",
    ):
        if adapter_output[name] is not direct_output[name]:
            return float("inf")
    return max(errors, default=0.0)


def _fnv_bytes(data: bytes, checksum: int = _FNV_OFFSET) -> int:
    value = checksum
    for byte in data:
        value = ((value ^ byte) * _FNV_PRIME) & _UINT64_MASK
    return value


def _checksum_vector(values: Iterable[Any], code: str) -> int:
    materialized = list(values)
    checksum = _fnv_bytes(struct.pack("<Q", len(materialized)))
    for value in materialized:
        checksum = _fnv_bytes(struct.pack(f"<{code}", value), checksum)
    return checksum


def _checksum_detector_rows(rows: list[list[float]]) -> int:
    checksum = _fnv_bytes(struct.pack("<Q", len(rows)))
    for row in rows:
        for value in row:
            checksum = _fnv_bytes(struct.pack("<d", value), checksum)
    return checksum


def _checksum_matrix(rows: list[list[float]]) -> int:
    checksum = _fnv_bytes(struct.pack("<Q", len(rows)))
    checksum = _fnv_bytes(struct.pack("<Q", len(rows[0])), checksum)
    for row in rows:
        for value in row:
            checksum = _fnv_bytes(struct.pack("<d", value), checksum)
    return checksum


def _checksum_covariance(rows: list[list[float]]) -> int:
    checksum = _FNV_OFFSET
    for row in rows:
        for value in row:
            checksum = _fnv_bytes(struct.pack("<d", value), checksum)
    return checksum


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _write_results_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_sha256sums(output_dir: Path) -> None:
    lines = []
    for path in sorted(output_dir.iterdir(), key=lambda item: item.name):
        if path.is_file() and path.name != "SHA256SUMS":
            digest = __import__("hashlib").sha256(path.read_bytes()).hexdigest()
            lines.append(f"{digest}  {path.name}")
    (output_dir / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run deterministic Day 4 synthetic adapter integration"
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run_pipeline(args.output_dir, overwrite=args.overwrite)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
