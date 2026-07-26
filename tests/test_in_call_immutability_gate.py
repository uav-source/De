from __future__ import annotations

from fastlio2_adapter.in_call_immutability import evaluate_gate
from test_in_call_immutability_schema import valid_status


def passing_facts() -> dict[str, object]:
    return {
        "hook_placement_confirmed": True,
        "canonical_checksum_reuse": True,
        "covariance_access_confirmed": True,
        "implementation_pass": True,
        "static_readonly_audit_pass": True,
        "fast_build_pass": True,
        "fast_test_pass": True,
        "degen_targeted_test_pass": True,
        "degen_full_test_pass": True,
        "real_engineering_run_completeness_pass": True,
        "all_callbacks_received_pass": True,
        "end_of_stream_drain_pass": True,
        "normal_shutdown_pass": True,
        "no_gt_pass": True,
        "tap_drop_count": 0,
        "diff_scope_pass": True,
    }


def test_all_frozen_gates_pass_only_for_clean_same_call_evidence() -> None:
    gates = evaluate_gate(valid_status(), passing_facts())
    assert gates["DAY5_FALLBACK_IN_CALL_IMMUTABILITY_PASS"]
    assert gates["FROZEN_REAL_OBSERVATION_RECORD_AUTHORIZED"]
    assert gates["DAY6_QUICK_DIAGNOSTICS_AUTHORIZED"] is False


def test_one_checksum_mismatch_fails_authorization() -> None:
    status = valid_status()
    status["mutation_detected_count"] = 1
    status["map_size_mismatch_count"] = 1
    status["all_unchanged_count"] = 2
    from fastlio2_adapter.in_call_immutability import expected_status_checksum

    status["audit_status_checksum"] = expected_status_checksum(status)
    gates = evaluate_gate(status, passing_facts())
    assert gates["MAP_SIZE_IMMUTABILITY_PASS"] is False
    assert gates["FROZEN_REAL_OBSERVATION_RECORD_AUTHORIZED"] is False


def test_zero_audited_calls_fail() -> None:
    status = valid_status()
    status["audited_call_count"] = 0
    status["all_unchanged_count"] = 0
    status["tap_call_attempt_count"] = 0
    from fastlio2_adapter.in_call_immutability import expected_status_checksum

    status["audit_status_checksum"] = expected_status_checksum(status)
    gates = evaluate_gate(status, passing_facts())
    assert gates["AUDITED_CALL_COUNT_POSITIVE_PASS"] is False
    assert gates["DAY5_FALLBACK_IN_CALL_IMMUTABILITY_PASS"] is False


def test_attempt_coverage_mismatch_fails() -> None:
    status = valid_status()
    status["tap_call_attempt_count"] = 4
    from fastlio2_adapter.in_call_immutability import expected_status_checksum

    status["audit_status_checksum"] = expected_status_checksum(status)
    gates = evaluate_gate(status, passing_facts())
    assert gates["AUDITED_CALL_COVERAGE_PASS"] is False
