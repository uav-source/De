"""Frozen-interval, reference-axis, eigengap, and trigger audit helpers."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
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
EIGENGAP_REGULARIZATION_EPSILON = 1.0e-12
EIGENGAP_THRESHOLD_SOURCE = (
    "Stage2A synthetic-development configuration; not calibrated on this real pilot"
)
ODI_METRIC_DEFINITION_VERSION = "detector_stage2a_v1"
ODI_TRIGGER_CALIBRATION_FRAME_COUNT = 2_080
ODI_TRIGGER_CONTROL_QUANTILE = 0.95
ODI_TRIGGER_THRESHOLD_SOURCE = (
    "Stage2A synthetic development Open Control q95 (n=2080)"
)


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


def _contract_bool(value: Any) -> bool | None:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    return None


def _finite_float(value: Any) -> float | None:
    if value in {"", None}:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _eigengap_contract_diagnostics(
    structural: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    nan_count = 0
    nonfinite_count = 0
    nonfinite_classified_reliable_count = 0
    assignment_mismatch_count = 0
    assignment_unparseable_count = 0
    eigenvalue_order_mismatch_count = 0
    ratio_reconstruction_mismatch_count = 0
    regularization_applied_count = 0
    unreliable_reasons: list[dict[str, Any]] = []

    for row in structural:
        raw_ratio = row.get("primary_eigengap_ratio")
        try:
            ratio_candidate = float(raw_ratio)
        except (TypeError, ValueError):
            ratio_candidate = float("nan")
        if math.isnan(ratio_candidate):
            nan_count += 1
        if not math.isfinite(ratio_candidate):
            nonfinite_count += 1
            if _contract_bool(row.get("direction_reliable")) is True:
                nonfinite_classified_reliable_count += 1
            continue

        recorded = _contract_bool(row.get("direction_reliable"))
        expected = ratio_candidate >= EIGENGAP_RATIO_THRESHOLD
        if recorded is None:
            assignment_unparseable_count += 1
            assignment_mismatch_count += 1
        elif recorded != expected:
            assignment_mismatch_count += 1

        eigenvalues = [
            _finite_float(row.get("lambda_min_trans")),
            _finite_float(row.get("lambda_mid_trans")),
            _finite_float(row.get("lambda_max_trans")),
        ]
        absolute_gap = _finite_float(row.get("primary_eigengap"))
        if all(value is not None for value in eigenvalues):
            finite_eigenvalues = [float(value) for value in eigenvalues]
            if finite_eigenvalues != sorted(finite_eigenvalues):
                eigenvalue_order_mismatch_count += 1
            ordered = np.sort(np.maximum(finite_eigenvalues, 0.0))
            denominator = max(
                float(ordered[-1]), EIGENGAP_REGULARIZATION_EPSILON
            )
            if any(value < 0.0 for value in finite_eigenvalues) or float(
                ordered[-1]
            ) <= EIGENGAP_REGULARIZATION_EPSILON:
                regularization_applied_count += 1
            reconstructed = float((ordered[1] - ordered[0]) / denominator)
            if not math.isclose(
                reconstructed, ratio_candidate, rel_tol=1.0e-12, abs_tol=1.0e-12
            ):
                ratio_reconstruction_mismatch_count += 1

        if not expected:
            unreliable_reasons.append(
                {
                    "scan_index": int(row["scan_index"]),
                    "reason": "PRIMARY_EIGENGAP_RATIO_BELOW_THRESHOLD",
                    "primary_eigengap_ratio": ratio_candidate,
                    "primary_eigengap_absolute": absolute_gap,
                    "threshold": EIGENGAP_RATIO_THRESHOLD,
                    "predicate": "primary_eigengap_ratio >= threshold",
                }
            )

    unreliable_reasons.sort(key=lambda item: item["scan_index"])
    return {
        "nan_primary_eigengap_ratio_count": nan_count,
        "nonfinite_primary_eigengap_ratio_count": nonfinite_count,
        "nonfinite_classified_reliable_count": nonfinite_classified_reliable_count,
        "assignment_mismatch_count": assignment_mismatch_count,
        "assignment_unparseable_count": assignment_unparseable_count,
        "eigenvalue_order_mismatch_count": eigenvalue_order_mismatch_count,
        "ratio_reconstruction_mismatch_count": ratio_reconstruction_mismatch_count,
        "regularization_applied_count": regularization_applied_count,
        "unreliable_reason_count": len(unreliable_reasons),
        "unreliable_reasons_json": json.dumps(
            unreliable_reasons, sort_keys=True, separators=(",", ":")
        ),
    }


def eigengap_reliability_rows(
    weak_rows: Sequence[Mapping[str, Any]],
    frame_rows: Sequence[Mapping[str, Any]],
    contract_evidence: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    angle_by_scan = {int(row["scan_index"]): float(row["angle_error_deg"]) for row in weak_rows}
    structural = [
        row
        for row in frame_rows
        if row.get("interval_label") == STRUCTURAL_LABEL
        and str(row.get("detector_valid")) == "True"
        and int(row["scan_index"]) in angle_by_scan
    ]
    diagnostics = _eigengap_contract_diagnostics(structural)
    groups: dict[str, list[float]] = {"reliable": [], "unreliable": []}
    nonfinite_angle_error_count = 0
    for row in structural:
        ratio = _finite_float(row.get("primary_eigengap_ratio"))
        angle = _finite_float(angle_by_scan[int(row["scan_index"])])
        assignment = _contract_bool(row.get("direction_reliable"))
        if angle is None:
            nonfinite_angle_error_count += 1
        # A non-finite eigengap ratio is never silently assigned to either
        # reliability group.  Its recorded state is audited above instead.
        if ratio is None or angle is None or assignment is None:
            continue
        group = "reliable" if assignment else "unreliable"
        groups[group].append(angle)
    reliable = groups["reliable"]
    unreliable = groups["unreliable"]
    if reliable and unreliable:
        test = mannwhitneyu(reliable, unreliable, alternative="two-sided")
        mann_whitney_u = float(test.statistic)
        mann_whitney_pvalue = float(test.pvalue)
        effect = cliffs_delta(reliable, unreliable)
    else:
        mann_whitney_u = float("nan")
        mann_whitney_pvalue = float("nan")
        effect = float("nan")
    output: list[dict[str, Any]] = []
    total = len(reliable) + len(unreliable)
    minority_count = min(len(reliable), len(unreliable))
    majority_ratio = max(len(reliable), len(unreliable)) / total if total else 0.0
    nearly_constant = bool(total and majority_ratio >= 0.95)
    evidence = dict(contract_evidence or {})
    threshold_source = str(
        evidence.get("threshold_source", EIGENGAP_THRESHOLD_SOURCE)
    )
    for offset, (name, values) in enumerate(groups.items()):
        lower, upper = bootstrap_median_interval(values, random_seed=20260726 + offset)
        output.append(
            {
                "group": name,
                "count": len(values),
                "ratio": len(values) / total if total else 0.0,
                "median_angle_error_deg": (
                    float(np.median(values)) if values else float("nan")
                ),
                "bootstrap_median_ci95_lower_deg": lower,
                "bootstrap_median_ci95_upper_deg": upper,
                "bootstrap_resamples": 10_000,
                "mann_whitney_u": mann_whitney_u,
                "mann_whitney_two_sided_pvalue": mann_whitney_pvalue,
                "cliffs_delta_reliable_minus_unreliable": effect,
                "minimum_sample_warning": len(values) < 20,
                "threshold": EIGENGAP_RATIO_THRESHOLD,
                "predicate": "primary_eigengap_ratio >= threshold",
                "comparison_operator": ">=",
                "gap_measure": "primary_eigengap_ratio",
                "ratio_not_absolute_gap": True,
                "absolute_gap_used_for_assignment": False,
                "eigenvalue_order": "ascending(lambda_min,lambda_mid,lambda_max)",
                "regularization": (
                    "eigenvalues=max(lambda_i,0); "
                    "denominator=max(lambda_max,1e-12)"
                ),
                "threshold_source": threshold_source,
                "threshold_origin_domain": "synthetic_development",
                "threshold_recalibrated_on_current_real_pilot": False,
                "nonfinite_angle_error_count": nonfinite_angle_error_count,
                "minority_group_count": minority_count,
                "majority_group_ratio": majority_ratio,
                "reliability_state_nearly_constant": nearly_constant,
                "near_constant_definition": "majority_group_ratio >= 0.95",
                "reliability_validation_sufficient": minority_count >= 20,
                **diagnostics,
            }
        )
    return output


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _default_trigger_contract_evidence() -> dict[str, Any]:
    """Load and verify the frozen production Stage2A contract.

    The production loader verifies the selected detector source and config
    hashes against the selected lock before it injects the finite threshold.
    The second lock copy and the calibration artifact are checked here so the
    audit records which lock and synthetic sample were used.
    """

    from fastlio2_adapter.detector_adapter import (
        DETECTOR_LOCK_PATH,
        ROOT,
        load_production_detector_contract,
    )

    config, provenance = load_production_detector_contract()
    lock_path = ROOT / DETECTOR_LOCK_PATH
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    canonical_lock_path = ROOT / "artifacts/current/detector_stage2a/detector_lock.json"
    calibration_path = (
        ROOT
        / "artifacts/current/detector_stage2a/development/odi_threshold_calibration.json"
    )
    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    lock_copy_hash_verified = (
        canonical_lock_path.is_file()
        and _sha256(lock_path) == _sha256(canonical_lock_path)
    )
    calibration_contract_matches_lock = bool(
        math.isclose(
            float(calibration["odi_trigger_threshold"]),
            float(lock["odi_trigger_threshold"]),
            rel_tol=0.0,
            abs_tol=0.0,
        )
        and math.isclose(
            float(calibration["trigger_control_quantile"]),
            float(lock["trigger_control_quantile"]),
            rel_tol=0.0,
            abs_tol=0.0,
        )
    )
    return {
        "detector_metric_version": str(lock["metric_definition_version"]),
        "calibration_frame_count": int(calibration["calibration_frame_count"]),
        "trigger_control_quantile": float(
            calibration["trigger_control_quantile"]
        ),
        "calibration_source": str(calibration["calibration_source"]),
        "calibration_data_sha256": str(calibration["calibration_data_sha256"]),
        "loaded_lock_path": DETECTOR_LOCK_PATH,
        "loaded_lock_sha256": str(provenance["detector_lock_sha256"]),
        "old_stage_lock_loaded": "detector_stage2a/locked" not in DETECTOR_LOCK_PATH,
        "detector_source_hash_verified": True,
        "detector_config_hash_verified": True,
        "lock_copy_hash_verified": lock_copy_hash_verified,
        "calibration_contract_matches_lock": calibration_contract_matches_lock,
        "default_infinity_fallback_used": "odi_trigger_threshold" not in config,
        "threshold_fields": {
            "detector_lock.odi_trigger_threshold": lock["odi_trigger_threshold"],
            "runtime_config.odi_trigger_threshold": config["odi_trigger_threshold"],
            "calibration.odi_trigger_threshold": calibration[
                "odi_trigger_threshold"
            ],
        },
    }


def trigger_contract_rows(
    frame_rows: Sequence[Mapping[str, Any]],
    contract_evidence: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    evidence = _default_trigger_contract_evidence()
    if contract_evidence:
        evidence.update(contract_evidence)
    threshold_fields = evidence.get("threshold_fields", {})
    if not isinstance(threshold_fields, Mapping):
        raise TypeError("contract_evidence.threshold_fields must be a mapping")
    threshold_field_values = {
        str(name): float(value) for name, value in threshold_fields.items()
    }
    conflicting_threshold_fields = [
        name
        for name, value in threshold_field_values.items()
        if not math.isclose(
            value, ODI_TRIGGER_THRESHOLD, rel_tol=0.0, abs_tol=0.0
        )
    ]

    output: list[dict[str, Any]] = []
    subsets = {
        "all_detector_valid": [row for row in frame_rows if str(row.get("detector_valid")) == "True"],
        "structural_frozen_interval": [row for row in frame_rows if row.get("interval_label") == STRUCTURAL_LABEL and str(row.get("detector_valid")) == "True"],
        "control_frozen_interval": [row for row in frame_rows if row.get("interval_label") == CONTROL_LABEL and str(row.get("detector_valid")) == "True"],
        "invalid_lifecycle_frames": [row for row in frame_rows if str(row.get("detector_valid")) != "True"],
    }
    all_assignment_mismatches = 0
    invalid_trigger_count = sum(
        _contract_bool(row.get("degeneracy_triggered")) is True
        for row in subsets["invalid_lifecycle_frames"]
    )
    for row in frame_rows:
        if str(row.get("detector_valid")) != "True":
            continue
        odi = _finite_float(row.get("ODI_trans"))
        recorded = _contract_bool(row.get("degeneracy_triggered"))
        if odi is None or recorded is None:
            all_assignment_mismatches += 1
        elif recorded != (odi >= ODI_TRIGGER_THRESHOLD):
            all_assignment_mismatches += 1

    source_hash_verified = bool(
        evidence.get("detector_source_hash_verified", False)
    )
    config_hash_verified = bool(
        evidence.get("detector_config_hash_verified", False)
    )
    lock_copy_hash_verified = bool(evidence.get("lock_copy_hash_verified", False))
    calibration_contract_matches_lock = bool(
        evidence.get("calibration_contract_matches_lock", False)
    )
    hash_verification_passed = bool(
        source_hash_verified
        and config_hash_verified
        and lock_copy_hash_verified
        and calibration_contract_matches_lock
    )
    metric_version = str(evidence.get("detector_metric_version", ""))
    metric_version_matches = metric_version == ODI_METRIC_DEFINITION_VERSION
    calibration_frame_count = int(evidence.get("calibration_frame_count", -1))
    calibration_quantile = float(evidence.get("trigger_control_quantile", math.nan))
    calibration_contract_matches_expected = bool(
        calibration_frame_count == ODI_TRIGGER_CALIBRATION_FRAME_COUNT
        and math.isclose(
            calibration_quantile,
            ODI_TRIGGER_CONTROL_QUANTILE,
            rel_tol=0.0,
            abs_tol=0.0,
        )
    )
    old_stage_lock_loaded = bool(evidence.get("old_stage_lock_loaded", True))
    default_infinity_fallback_used = bool(
        evidence.get("default_infinity_fallback_used", True)
    )

    for name, rows in subsets.items():
        odi = np.asarray(
            [
                value
                for row in rows
                if (value := _finite_float(row.get("ODI_trans"))) is not None
            ],
            dtype=float,
        )
        triggered = [
            _contract_bool(row.get("degeneracy_triggered")) is True for row in rows
        ]
        assignment_mismatch_count = 0
        unparseable_trigger_state_count = 0
        nonfinite_valid_odi_count = 0
        for row in rows:
            if str(row.get("detector_valid")) != "True":
                continue
            value = _finite_float(row.get("ODI_trans"))
            recorded = _contract_bool(row.get("degeneracy_triggered"))
            if value is None:
                nonfinite_valid_odi_count += 1
                assignment_mismatch_count += 1
            elif recorded is None:
                unparseable_trigger_state_count += 1
                assignment_mismatch_count += 1
            elif recorded != (value >= ODI_TRIGGER_THRESHOLD):
                assignment_mismatch_count += 1
        output.append(
            {
                "subset": name,
                "count": len(rows),
                "threshold": ODI_TRIGGER_THRESHOLD,
                "threshold_unit": "dimensionless_ODI_0_to_1",
                "predicate": "ODI_trans >= threshold",
                "comparison_operator": ">=",
                "threshold_source": ODI_TRIGGER_THRESHOLD_SOURCE,
                "calibration_source": str(evidence.get("calibration_source", "")),
                "calibration_frame_count": calibration_frame_count,
                "trigger_control_quantile": calibration_quantile,
                "calibration_contract_matches_expected": (
                    calibration_contract_matches_expected
                ),
                "detector_metric_version": metric_version,
                "expected_detector_metric_version": ODI_METRIC_DEFINITION_VERSION,
                "metric_version_matches_threshold": metric_version_matches,
                "loaded_lock_path": str(evidence.get("loaded_lock_path", "")),
                "loaded_lock_sha256": str(
                    evidence.get("loaded_lock_sha256", "")
                ),
                "old_stage_lock_loaded": old_stage_lock_loaded,
                "detector_source_hash_verified": source_hash_verified,
                "detector_config_hash_verified": config_hash_verified,
                "lock_copy_hash_verified": lock_copy_hash_verified,
                "calibration_contract_matches_lock": (
                    calibration_contract_matches_lock
                ),
                "hash_verification_passed": hash_verification_passed,
                "calibration_data_sha256": str(
                    evidence.get("calibration_data_sha256", "")
                ),
                "threshold_field_names": ";".join(sorted(threshold_field_values)),
                "threshold_field_values_json": json.dumps(
                    threshold_field_values, sort_keys=True, separators=(",", ":")
                ),
                "config_field_conflict": bool(conflicting_threshold_fields),
                "config_field_conflict_count": len(conflicting_threshold_fields),
                "conflicting_threshold_fields": ";".join(
                    sorted(conflicting_threshold_fields)
                ),
                "missing_threshold_default": "positive_infinity",
                "default_infinity_fallback_used": default_infinity_fallback_used,
                "missing_threshold_triggers": False,
                "threshold_recalibrated_on_current_real_data": False,
                "trigger_count": int(np.sum(triggered)),
                "trigger_ratio": float(np.mean(triggered)) if triggered else 0.0,
                "odi_min": float(np.min(odi)) if odi.size else float("nan"),
                "odi_median": float(np.median(odi)) if odi.size else float("nan"),
                "odi_max": float(np.max(odi)) if odi.size else float("nan"),
                "nonfinite_valid_odi_count": nonfinite_valid_odi_count,
                "unparseable_trigger_state_count": unparseable_trigger_state_count,
                "trigger_assignment_mismatch_count": assignment_mismatch_count,
                "trigger_assignment_mismatch_total": all_assignment_mismatches,
                "invalid_trigger_count": invalid_trigger_count,
                "invalid_treated_as_trigger": bool(
                    invalid_trigger_count and name == "invalid_lifecycle_frames"
                ),
                "trigger_implementation_bug_confirmed": bool(
                    all_assignment_mismatches
                    or invalid_trigger_count
                    or old_stage_lock_loaded
                    or default_infinity_fallback_used
                    or conflicting_threshold_fields
                    or not metric_version_matches
                    or not hash_verification_passed
                    or not calibration_contract_matches_expected
                ),
            }
        )
    return output
