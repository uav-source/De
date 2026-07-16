"""Schemas and engineering gates for the independent Day 13 V2 correction."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence


CORRECTION_SCHEMA_VERSION = "stage2_failure_day13_analysis_correction_v2"
CORRECTION_ID = "stage2_failure_day13_matched_analysis_correction_v2"
ANALYSIS_POPULATION = (
    "evaluation_one_to_one_matched_clean_vs_coherent_active_v2"
)
MATCHING_KEY_DESCRIPTION = (
    "sweep,level,geometry_seed,sensor_seed,process_seed,method,frame_index;"
    "timestamp_equal"
)

MATCHED_POPULATION_AUDIT_FIELDS = (
    "schema_version", "statistic_name", "statistic_role", "sweep",
    "matched_pair_count", "positive_frame_count", "negative_frame_count",
    "unmatched_positive_count", "duplicate_positive_key_count",
    "duplicate_clean_key_count", "invalid_pair_count",
    "unpaired_selected_row_count", "excluded_unmatched_clean_count",
    "analysis_population", "matching_key", "correction_version",
)

AUROC_SUMMARY_V2_FIELDS = (
    "schema_version", "statistic_name", "statistic_role", "sweep",
    "matched_pair_count", "positive_frame_count", "negative_frame_count",
    "unmatched_positive_count", "duplicate_positive_key_count",
    "duplicate_clean_key_count", "excluded_unmatched_clean_count", "auroc",
    "bootstrap_median", "ci95_lower", "ci95_upper",
    "valid_bootstrap_count", "invalid_bootstrap_count", "analysis_population",
    "matching_key", "correction_version",
)

PRIMARY_ROC_POINTS_V2_FIELDS = (
    "schema_version", "statistic_name", "sweep", "threshold",
    "comparison_operator", "true_positive_rate", "false_positive_rate",
    "positive_frame_count", "negative_frame_count", "matched_pair_count",
    "analysis_population", "correction_version",
)

LOCKED_OPERATING_POINT_FIELDS = (
    "schema_version", "statistic_name", "sweep", "matched_positive_count",
    "matched_negative_count", "true_positive_count", "false_positive_count",
    "true_positive_rate", "matched_clean_false_positive_rate", "threshold",
    "operator", "analysis_population", "correction_version",
)

FPR_BREAKDOWN_V2_FIELDS = (
    "schema_version", "role", "population", "eligible_frame_count",
    "false_positive_frame_count", "fpr", "threshold",
    "comparison_operator", "target", "target_met", "correction_version",
)

GROSS_CONTROL_INTERPRETATION_V2_FIELDS = (
    "schema_version", "sweep", "level", "gross_case_count",
    "median_contaminated_huber_downweighted_ratio",
    "zero_downweight_case_count", "zero_downweight_case_ratio",
    "median_contaminated_subhuber_ratio", "median_huber_outlier_ratio",
    "interpretation", "correction_version",
)

EXPECTED_OUTPUT_FILES = {
    "matched_population_audit.csv": MATCHED_POPULATION_AUDIT_FIELDS,
    "auroc_summary_v2.csv": AUROC_SUMMARY_V2_FIELDS,
    "primary_roc_points_v2.csv": PRIMARY_ROC_POINTS_V2_FIELDS,
    "locked_threshold_operating_points_v2.csv": LOCKED_OPERATING_POINT_FIELDS,
    "fpr_breakdown_v2.csv": FPR_BREAKDOWN_V2_FIELDS,
    "gross_control_interpretation_v2.csv": GROSS_CONTROL_INTERPRETATION_V2_FIELDS,
}
EXPECTED_JSON_FILES = {
    "preliminary_criteria_summary_v2.json",
    "analysis_correction_manifest.json",
    "day13_correction_summary.json",
}


def validate_fixed_rows(
    rows: Sequence[Mapping[str, Any]], fields: Sequence[str], name: str
) -> None:
    if not rows:
        raise ValueError(f"Day 13 correction {name} is empty")
    expected = set(fields)
    for row in rows:
        if set(row) != expected:
            raise ValueError(f"Day 13 correction {name} schema changed")
        if row.get("schema_version") != CORRECTION_SCHEMA_VERSION:
            raise ValueError(f"Day 13 correction {name} schema version changed")
        _reject_infinity(row, name)


def validate_correction_manifest(manifest: Mapping[str, Any]) -> None:
    required = {
        "schema_version", "correction_id", "created_at", "source_run_id",
        "source_run_dir", "source_v1_git_commit", "current_git_commit",
        "correction_reason", "original_population_rule",
        "incorrect_v1_implementation", "corrected_population_rule",
        "matching_key_fields", "source_design_lock_path",
        "source_design_lock_sha256", "source_calibration_lock_path",
        "source_calibration_lock_sha256",
        "source_calibration_frame_scores_sha256_before",
        "source_calibration_frame_scores_sha256_after",
        "source_evaluation_frame_scores_sha256_before",
        "source_evaluation_frame_scores_sha256_after",
        "source_frames_merged_sha256_before", "source_frames_merged_sha256_after",
        "source_v1_auroc_summary_sha256", "source_v1_roc_points_sha256",
        "source_v1_fpr_summary_sha256", "source_v1_summary_sha256",
        "original_geometry_positive_count", "original_geometry_negative_count",
        "corrected_geometry_positive_count", "corrected_geometry_negative_count",
        "original_observation_positive_count",
        "original_observation_negative_count",
        "corrected_observation_positive_count",
        "corrected_observation_negative_count", "original_geometry_auroc",
        "corrected_geometry_auroc", "corrected_geometry_ci95_lower",
        "corrected_geometry_ci95_upper", "original_observation_auroc",
        "corrected_observation_auroc", "corrected_observation_ci95_lower",
        "corrected_observation_ci95_upper", "locked_threshold",
        "threshold_unchanged", "calibration_trial_rerun",
        "evaluation_trial_rerun", "estimator_invoked", "seed_changed",
        "stress_changed", "statistic_changed", "threshold_changed",
        "retuning_performed", "matched_population_audit_pass",
        "input_immutability_pass", "bootstrap_pass", "fpr_breakdown_pass",
        "operating_point_pass", "gross_control_reporting_pass",
        "DAY13_CORRECTION_ENGINEERING_PASS",
        "DAY13_CORRECTION_PROTOCOL_PASS", "DAY13_CORRECTION_PASS",
        "DAY14_STAGE2_DECISION_AUTHORIZED", "STAGE2_GATE", "STAGE3_GATE",
        "COHERENT_BIAS_DETECTABLE", "RISK_WARNING_AUTHORIZED",
        "FAST_LIO2_INTEGRATION_AUTHORIZED", "PUBLIC_DISCLOSURE_AUTHORIZED",
    }
    missing = required - set(manifest)
    if missing:
        raise ValueError(
            "Day 13 correction manifest missing fields: " + ", ".join(sorted(missing))
        )
    if manifest.get("schema_version") != CORRECTION_SCHEMA_VERSION:
        raise ValueError("Day 13 correction manifest schema version changed")
    if manifest.get("correction_id") != CORRECTION_ID:
        raise ValueError("Day 13 correction ID changed")
    for field in (
        "source_design_lock_sha256", "source_calibration_lock_sha256",
        "source_calibration_frame_scores_sha256_before",
        "source_calibration_frame_scores_sha256_after",
        "source_evaluation_frame_scores_sha256_before",
        "source_evaluation_frame_scores_sha256_after",
        "source_frames_merged_sha256_before", "source_frames_merged_sha256_after",
        "source_v1_auroc_summary_sha256", "source_v1_roc_points_sha256",
        "source_v1_fpr_summary_sha256", "source_v1_summary_sha256",
    ):
        value = str(manifest.get(field, ""))
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError(f"invalid Day 13 correction hash: {field}")
    _reject_infinity(manifest, "manifest")


def evaluate_correction_gate(manifest: Mapping[str, Any]) -> bool:
    """Return engineering/protocol completeness, never a Stage 2 decision."""

    exact = {
        "schema_version": CORRECTION_SCHEMA_VERSION,
        "correction_id": CORRECTION_ID,
        "matching_key_fields": list((
            "sweep", "level", "geometry_seed", "sensor_seed", "process_seed",
            "method", "frame_index",
        )),
        "locked_threshold": 13.745952939169019,
        "threshold_unchanged": True,
        "calibration_trial_rerun": False,
        "evaluation_trial_rerun": False,
        "estimator_invoked": False,
        "seed_changed": False,
        "stress_changed": False,
        "statistic_changed": False,
        "threshold_changed": False,
        "retuning_performed": False,
        "original_geometry_positive_count": 1600,
        "original_geometry_negative_count": 2800,
        "corrected_geometry_positive_count": 1600,
        "corrected_geometry_negative_count": 1600,
        "original_observation_positive_count": 1600,
        "original_observation_negative_count": 2800,
        "corrected_observation_positive_count": 1600,
        "corrected_observation_negative_count": 1600,
        "geometry_missing_match_count": 0,
        "observation_missing_match_count": 0,
        "duplicate_positive_key_count": 0,
        "duplicate_clean_key_count": 0,
        "invalid_pair_count": 0,
        "unpaired_selected_row_count": 0,
        "geometry_excluded_unmatched_clean_count": 1200,
        "observation_excluded_unmatched_clean_count": 1200,
        "primary_geometry_valid_bootstrap_count": 5000,
        "primary_geometry_invalid_bootstrap_count": 0,
        "primary_observation_valid_bootstrap_count": 5000,
        "primary_observation_invalid_bootstrap_count": 0,
        "v1_locked_files_unchanged": True,
        "v1_raw_inputs_unchanged": True,
        "v1_analysis_outputs_unchanged": True,
        "matched_population_audit_pass": True,
        "input_immutability_pass": True,
        "bootstrap_pass": True,
        "fpr_breakdown_pass": True,
        "operating_point_pass": True,
        "gross_control_reporting_pass": True,
        "output_schema_pass": True,
        "STAGE2_GATE": "INCOMPLETE",
        "STAGE3_GATE": "NOT_STARTED",
        "COHERENT_BIAS_DETECTABLE": "UNDETERMINED",
        "RISK_WARNING_AUTHORIZED": False,
        "FAST_LIO2_INTEGRATION_AUTHORIZED": False,
        "PUBLIC_DISCLOSURE_AUTHORIZED": False,
    }
    if any(
        manifest.get(field) != value or type(manifest.get(field)) is not type(value)
        for field, value in exact.items()
    ):
        return False
    try:
        numeric = (
            "corrected_geometry_auroc", "corrected_geometry_ci95_lower",
            "corrected_geometry_ci95_upper", "corrected_observation_auroc",
            "corrected_observation_ci95_lower", "corrected_observation_ci95_upper",
            "geometry_locked_threshold_tpr", "geometry_matched_clean_fpr",
            "observation_locked_threshold_tpr", "observation_matched_clean_fpr",
        )
        if not all(math.isfinite(float(manifest[field])) for field in numeric):
            return False
    except (KeyError, TypeError, ValueError):
        return False
    return True


def validate_output_directory(output_dir: Path) -> None:
    output_dir = Path(output_dir)
    actual = {path.name for path in output_dir.iterdir() if path.is_file()}
    expected = set(EXPECTED_OUTPUT_FILES) | EXPECTED_JSON_FILES
    if actual != expected:
        raise ValueError("Day 13 correction output file set changed")
    for name, fields in EXPECTED_OUTPUT_FILES.items():
        path = output_dir / name
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != tuple(fields):
                raise ValueError(f"Day 13 correction CSV schema changed: {name}")
            rows = list(reader)
        if not rows:
            raise ValueError(f"Day 13 correction CSV is empty: {name}")
        for row in rows:
            if row.get("schema_version") != CORRECTION_SCHEMA_VERSION:
                raise ValueError(f"Day 13 correction CSV version changed: {name}")
            _reject_infinity(row, name)
    manifest = json.loads(
        (output_dir / "analysis_correction_manifest.json").read_text(encoding="utf-8")
    )
    if not isinstance(manifest, dict):
        raise ValueError("Day 13 correction manifest is not a mapping")
    validate_correction_manifest(manifest)
    for name in EXPECTED_JSON_FILES - {"analysis_correction_manifest.json"}:
        value = json.loads((output_dir / name).read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("schema_version") != CORRECTION_SCHEMA_VERSION:
            raise ValueError(f"Day 13 correction JSON schema changed: {name}")
        _reject_infinity(value, name)
    forbidden = {
        "frame_scores.csv", "frames_merged.csv", "frames_online.csv",
        "frames_gt.csv", "frames_window.csv",
    }
    if forbidden & actual:
        raise ValueError("Day 13 correction copied a frozen raw table")


def _reject_infinity(value: Any, context: str) -> None:
    if isinstance(value, Mapping):
        for item in value.values():
            _reject_infinity(item, context)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_infinity(item, context)
    elif isinstance(value, float) and math.isinf(value):
        raise ValueError(f"Day 13 correction {context} contains infinity")
    elif isinstance(value, str) and value.strip().lower() in {
        "inf", "+inf", "-inf", "infinity", "+infinity", "-infinity",
    }:
        raise ValueError(f"Day 13 correction {context} contains infinity")
