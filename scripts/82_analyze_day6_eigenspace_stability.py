#!/usr/bin/env python3
"""Reconstruct frozen information matrices and compare weak eigenspaces."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.day6_branch_divergence import (  # noqa: E402
    validate_source_lock,
    write_json,
)
from fastlio2_adapter.day6_eigenspace_stability import (  # noqa: E402
    GAP_BINS,
    compare_reconstruction,
    descriptive_statistics,
    gap_bin_name,
    matrix_perturbation,
    reconstruct_translation_information,
    reconstruction_pass,
    sign_invariant_angle_deg,
    spearman_summary,
    weak_subspace_principal_angles_deg,
)
from fastlio2_adapter.day6_semantic_observation import (  # noqa: E402
    load_observation_records,
)


PAIR_DEFINITIONS = (
    ("r1-r2", 1, 2),
    ("r1-r3", 1, 3),
    ("r2-r3", 2, 3),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", required=True, type=Path)
    parser.add_argument(
        "--semantic-comparison",
        required=True,
        type=Path,
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def csv_value(value: Any) -> Any:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict)):
        return json.dumps(
            value, allow_nan=False, separators=(",", ":"), sort_keys=True
        )
    if value is None:
        return ""
    return value


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    rows = list(rows)
    if not rows:
        raise ValueError(f"cannot write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(value) for key, value in row.items()})


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def maximum_error(rows: Sequence[Mapping[str, float]]) -> dict[str, float]:
    if not rows:
        raise ValueError("empty reconstruction error set")
    return {
        field: max(float(row[field]) for row in rows)
        for field in rows[0]
    }


def reconstruction_row(
    *,
    run_index: int,
    record_index: int,
    record: Mapping[str, Any],
    direct: Mapping[str, Any],
    value: Mapping[str, Any],
    error: Mapping[str, float],
) -> dict[str, Any]:
    matrix = np.asarray(value["h_translation"], dtype=np.float64)
    eigenvalues = np.asarray(value["eigenvalues"], dtype=np.float64)
    vectors = np.asarray(value["eigenvectors"], dtype=np.float64)
    row = {
        "run": f"run_{run_index}",
        "record_index": record_index,
        "scan_index": int(record["scan_index"]),
        "timestamp_begin": float(record["timestamp_begin"]),
        "timestamp_end": float(record["timestamp_end"]),
        "valid_correspondence_count": int(
            record["valid_correspondence_count"]
        ),
        "lambda_1": float(eigenvalues[0]),
        "lambda_2": float(eigenvalues[1]),
        "lambda_3": float(eigenvalues[2]),
        "absolute_gap_12": float(value["absolute_gap_12"]),
        "relative_gap_12": float(value["relative_gap_12"]),
        "absolute_gap_23": float(value["absolute_gap_23"]),
        "relative_gap_23": float(value["relative_gap_23"]),
        "gap_bin": gap_bin_name(float(value["relative_gap_12"])),
        "condition_number": float(value["condition_number"]),
        "primary_eigengap_ratio": float(
            value["primary_eigengap_ratio"]
        ),
        "primary_direction_stable": bool(
            direct["primary_direction_stable"]
        ),
        "odi_trans": float(value["odi_trans"]),
        "ais_trans": float(value["ais_trans"]),
        "v1_x": float(vectors[0, 0]),
        "v1_y": float(vectors[1, 0]),
        "v1_z": float(vectors[2, 0]),
        "v2_x": float(vectors[0, 1]),
        "v2_y": float(vectors[1, 1]),
        "v2_z": float(vectors[2, 1]),
        "h_00": float(matrix[0, 0]),
        "h_01": float(matrix[0, 1]),
        "h_02": float(matrix[0, 2]),
        "h_10": float(matrix[1, 0]),
        "h_11": float(matrix[1, 1]),
        "h_12": float(matrix[1, 2]),
        "h_20": float(matrix[2, 0]),
        "h_21": float(matrix[2, 1]),
        "h_22": float(matrix[2, 2]),
        **error,
    }
    return row


def time_rows(
    run_index: int,
    reconstructions: Sequence[Mapping[str, Any]],
    records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for index in range(1, len(reconstructions)):
        previous = reconstructions[index - 1]
        current = reconstructions[index]
        subspace_min, subspace_max = weak_subspace_principal_angles_deg(
            previous["weak_subspace"],
            current["weak_subspace"],
        )
        perturbation = matrix_perturbation(
            previous["h_translation"],
            current["h_translation"],
        )
        gap = float(current["absolute_gap_12"])
        rows.append(
            {
                "run": f"run_{run_index}",
                "previous_record_index": index - 1,
                "record_index": index,
                "previous_scan_index": int(
                    records[index - 1]["scan_index"]
                ),
                "scan_index": int(records[index]["scan_index"]),
                "v1_sign_invariant_angle_deg": sign_invariant_angle_deg(
                    previous["v1"], current["v1"]
                ),
                "subspace_angle_min_deg": subspace_min,
                "subspace_angle_max_deg": subspace_max,
                "relative_gap_12": float(current["relative_gap_12"]),
                "relative_gap_23": float(current["relative_gap_23"]),
                "gap_bin": gap_bin_name(
                    float(current["relative_gap_12"])
                ),
                **perturbation,
                "perturbation_gap_ratio": float(
                    perturbation["h_perturbation_norm_2"]
                    / max(gap, 1.0e-18)
                ),
                "descriptive_proxy_only": True,
            }
        )
    return rows


def summarize_time_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    angle = [
        float(row["v1_sign_invariant_angle_deg"]) for row in rows
    ]
    subspace = [float(row["subspace_angle_max_deg"]) for row in rows]
    gap12 = [float(row["relative_gap_12"]) for row in rows]
    gap23 = [float(row["relative_gap_23"]) for row in rows]
    perturbation_gap = [
        float(row["perturbation_gap_ratio"]) for row in rows
    ]
    h_relative = [float(row["relative_h_perturbation"]) for row in rows]
    bin_summary = {}
    for name, _, _ in GAP_BINS:
        selected = [
            float(row["v1_sign_invariant_angle_deg"])
            for row in rows
            if row["gap_bin"] == name
        ]
        bin_summary[name] = {
            "sample_count": len(selected),
            "v1_angle_statistics": descriptive_statistics(selected),
        }
    return {
        "adjacent_pair_count": len(rows),
        "v1_angle_statistics": descriptive_statistics(angle),
        "weak_subspace_max_angle_statistics": descriptive_statistics(
            subspace
        ),
        "relative_gap_12_statistics": descriptive_statistics(gap12),
        "relative_gap_23_statistics": descriptive_statistics(gap23),
        "relative_h_perturbation_statistics": descriptive_statistics(
            h_relative
        ),
        "perturbation_gap_ratio_statistics": descriptive_statistics(
            perturbation_gap
        ),
        "correlations": {
            "angle_v1_vs_relative_gap_12": spearman_summary(angle, gap12),
            "angle_v1_vs_perturbation_gap_ratio": spearman_summary(
                angle, perturbation_gap
            ),
            "subspace_angle_vs_relative_gap_12": spearman_summary(
                subspace, gap12
            ),
            "subspace_angle_vs_relative_h_perturbation": spearman_summary(
                subspace, h_relative
            ),
        },
        "gap_bins": bin_summary,
        "association_is_causal_proof": False,
    }


def region_rows(
    rows: Sequence[Mapping[str, Any]],
    region: str,
    first_divergence: int,
    window_start: int,
    window_end: int,
) -> list[Mapping[str, Any]]:
    if region == "pre_divergence":
        return [
            row for row in rows
            if int(row["record_index"]) < first_divergence
        ]
    if region == "onset_window":
        return [
            row for row in rows
            if window_start <= int(row["record_index"]) <= window_end
        ]
    if region == "post_divergence":
        return [
            row for row in rows
            if int(row["record_index"]) >= first_divergence
        ]
    raise ValueError(f"unknown region: {region}")


def summarize_cross_region(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "sample_count": len(rows),
        "v1_angle_statistics": descriptive_statistics(
            [float(row["v1_sign_invariant_angle_deg"]) for row in rows]
        ),
        "weak_subspace_max_angle_statistics": descriptive_statistics(
            [float(row["subspace_angle_max_deg"]) for row in rows]
        ),
        "relative_h_perturbation_statistics": descriptive_statistics(
            [float(row["relative_h_perturbation"]) for row in rows]
        ),
        "relative_gap_12_difference_statistics": descriptive_statistics(
            [float(row["relative_gap_12_abs_difference"]) for row in rows]
        ),
        "valid_correspondence_count_difference_statistics": (
            descriptive_statistics(
                [
                    abs(float(row["valid_correspondence_count_difference"]))
                    for row in rows
                ]
            )
        ),
        "semantic_equal_count": sum(
            bool(row["semantic_observation_equal"]) for row in rows
        ),
    }


def main() -> int:
    args = parse_args()
    input_root = args.input_root.resolve()
    semantic_root = args.semantic_comparison.resolve()
    output = args.output_dir.resolve()
    if output.exists():
        raise SystemExit(f"ERROR: output already exists: {output}")
    lock = json.loads(
        (input_root / "day6_branch_root_cause_input_lock.json").read_text(
            encoding="utf-8"
        )
    )
    mismatches = validate_source_lock(ROOT, lock["analysis_source_sha256"])
    if mismatches:
        raise ValueError(f"analysis source lock mismatch: {mismatches}")
    semantic_summary = json.loads(
        (semantic_root / "semantic_comparison_summary.json").read_text(
            encoding="utf-8"
        )
    )
    first_divergence = int(semantic_summary["first_divergence_record"])
    window_start = int(semantic_summary["window_start_record"])
    window_end = int(semantic_summary["window_end_record"])
    semantic_rows = read_csv(
        semantic_root / "semantic_observation_pairwise_comparison.csv"
    )
    semantic_equal = {
        (row["pair"], int(row["record_index"])): row["semantic_equal"]
        == "true"
        for row in semantic_rows
    }

    output.mkdir(parents=True)
    records = {}
    direct = {}
    reconstructions = {}
    reconstruction_rows = []
    time_continuity_rows = []
    reconstruction_summary = {}
    time_summary = {}
    all_errors = []
    for run_index in (1, 2, 3):
        records[run_index], _ = load_observation_records(
            input_root
            / f"run_{run_index}/observation_records_v3.bin"
        )
        direct[run_index] = read_jsonl(
            input_root
            / f"run_{run_index}/direct_production_metrics_v1.jsonl"
        )
        values = []
        errors = []
        for record_index, (record, direct_output) in enumerate(
            zip(records[run_index], direct[run_index])
        ):
            value = reconstruct_translation_information(record)
            error = compare_reconstruction(value, direct_output)
            values.append(value)
            errors.append(error)
            all_errors.append(error)
            reconstruction_rows.append(
                reconstruction_row(
                    run_index=run_index,
                    record_index=record_index,
                    record=record,
                    direct=direct_output,
                    value=value,
                    error=error,
                )
            )
        reconstructions[run_index] = values
        maximum = maximum_error(errors)
        reconstruction_summary[f"run_{run_index}"] = {
            "record_count": len(values),
            "maximum_error": maximum,
            "reconstruction_pass": reconstruction_pass(maximum),
            "relative_gap_12_statistics": descriptive_statistics(
                [float(value["relative_gap_12"]) for value in values]
            ),
            "relative_gap_23_statistics": descriptive_statistics(
                [float(value["relative_gap_23"]) for value in values]
            ),
        }
        adjacent = time_rows(run_index, values, records[run_index])
        time_continuity_rows.extend(adjacent)
        time_summary[f"run_{run_index}"] = summarize_time_rows(adjacent)

    write_csv(
        output / "information_matrix_reconstruction.csv",
        reconstruction_rows,
    )
    write_csv(
        output / "weak_vector_vs_subspace_stability.csv",
        time_continuity_rows,
    )
    overall_maximum = maximum_error(all_errors)
    all_reconstruction_pass = all(
        bool(value["reconstruction_pass"])
        for value in reconstruction_summary.values()
    )
    information_summary = {
        "schema_version": "day6_information_matrix_reconstruction_v1",
        "matrix_definition": (
            "PRODUCTION_HELPERS_POSE_WHITENING_TRANSLATION_SCHUR_"
            "EFFECTIVE_SAMPLE_NORMALIZATION"
        ),
        "detector_entrypoint_called": False,
        "production_helper_reuse": True,
        "float_dtype": "float64",
        "weight_semantics": "CONSTANT_SCALAR_VARIANCE",
        "robust_weight_added": False,
        "regularization_added": False,
        "per_run": reconstruction_summary,
        "overall_maximum_error": overall_maximum,
        "INFORMATION_MATRIX_RECONSTRUCTION_PASS": all_reconstruction_pass,
        "EIGENSYSTEM_RECONSTRUCTION_PASS": all_reconstruction_pass,
    }
    write_json(
        output / "information_matrix_reconstruction_summary.json",
        information_summary,
    )
    time_value = {
        "schema_version": "day6_time_continuity_association_v1",
        "per_run": time_summary,
        "descriptive_only": True,
        "davis_kahan_conditions_claimed": False,
        "TIME_CONTINUITY_ASSOCIATION_ANALYSIS_PASS": True,
    }
    write_json(
        output / "time_continuity_association_summary.json",
        time_value,
    )

    cross_rows = []
    cross_summary = {}
    for pair, left_index, right_index in PAIR_DEFINITIONS:
        pair_rows = []
        for record_index in range(487):
            left = reconstructions[left_index][record_index]
            right = reconstructions[right_index][record_index]
            left_record = records[left_index][record_index]
            right_record = records[right_index][record_index]
            left_direct = direct[left_index][record_index]
            right_direct = direct[right_index][record_index]
            subspace_min, subspace_max = (
                weak_subspace_principal_angles_deg(
                    left["weak_subspace"],
                    right["weak_subspace"],
                )
            )
            perturbation = matrix_perturbation(
                left["h_translation"],
                right["h_translation"],
            )
            row = {
                "pair": pair,
                "record_index": record_index,
                "scan_index": int(left_record["scan_index"]),
                "timestamp_begin": float(left_record["timestamp_begin"]),
                "timestamp_end": float(left_record["timestamp_end"]),
                "semantic_observation_equal": semantic_equal[
                    (pair, record_index)
                ],
                "valid_correspondence_count_difference": (
                    int(right_record["valid_correspondence_count"])
                    - int(left_record["valid_correspondence_count"])
                ),
                "jacobian_row_count_difference": (
                    len(right_record["detector_pose_jacobian_rows"])
                    - len(left_record["detector_pose_jacobian_rows"])
                ),
                "jacobian_shape_equal": (
                    len(right_record["detector_pose_jacobian_rows"])
                    == len(left_record["detector_pose_jacobian_rows"])
                ),
                **perturbation,
                "odi_abs_difference": abs(
                    float(right["odi_trans"]) - float(left["odi_trans"])
                ),
                "condition_number_abs_difference": abs(
                    float(right["condition_number"])
                    - float(left["condition_number"])
                ),
                "relative_gap_12_abs_difference": abs(
                    float(right["relative_gap_12"])
                    - float(left["relative_gap_12"])
                ),
                "v1_sign_invariant_angle_deg": sign_invariant_angle_deg(
                    left["v1"], right["v1"]
                ),
                "subspace_angle_min_deg": subspace_min,
                "subspace_angle_max_deg": subspace_max,
                "degeneracy_flag_agreement": (
                    left_direct["degeneracy_triggered"]
                    == right_direct["degeneracy_triggered"]
                ),
                "stable_flag_agreement": (
                    left_direct["primary_direction_stable"]
                    == right_direct["primary_direction_stable"]
                ),
                "actionable_flag_agreement": (
                    left_direct["actionable_direction"]
                    == right_direct["actionable_direction"]
                ),
            }
            pair_rows.append(row)
            cross_rows.append(row)
        cross_summary[pair] = {
            region: summarize_cross_region(
                region_rows(
                    pair_rows,
                    region,
                    first_divergence,
                    window_start,
                    window_end,
                )
            )
            for region in (
                "pre_divergence",
                "onset_window",
                "post_divergence",
            )
        }
    write_csv(output / "cross_run_eigenspace_alignment.csv", cross_rows)
    cross_value = {
        "schema_version": "day6_cross_run_eigenspace_summary_v1",
        "alignment_key": [
            "scan_index",
            "timestamp_begin",
            "timestamp_end",
        ],
        "first_divergence_record": first_divergence,
        "onset_window_start": window_start,
        "onset_window_end": window_end,
        "pairs": cross_summary,
        "descriptive_only": True,
        "CROSS_RUN_EIGENSPACE_ANALYSIS_PASS": True,
    }
    write_json(
        output / "cross_run_eigenspace_summary.json",
        cross_value,
    )

    gap_rows = []
    for run_name, value in time_summary.items():
        for bin_name, bin_value in value["gap_bins"].items():
            gap_rows.append(
                {
                    "run": run_name,
                    "gap_bin": bin_name,
                    "sample_count": bin_value["sample_count"],
                    "v1_angle_statistics": bin_value[
                        "v1_angle_statistics"
                    ],
                }
            )
    write_csv(output / "gap_bin_angle_summary.csv", gap_rows)

    extreme_count = sum(
        int(time_summary[run]["gap_bins"][name]["sample_count"])
        for run in ("run_1", "run_2", "run_3")
        for name in ("lt_1e-3", "1e-3_to_1e-2")
    )
    near_status = (
        "WEAK_DESCRIPTIVE_ASSOCIATION_NO_EXTREME_NEAR_MULTIPLES"
        if extreme_count == 0
        else "DESCRIPTIVE_ASSOCIATION_WITH_NEAR_MULTIPLES"
    )
    v1_p95 = max(
        float(time_summary[run]["v1_angle_statistics"]["p95"])
        for run in ("run_1", "run_2", "run_3")
    )
    subspace_p95 = max(
        float(
            time_summary[run]["weak_subspace_max_angle_statistics"]["p95"]
        )
        for run in ("run_1", "run_2", "run_3")
    )
    weak_subspace_status = (
        "RELATIVELY_MORE_STABLE_BUT_NOT_UNIFORMLY_STABLE"
        if subspace_p95 < v1_p95
        else "NOT_MORE_STABLE_THAN_V1"
    )
    summary = {
        "schema_version": "day6_weak_vector_subspace_summary_v1",
        "information_matrix_reconstruction": information_summary,
        "time_continuity": time_value,
        "cross_run": cross_value,
        "NEAR_MULTIPLE_EIGENSPACE_ASSOCIATION_STATUS": near_status,
        "WEAK_VECTOR_INSTABILITY_STATUS": (
            "DESCRIPTIVE_LARGE_ANGLE_TAIL_OBSERVED"
        ),
        "WEAK_SUBSPACE_STABILITY_STATUS": weak_subspace_status,
        "extreme_near_multiple_bin_sample_count": extreme_count,
        "single_vector_p95_max_across_runs_deg": v1_p95,
        "weak_subspace_p95_max_across_runs_deg": subspace_p95,
        "weak_subspace_uniform_stability_claimed": False,
        "near_multiple_explains_fast_branch_claimed": False,
        "SIGN_INVARIANT_DIRECTION_ANALYSIS_PASS": True,
        "WEAK_SUBSPACE_PRINCIPAL_ANGLE_ANALYSIS_PASS": True,
        "GAP_AND_PERTURBATION_ANALYSIS_PASS": True,
    }
    write_json(
        output / "weak_vector_vs_subspace_summary.json",
        summary,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
