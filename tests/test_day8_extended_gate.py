from fastlio2_adapter.day8_extended_token_window import (
    evaluate_extended_gate,
)


FIELDS = (
    "authorization_pass",
    "targeted_test_pass",
    "full_test_pass",
    "synthetic_pass",
    "fast_source_lock_pass",
    "fast_binary_lock_pass",
    "formal_logic_unchanged_pass",
    "four_replay_runs_complete_pass",
    "observation_binary_integrity_pass",
    "map_snapshot_coherence_pass",
    "day7_mutation_trace_reuse_pass",
    "range_query_summary_capture_pass",
    "range_traversal_token_capture_pass",
    "scan157_token_coverage_pass",
    "scan162_token_coverage_pass",
    "query_trace_overflow_pass",
    "query_trace_schema_pass",
    "shadow_logical_voxel_replay_pass",
    "shadow_state_accounting_pass",
    "six_pair_range_query_comparison_pass",
    "previous_query_identity_check_complete",
    "first_divergent_query_detailed_token_coverage_pass",
    "missing_expected_point_witness_pass",
    "root_cause_classification_complete",
    "null_token_semantics_fully_propagated_pass",
    "offline_analysis_lock_pass",
    "diagnostic_immutability_pass",
    "no_tap_drop_pass",
    "no_writer_error_pass",
    "no_gt_pass",
    "diff_scope_pass",
    "audit_package_scope_pass",
)


def test_all_required_checks_pass_but_day9_is_not_authorized():
    gate = evaluate_extended_gate(**{field: True for field in FIELDS})
    assert gate["DAY8_EXTENDED_TOKEN_WINDOW_EXECUTION_PASS"] is True
    assert gate["DAY9_AUTHORIZED"] is False
    assert gate["FORMAL_IKDTREE_BUG_PROVEN"] is False
    assert gate["DATA_RACE_PROVEN"] is False


def test_one_failed_check_fails_execution():
    values = {field: True for field in FIELDS}
    values["scan162_token_coverage_pass"] = False
    gate = evaluate_extended_gate(**values)
    assert gate["DAY8_EXTENDED_TOKEN_WINDOW_EXECUTION_PASS"] is False
