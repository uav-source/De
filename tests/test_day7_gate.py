from fastlio2_adapter.day7_map_update_root_cause import evaluate_day7_gate


REQUIRED = {
    name: True
    for name in (
        "day7_authorization_identity_pass",
        "day7_source_path_resolution_pass",
        "day7_outcome_taxonomy_pass",
        "fast_build_pass",
        "fast_test_pass",
        "degen_targeted_test_pass",
        "degen_full_test_pass",
        "formal_fast_logic_unchanged_pass",
        "diagnostic_readonly_scope_pass",
        "day7_synthetic_trace_validation_pass",
        "four_replay_runs_complete_pass",
        "map_mutation_event_capture_pass",
        "rebuild_logger_trace_pass",
        "rebuild_commit_trace_pass",
        "map_point_identity_snapshot_pass",
        "event_trace_overflow_pass",
        "event_trace_schema_pass",
        "map_delta_accounting_pass",
        "map_point_symmetric_difference_pass",
        "six_pair_event_comparison_pass",
        "previous_event_identity_check_complete",
        "offline_analysis_lock_pass",
        "diff_scope_pass",
        "audit_package_scope_pass",
    )
}


def pair(classification="DIRECT_TREE_INSERTION_OUTCOME_DIVERGED"):
    return {
        "map_insertion_divergence_reproduced": True,
        "root_cause_classification": classification,
        "event_explains_symmetric_difference": True,
        "previous_event_identity_equal": True,
    }


def test_all_gates_and_explained_event_pass():
    result = evaluate_day7_gate(REQUIRED, [pair()])
    assert result["day7_execution_pass"] is True
    assert result["map_update_root_cause_localized"] is True
    assert result["day8_recommended"] is True
    assert result["day8_authorized"] is False


def test_overflow_or_missing_gate_fails():
    gates = dict(REQUIRED)
    gates["event_trace_overflow_pass"] = False
    result = evaluate_day7_gate(gates, [pair()])
    assert result["day7_execution_pass"] is False
    assert result["day7_map_update_rebuild_root_cause_pass"] is False


def test_unexplained_symmetric_difference_fails_root_cause():
    value = pair()
    value["event_explains_symmetric_difference"] = False
    result = evaluate_day7_gate(REQUIRED, [value])
    assert result["map_after_delta_explained_pass"] is False
    assert result["map_update_root_cause_localized"] is False


def test_multiple_modes_reported_without_authorizing_day8():
    result = evaluate_day7_gate(REQUIRED, [
        pair(),
        pair("REBUILD_LOGGER_APPLICATION_ORDER_DIVERGED"),
    ])
    assert result["multiple_map_update_divergence_modes"] is True
    assert result["day8_authorized"] is False
    assert result["data_race_proven"] is False
    assert result["formal_ikdtree_bug_proven"] is False
