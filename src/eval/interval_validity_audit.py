"""Frozen-interval, reference-axis, eigengap, and trigger audit helpers."""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from scipy.spatial.transform import Rotation
from scipy.stats import mannwhitneyu

from eval.frame_contract import sign_invariant_angle_deg
from eval.measurement_real_analysis import summary_statistics


STRUCTURAL_LABEL = "structural_degeneracy_candidate"
CONTROL_LABEL = "geometry_rich_control"
EIGENGAP_RATIO_THRESHOLD = 0.02
ODI_TRIGGER_THRESHOLD = 0.035199792993590634


INFORMATION_RISK_DIRECTIONS = {
    "ODI_trans": "higher",
    "AIS_trans": "lower",
    "lambda_min_trans": "lower",
    "condition_number_trans": "higher",
    "lambda_min_over_lambda_max": "lower",
    "spectral_entropy_trans": "lower",
    "effective_rank_trans": "lower",
}


def _selected_frame_rows(
    rows: Iterable[Mapping[str, Any]], interval_id: str
) -> list[Mapping[str, Any]]:
    return [
        row
        for row in rows
        if row.get("interval_id") == interval_id
        and str(row.get("detector_valid")) == "True"
    ]


def interval_information_rows(
    frame_rows: Iterable[Mapping[str, Any]],
    intervals: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    fields = (
        "ODI_trans",
        "AIS_trans",
        "lambda_min_trans",
        "lambda_mid_trans",
        "lambda_max_trans",
        "condition_number_trans",
        "lambda_min_over_lambda_max",
        "spectral_entropy_trans",
        "effective_rank_trans",
        "primary_eigengap",
        "primary_eigengap_ratio",
        "valid_correspondence_count",
    )
    all_rows = list(frame_rows)
    for interval in intervals:
        selected = _selected_frame_rows(all_rows, str(interval["interval_id"]))
        for field in fields:
            statistics = summary_statistics([float(row[field]) for row in selected])
            output.append(
                {
                    "interval_id": interval["interval_id"],
                    "interval_label": interval["label"],
                    "metric": field,
                    "risk_direction": INFORMATION_RISK_DIRECTIONS.get(
                        field, "direction_identifiability_only" if "eigengap" in field else "not_risk_oriented"
                    ),
                    **statistics,
                }
            )
    return output


def information_supports_label_invalidation(
    information_rows: Sequence[Mapping[str, Any]],
) -> tuple[bool, list[dict[str, Any]]]:
    medians: dict[tuple[str, str], float] = {
        (str(row["interval_label"]), str(row["metric"])): float(row["median"])
        for row in information_rows
    }
    comparisons: list[dict[str, Any]] = []
    for metric, direction in INFORMATION_RISK_DIRECTIONS.items():
        structural = medians[(STRUCTURAL_LABEL, metric)]
        control = medians[(CONTROL_LABEL, metric)]
        control_more_risky = control > structural if direction == "higher" else control < structural
        comparisons.append(
            {
                "metric": metric,
                "risk_direction": direction,
                "structural_median": structural,
                "control_median": control,
                "control_more_degenerate": control_more_risky,
            }
        )
    # The values include algebraically related reporting fields, but both
    # absolute-strength and spectral-shape families must independently agree.
    absolute_family = all(
        row["control_more_degenerate"]
        for row in comparisons
        if row["metric"] in {"AIS_trans", "lambda_min_trans"}
    )
    shape_family = all(
        row["control_more_degenerate"]
        for row in comparisons
        if row["metric"] in {
            "ODI_trans",
            "condition_number_trans",
            "lambda_min_over_lambda_max",
        }
    )
    return bool(absolute_family and shape_family), comparisons


def _geometry_measure(
    interval: Mapping[str, Any],
    measure: str,
    availability: str,
    value: Any,
    unit: str,
    source: str,
    interpretation: str,
) -> dict[str, Any]:
    return {
        "interval_id": interval["interval_id"],
        "interval_label": interval["label"],
        "measure": measure,
        "availability": availability,
        "value": value,
        "unit": unit,
        "evidence_source": source,
        "interpretation": interpretation,
    }


def interval_geometry_rows(
    intervals: Sequence[Mapping[str, Any]],
    runtime_rows: Sequence[Mapping[str, Any]],
    descriptor_rows: Sequence[Mapping[str, Any]],
    navsat_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for interval in intervals:
        start = float(interval["start_timestamp"])
        end = float(interval["end_timestamp"])
        runtime = [row for row in runtime_rows if start <= float(row["timestamp_end"]) <= end]
        descriptors = [row for row in descriptor_rows if start <= float(row["timestamp"]) <= end]
        fixes = [row for row in navsat_rows if start <= float(row["timestamp"]) <= end]
        numeric_runtime = (
            ("accepted_correspondence_count", "valid_correspondence_count", "count", "active FAST-LIO accepted plane correspondences"),
            ("downsampled_scan_point_count", "downsampled_point_count", "count", "points presented to scan-to-map matching"),
            ("processed_lidar_point_count", "lidar_point_count", "count", "post-preprocess scan points"),
            ("local_map_point_count", "map_size_after_update", "count", "map support size; spatial extent was not retained"),
        )
        for measure, field, unit, interpretation in numeric_runtime:
            values = np.asarray([float(row[field]) for row in runtime])
            statistics = summary_statistics(values)
            output.append(
                _geometry_measure(
                    interval,
                    f"{measure}_median",
                    "AVAILABLE",
                    statistics["median"],
                    unit,
                    "runtime_audit_v2.bin",
                    interpretation,
                )
            )
            output.append(
                _geometry_measure(
                    interval,
                    f"{measure}_q05_q95",
                    "AVAILABLE",
                    f"{statistics['q05']:.12g};{statistics['q95']:.12g}",
                    unit,
                    "runtime_audit_v2.bin",
                    "descriptive interval spread",
                )
            )
        for measure, field, unit, interpretation in (
            ("raw_scan_xy_anisotropy_median", "raw_xy_anisotropy", "ratio", "detector-free selection proxy only"),
            ("raw_scan_azimuth_coverage_median", "azimuth_sector_coverage", "fraction", "raw scan angular support"),
            ("raw_scan_range_median", "range_median_m", "m", "raw scan range descriptor"),
            ("raw_scan_range_q95_median", "range_q95_m", "m", "available scan-extent proxy"),
        ):
            values = [float(row[field]) for row in descriptors]
            output.append(
                _geometry_measure(
                    interval,
                    measure,
                    "AVAILABLE" if values else "UNAVAILABLE",
                    float(np.median(values)) if values else "",
                    unit,
                    "raw_scene_descriptors.csv",
                    interpretation,
                )
            )
        if len(runtime) >= 2:
            times = np.asarray([float(row["timestamp_end"]) for row in runtime])
            positions = np.asarray([row["posterior_position"] for row in runtime], dtype=float)
            speeds = np.linalg.norm(np.diff(positions, axis=0), axis=1) / np.diff(times)
            rotations = Rotation.from_quat(
                np.asarray([row["posterior_orientation_xyzw"] for row in runtime], dtype=float)
            ).as_euler("xyz")
            rpy_range = np.ptp(np.unwrap(rotations, axis=0), axis=0) * 180.0 / np.pi
            output.append(_geometry_measure(interval, "vehicle_speed_median", "AVAILABLE", float(np.median(speeds)), "m/s", "runtime_audit_v2.bin", "posterior finite-difference speed"))
            for name, value in zip(("roll", "pitch", "yaw"), rpy_range):
                output.append(_geometry_measure(interval, f"{name}_range", "AVAILABLE", float(value), "degree", "runtime_audit_v2.bin", "unwrapped posterior orientation range"))
        status = np.asarray([int(row["status"]) for row in fixes], dtype=int)
        output.append(
            _geometry_measure(
                interval,
                "rtk_quality_good_ratio",
                "AVAILABLE" if status.size else "UNAVAILABLE",
                float(np.mean(status >= 2)) if status.size else "",
                "fraction",
                "navsat_fix.csv",
                "NavSatStatus >= GBAS_FIX",
            )
        )
        for measure, explanation in (
            ("scan_to_map_plane_normal_distribution", "observation binary and individual correspondences were not retained"),
            ("scan_to_map_normal_direction_covariance", "observation binary and plane normals were not retained"),
            ("local_map_spatial_extent", "only local-map point count/checksum was retained"),
            ("end_face_constraint_count", "correspondence geometry classification was not retained"),
            ("floor_ceiling_wall_support_ratio", "correspondence geometry classification was not retained"),
            ("correspondence_residual_distribution", "only residual count/checksum, not residual values, was retained"),
        ):
            output.append(
                _geometry_measure(
                    interval,
                    measure,
                    "UNAVAILABLE_NOT_RETAINED",
                    "",
                    "N/A",
                    "measurement retention contract",
                    explanation,
                )
            )
    return output


def bootstrap_median_interval(
    values: Sequence[float],
    *,
    random_seed: int = 20260726,
    resamples: int = 10_000,
) -> tuple[float, float]:
    data = np.asarray(values, dtype=np.float64)
    data = data[np.isfinite(data)]
    if data.size == 0:
        return float("nan"), float("nan")
    rng = np.random.default_rng(random_seed)
    medians = np.median(rng.choice(data, size=(resamples, data.size), replace=True), axis=1)
    lower, upper = np.quantile(medians, [0.025, 0.975])
    return float(lower), float(upper)


def cliffs_delta(left: Sequence[float], right: Sequence[float]) -> float:
    a = np.asarray(left, dtype=np.float64)
    b = np.asarray(right, dtype=np.float64)
    differences = a[:, None] - b[None, :]
    return float((np.sum(differences > 0.0) - np.sum(differences < 0.0)) / differences.size)


def eigengap_reliability_rows(
    weak_rows: Sequence[Mapping[str, Any]],
    frame_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    angle_by_scan = {int(row["scan_index"]): float(row["angle_error_deg"]) for row in weak_rows}
    structural = [
        row
        for row in frame_rows
        if row.get("interval_label") == STRUCTURAL_LABEL
        and str(row.get("detector_valid")) == "True"
        and int(row["scan_index"]) in angle_by_scan
    ]
    groups: dict[str, list[float]] = {"reliable": [], "unreliable": []}
    for row in structural:
        group = "reliable" if str(row["direction_reliable"]) == "True" else "unreliable"
        groups[group].append(angle_by_scan[int(row["scan_index"])])
    reliable = groups["reliable"]
    unreliable = groups["unreliable"]
    test = mannwhitneyu(reliable, unreliable, alternative="two-sided")
    effect = cliffs_delta(reliable, unreliable)
    output: list[dict[str, Any]] = []
    total = len(reliable) + len(unreliable)
    for offset, (name, values) in enumerate(groups.items()):
        lower, upper = bootstrap_median_interval(values, random_seed=20260726 + offset)
        output.append(
            {
                "group": name,
                "count": len(values),
                "ratio": len(values) / total,
                "median_angle_error_deg": float(np.median(values)),
                "bootstrap_median_ci95_lower_deg": lower,
                "bootstrap_median_ci95_upper_deg": upper,
                "bootstrap_resamples": 10_000,
                "mann_whitney_u": float(test.statistic),
                "mann_whitney_two_sided_pvalue": float(test.pvalue),
                "cliffs_delta_reliable_minus_unreliable": effect,
                "minimum_sample_warning": len(values) < 20,
                "threshold": EIGENGAP_RATIO_THRESHOLD,
                "predicate": "primary_eigengap_ratio >= threshold",
            }
        )
    return output


def trigger_contract_rows(frame_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    subsets = {
        "all_detector_valid": [row for row in frame_rows if str(row.get("detector_valid")) == "True"],
        "structural_frozen_interval": [row for row in frame_rows if row.get("interval_label") == STRUCTURAL_LABEL and str(row.get("detector_valid")) == "True"],
        "control_frozen_interval": [row for row in frame_rows if row.get("interval_label") == CONTROL_LABEL and str(row.get("detector_valid")) == "True"],
        "invalid_lifecycle_frames": [row for row in frame_rows if str(row.get("detector_valid")) != "True"],
    }
    for name, rows in subsets.items():
        odi = np.asarray(
            [float(row["ODI_trans"]) for row in rows if row.get("ODI_trans") not in {"", None}],
            dtype=float,
        )
        triggered = [str(row.get("degeneracy_triggered")) == "True" for row in rows]
        output.append(
            {
                "subset": name,
                "count": len(rows),
                "threshold": ODI_TRIGGER_THRESHOLD,
                "threshold_unit": "dimensionless_ODI_0_to_1",
                "predicate": "ODI_trans >= threshold",
                "threshold_source": "Stage2A synthetic development Open Control q95 (n=2080)",
                "trigger_count": int(np.sum(triggered)),
                "trigger_ratio": float(np.mean(triggered)) if triggered else 0.0,
                "odi_min": float(np.min(odi)) if odi.size else float("nan"),
                "odi_median": float(np.median(odi)) if odi.size else float("nan"),
                "odi_max": float(np.max(odi)) if odi.size else float("nan"),
                "invalid_treated_as_trigger": bool(
                    any(triggered) and name == "invalid_lifecycle_frames"
                ),
            }
        )
    return output
