"""Null-safe, contract-aware comparison for offline detector diagnostics."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from numbers import Real
from typing import Any

import numpy as np


PRODUCTION_EXECUTED_DOMAIN = "PRODUCTION_EXECUTED_DOMAIN"
ADAPTER_PRECONDITION_DOMAIN = "ADAPTER_PRECONDITION_DOMAIN"
NOT_APPLICABLE = "NOT_APPLICABLE"
COMPARISON_TOLERANCE = 1.0e-12

METRIC_FIELDS = (
    "odi_trans",
    "ais_trans",
    "lambda_min_trans",
    "condition_number_trans",
    "translation_eigenvalues_ascending",
    "primary_weak_direction",
    "primary_eigengap_ratio",
    "primary_direction_stable",
    "degeneracy_triggered",
    "actionable_direction",
)
PRECONDITION_NULL_FIELDS = (
    "odi_trans",
    "ais_trans",
    "lambda_min_trans",
    "condition_number_trans",
    "translation_eigenvalues_ascending",
    "primary_weak_direction",
    "primary_eigengap_ratio",
)
PRECONDITION_FALSE_FIELDS = (
    "primary_direction_stable",
    "degeneracy_triggered",
    "actionable_direction",
)
REMEDIATION_REQUIRED_GATES = (
    "FROZEN_INPUT_IDENTITY_PASS",
    "PRODUCTION_DETECTOR_IDENTITY_PASS",
    "PRODUCTION_DETECTOR_ENTRYPOINT_CONFIRMED",
    "OBSERVATION_SCHEMA_REUSE_PASS",
    "DETECTOR_OUTPUT_SCHEMA_REUSE_PASS",
    "ADAPTER_GUARD_UNCHANGED_PASS",
    "THIN_ADAPTER_PASS",
    "JACOBIAN_NO_DOUBLE_REORDER_PASS",
    "VARIANCE_MAPPING_PASS",
    "PRIOR_COVARIANCE_NOT_USED_PASS",
    "RESIDUAL_NOT_USED_BY_DETECTOR_CONFIRMED",
    "NULL_SAFE_COMPARATOR_PASS",
    "PRODUCTION_EXECUTED_DOMAIN_COUNT_PASS",
    "ADAPTER_PRECONDITION_DOMAIN_COUNT_PASS",
    "ADAPTER_PRECONDITION_IDENTITY_PASS",
    "PRODUCTION_METRIC_EQUIVALENCE_PASS",
    "ADAPTER_PRECONDITION_CONTRACT_PASS",
    "FULL_DIRECT_PRODUCTION_ENTRYPOINT_COVERAGE_PASS",
    "DIRECT_PRODUCTION_DIAGNOSTIC_STREAM_PASS",
    "DIRECT_PRODUCTION_THREE_PROCESS_DETERMINISM_PASS",
    "ADAPTER_PIPELINE_THREE_PROCESS_DETERMINISM_PASS",
    "ADAPTER_OUTPUT_BACKWARD_COMPATIBILITY_PASS",
    "INPUT_IMMUTABILITY_PASS",
    "OUTPUT_COUNT_COMPLETENESS_PASS",
    "OUTPUT_SCHEMA_PASS",
    "NO_GT_PASS",
    "DETECTOR_ARTIFACT_IMMUTABILITY_PASS",
    "FROZEN_ARTIFACT_IMMUTABILITY_PASS",
    "FRESH_PROCESS_RUN_COMPLETENESS_PASS",
    "DEGEN_TARGETED_TEST_PASS",
    "DEGEN_FULL_TEST_PASS",
    "DIFF_SCOPE_PASS",
)
REMEDIATION_ZERO_COUNTS = (
    "production_metric_equivalence_mismatch_count",
    "adapter_precondition_contract_mismatch_count",
    "adapter_record_checksum_mismatch_count",
    "adapter_json_line_mismatch_count",
    "adapter_whole_file_sha_mismatch_count",
    "direct_record_checksum_mismatch_count",
    "direct_json_line_mismatch_count",
    "direct_whole_file_sha_mismatch_count",
    "adapter_input_mutation_count",
    "direct_input_mutation_count",
    "missing_output_count",
    "duplicate_output_count",
    "adapter_schema_rejected_count",
    "direct_schema_rejected_count",
    "detector_exception_count",
    "forbidden_field_count",
    "gt_topic_consumed_count",
)
REMEDIATION_FALSE_BOUNDARIES = (
    "roscore_run",
    "roslaunch_run",
    "rosbag_run",
    "fastlio2_run",
    "development_run",
    "holdout_run",
    "future_test_run",
    "detector_modified",
    "config_modified",
    "lock_modified",
    "threshold_modified",
    "adapter_guard_modified",
    "commit_created",
    "push_performed",
)


def classify_direct_equivalence_domain(
    record: Mapping[str, Any],
    adapter_output: Mapping[str, Any],
) -> str:
    """Classify by input shape only; the output argument prevents hidden lookup."""

    del adapter_output
    jacobian = np.asarray(record["detector_pose_jacobian_rows"], dtype=np.float64)
    if jacobian.ndim != 2:
        raise ValueError("detector Jacobian must be two-dimensional")
    if jacobian.shape[0] < jacobian.shape[1]:
        return ADAPTER_PRECONDITION_DOMAIN
    return PRODUCTION_EXECUTED_DOMAIN


def compare_null_safe(
    left: Any,
    right: Any,
    *,
    tolerance: float = COMPARISON_TOLERANCE,
) -> dict[str, Any]:
    """Compare supported canonical values without coercing nulls or booleans."""

    if left is None or right is None:
        if left is None and right is None:
            return _result(True, 0.0, ())
        return _result(False, 0.0, ("NULL_VALUE_DOMAIN_MISMATCH",))

    if isinstance(left, bool) or isinstance(right, bool):
        if isinstance(left, bool) and isinstance(right, bool):
            return _result(
                left is right,
                0.0,
                () if left is right else ("BOOLEAN_VALUE_MISMATCH",),
            )
        return _result(False, 0.0, ("VALUE_TYPE_MISMATCH",))

    if isinstance(left, Real) or isinstance(right, Real):
        if not isinstance(left, Real) or not isinstance(right, Real):
            return _result(False, 0.0, ("VALUE_TYPE_MISMATCH",))
        left_float = float(left)
        right_float = float(right)
        if not math.isfinite(left_float) or not math.isfinite(right_float):
            return _result(False, 0.0, ("NONFINITE_NUMERIC_VALUE",))
        error = abs(left_float - right_float)
        return _result(
            error <= tolerance,
            error,
            () if error <= tolerance else ("NUMERIC_TOLERANCE_EXCEEDED",),
        )

    left_sequence = _is_sequence(left)
    right_sequence = _is_sequence(right)
    if left_sequence or right_sequence:
        if not left_sequence or not right_sequence:
            return _result(False, 0.0, ("VALUE_TYPE_MISMATCH",))
        if len(left) != len(right):
            return _result(False, 0.0, ("LIST_LENGTH_MISMATCH",))
        results = [
            compare_null_safe(a, b, tolerance=tolerance)
            for a, b in zip(left, right)
        ]
        mismatch_types = tuple(
            dict.fromkeys(
                mismatch
                for result in results
                for mismatch in result["mismatch_types"]
            )
        )
        return _result(
            all(result["equal"] for result in results),
            max((result["max_abs_error"] for result in results), default=0.0),
            mismatch_types,
        )

    return _result(False, 0.0, ("UNSUPPORTED_VALUE_TYPE",))


def compare_metric_fields(
    adapter_output: Mapping[str, Any],
    direct_output: Mapping[str, Any],
    *,
    tolerance: float = COMPARISON_TOLERANCE,
) -> dict[str, Any]:
    mismatched_fields: list[str] = []
    mismatch_types: list[str] = []
    max_abs_error = 0.0
    for field in METRIC_FIELDS:
        result = compare_null_safe(
            adapter_output.get(field),
            direct_output.get(field),
            tolerance=tolerance,
        )
        max_abs_error = max(max_abs_error, float(result["max_abs_error"]))
        if not result["equal"]:
            mismatched_fields.append(field)
            mismatch_types.extend(result["mismatch_types"])
    return {
        "equal": not mismatched_fields,
        "max_abs_error": max_abs_error,
        "mismatched_fields": mismatched_fields,
        "mismatch_types": list(dict.fromkeys(mismatch_types)),
    }


def validate_adapter_precondition_contract(
    adapter_output: Mapping[str, Any],
) -> dict[str, Any]:
    mismatched_fields: list[str] = []
    if adapter_output.get("valid") is not False:
        mismatched_fields.append("valid")
    if adapter_output.get("invalid_reason") != "TOO_FEW_CORRESPONDENCES":
        mismatched_fields.append("invalid_reason")
    mismatched_fields.extend(
        field
        for field in PRECONDITION_NULL_FIELDS
        if adapter_output.get(field) is not None
    )
    mismatched_fields.extend(
        field
        for field in PRECONDITION_FALSE_FIELDS
        if adapter_output.get(field) is not False
    )
    return {
        "pass": not mismatched_fields,
        "mismatched_fields": mismatched_fields,
    }


def compare_contract_record(
    record: Mapping[str, Any],
    adapter_output: Mapping[str, Any],
    direct_output: Mapping[str, Any],
    *,
    tolerance: float = COMPARISON_TOLERANCE,
) -> dict[str, Any]:
    domain = classify_direct_equivalence_domain(record, adapter_output)
    if domain == ADAPTER_PRECONDITION_DOMAIN:
        contract = validate_adapter_precondition_contract(adapter_output)
        return {
            "equivalence_domain": domain,
            "metric_comparison_required": False,
            "metric_equivalence_pass": NOT_APPLICABLE,
            "max_abs_error": 0.0,
            "mismatched_fields": [],
            "mismatch_types": [],
            "precondition_contract_pass": contract["pass"],
            "precondition_mismatched_fields": contract["mismatched_fields"],
        }

    if adapter_output.get("valid") is not True or direct_output.get("valid") is not True:
        mismatched = []
        if adapter_output.get("valid") is not True:
            mismatched.append("adapter_valid")
        if direct_output.get("valid") is not True:
            mismatched.append("direct_valid")
        return {
            "equivalence_domain": domain,
            "metric_comparison_required": True,
            "metric_equivalence_pass": False,
            "max_abs_error": 0.0,
            "mismatched_fields": mismatched,
            "mismatch_types": ["PRODUCTION_DOMAIN_INVALID_OUTPUT"],
            "precondition_contract_pass": NOT_APPLICABLE,
            "precondition_mismatched_fields": [],
        }

    metrics = compare_metric_fields(
        adapter_output,
        direct_output,
        tolerance=tolerance,
    )
    return {
        "equivalence_domain": domain,
        "metric_comparison_required": True,
        "metric_equivalence_pass": metrics["equal"],
        "max_abs_error": metrics["max_abs_error"],
        "mismatched_fields": metrics["mismatched_fields"],
        "mismatch_types": metrics["mismatch_types"],
        "precondition_contract_pass": NOT_APPLICABLE,
        "precondition_mismatched_fields": [],
    }


def evaluate_remediation_gate(facts: Mapping[str, Any]) -> dict[str, bool]:
    """Evaluate only the explicitly authorized offline remediation decision."""

    required = {
        name: facts.get(name) is True for name in REMEDIATION_REQUIRED_GATES
    }
    zero_counts_pass = all(
        int(facts.get(name, -1)) == 0 for name in REMEDIATION_ZERO_COUNTS
    )
    boundary_pass = all(
        facts.get(name) is False for name in REMEDIATION_FALSE_BOUNDARIES
    )
    run_shape_pass = (
        int(facts.get("fresh_process_run_count", -1)) == 3
        and facts.get("per_run_input_count") == [487, 487, 487]
        and facts.get("per_run_adapter_output_count") == [487, 487, 487]
        and facts.get("per_run_direct_output_count") == [487, 487, 487]
        and facts.get("per_run_adapter_valid_count") == [486, 486, 486]
        and facts.get("per_run_adapter_invalid_count") == [1, 1, 1]
        and facts.get("per_run_direct_valid_count") == [487, 487, 487]
        and facts.get("per_run_direct_invalid_count") == [0, 0, 0]
        and int(facts.get("production_executed_domain_record_count", -1)) == 486
        and int(facts.get("adapter_precondition_domain_record_count", -1)) == 1
    )
    complete = (
        all(required.values())
        and zero_counts_pass
        and boundary_pass
        and run_shape_pass
    )
    return {
        **required,
        "PRODUCTION_DETECTOR_DETERMINISM_ON_DIRECT_STREAM_PASS": complete,
        "ADAPTER_PIPELINE_DETERMINISM_PASS": complete,
        "OFFLINE_PRODUCTION_DETECTOR_DETERMINISM_PASS": complete,
        "FALLBACK_C_PASS": complete,
        "DAY6_FALLBACK_FUNCTIONAL_DIAGNOSTICS_RECOMMENDED": complete,
        "FULL_ADAPTER_PRODUCTION_CALL_COVERAGE_PASS": False,
        "DAY6_QUICK_DIAGNOSTICS_AUTHORIZED": False,
        "REAL_REPLAY_FUNCTIONAL_STATISTICAL_TOLERANCE_AUTHORIZED": False,
    }


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    )


def _result(
    equal: bool,
    max_abs_error: float,
    mismatch_types: Sequence[str],
) -> dict[str, Any]:
    types = list(mismatch_types)
    return {
        "equal": bool(equal),
        "max_abs_error": float(max_abs_error),
        "mismatch_type": types[0] if types else "NONE",
        "mismatch_types": types,
    }
