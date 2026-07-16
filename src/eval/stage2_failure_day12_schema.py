"""Frozen schemas and gate logic for Stage 2 Day 12 diagnostics."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any, Mapping, Sequence


DAY12_SCHEMA_VERSION = "stage2_failure_day12_figures_v2"
INPUT_AUDIT_SCHEMA_VERSION = "stage2_failure_day12_input_audit_v2"
INPUT_LOCK_SCHEMA_VERSION = "stage2_failure_day12_input_lock_v2"
EXPECTED_METHODS = ("huber_full", "huber_projected_gain")
EXPECTED_STRESSES = ("clean", "coherent_subhuber_slip")
EXPECTED_SWEEPS = ("geometry", "observation")
DISCLOSURE_NOTE = (
    "Preregistered deterministic diagnostic cases; frame-wise descriptive data; "
    "not an independent test."
)

FIGURE_DATA_FIELDS = {
    "day12_fig01_innovation_timeline": (
        "case_id", "sweep", "method", "stress", "frame_index", "timestamp",
        "stress_active", "stat_input_valid", "window_ready",
        "weak_innovation_z_huber", "huber_window_mean", "source_row_sha256",
    ),
    "day12_fig02_prior_posterior_axis_error": (
        "case_id", "sweep", "method", "stress", "frame_index", "timestamp",
        "stress_active", "offline_evaluation_only", "prior_axis_error_abs_m",
        "posterior_axis_error_abs_m", "axis_abs_error_reduction_m", "source_row_sha256",
    ),
    "day12_fig03_same_sign_run_timeline": (
        "case_id", "sweep", "method", "stress", "frame_index", "timestamp",
        "stress_active", "stat_input_valid", "window_ready",
        "huber_current_same_sign_run_length", "huber_max_same_sign_run_length",
        "huber_dominant_sign_ratio", "source_row_sha256",
    ),
    "day12_fig04_clean_stress_distributions": (
        "case_id", "sweep", "method", "stress", "frame_index", "metric_name",
        "metric_value", "inclusion_rule", "included", "deterministic_jitter",
        "source_row_sha256",
    ),
}

DESCRIPTIVE_SUMMARY_FIELDS = (
    "sweep", "method", "stress", "frame_count", "valid_innovation_frame_count",
    "window_ready_frame_count", "median_abs_weak_innovation_z_huber",
    "q25_abs_weak_innovation_z_huber", "q75_abs_weak_innovation_z_huber",
    "median_abs_huber_window_mean", "q25_abs_huber_window_mean",
    "q75_abs_huber_window_mean", "max_abs_huber_cusum_signed",
    "median_abs_huber_cusum_signed", "max_huber_same_sign_run_length",
    "median_huber_same_sign_run_length", "median_prior_axis_error_abs_m",
    "median_posterior_axis_error_abs_m", "median_axis_abs_error_reduction_m",
    "fraction_axis_error_reduced",
)


def evaluate_day12_gate(values: Mapping[str, Any]) -> bool:
    required_true = (
        "git_status_clean_at_start", "head_descends_from_day11b_v2_checkpoint",
        "day12_input_audit_pass", "axial_only_audit_pass",
        "repro_plot_data_byte_identical", "repro_png_pixel_hash_identical",
        "repro_summary_byte_identical", "repro_captions_byte_identical",
        "day11b_v2_results_unchanged", "figures_for_diagnosis_only",
        "coherent_shared_sign_pass", "historical_artifacts_unchanged",
    )
    zero_fields = (
        "strategy_chain_mismatch_count", "duplicate_frame_key_count",
        "case_identity_mismatch_count",
        "missing_frame_key_count", "nonfinite_violation_count",
        "plot_data_audit_failure_count", "source_row_hash_mismatch_count",
        "source_value_mismatch_count",
        "unexpected_figure_count", "figure_qc_failure_count",
        "forbidden_output_count",
        "contaminated_non_axial_support_count",
        "points_lidar_mismatch_count", "normals_world_mismatch_count",
        "R_diag_mismatch_count",
    )
    false_fields = (
        "estimator_replayed", "new_seed_used", "day11b_results_modified",
        "figure_data_selected_after_viewing", "best_statistic_selected",
        "best_method_selected", "threshold_created", "threshold_line_drawn",
        "auroc_computed", "fpr_computed", "f1_computed",
        "detection_delay_computed", "significance_test_performed",
        "replay_is_independent_test", "replay_is_representative",
    )
    if not all(values.get(field) is True for field in required_true):
        return False
    if not all(int(values.get(field, -1)) == 0 for field in zero_fields):
        return False
    if not all(values.get(field) is False for field in false_fields):
        return False
    exact = {
        "expected_case_count": 8, "actual_case_count": 8,
        "day11b_v2_checkpoint_commit": "480960def270d2739a21bfc4967990318d2ed3c3",
        "strategy_chain_comparison_count": 8,
        "method_expanded_contaminated_measurement_count": 872,
        "external_unique_contaminated_measurement_count": 436,
        "method_expanded_stress_active_frame_count": 80,
        "external_unique_stress_active_frame_count": 40,
        "coherent_burst_count": 2, "coherent_burst_lengths": [20, 20],
        "coherent_offset_abs_m": 0.03, "plot_data_file_count": 4,
        "expected_figure_count": 4, "png_figure_count": 4,
        "pdf_figure_count": 4, "STAGE2_GATE": "INCOMPLETE",
        "STAGE3_GATE": "NOT_STARTED", "COHERENT_BIAS_DETECTABLE": "UNDETERMINED",
        "RISK_WARNING_AUTHORIZED": False, "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
        "PUBLIC_DISCLOSURE_AUTHORIZED": False,
    }
    if any(values.get(field) != expected for field, expected in exact.items()):
        return False
    expected_rows = int(values.get("expected_merged_row_count", -1))
    if expected_rows <= 0 or int(values.get("actual_merged_row_count", -2)) != expected_rows:
        return False
    return True


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def padded_limits(values: Sequence[float], integer: bool = False) -> tuple[float, float]:
    finite = [float(value) for value in values if math.isfinite(float(value))]
    if not finite:
        return (-1.0, 1.0)
    low, high = min(finite), max(finite)
    span = high - low
    padding = 0.05 * span if span > 0.0 else max(abs(high) * 0.05, 0.05)
    if integer:
        return (math.floor(min(0.0, low) - padding), math.ceil(high + padding))
    return (low - padding, high + padding)
