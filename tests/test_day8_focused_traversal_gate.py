from fastlio2_adapter.day8_focused_traversal_remediation import (
    evaluate_focused_gate,
)


def test_focused_gate_is_conjunctive_and_never_authorizes_day9():
    names = (
        "authorization_pass shadow_adjudication_pass targeted_test_pass "
        "full_test_pass fast_source_lock_pass fast_binary_lock_pass "
        "formal_logic_unchanged_pass synthetic_pass run_complete_pass "
        "scan157_coverage_pass shadow_accounting_pass six_pair_pass "
        "previous_identity_pass first_divergence_coverage_pass witness_pass "
        "classification_complete offline_analysis_lock_pass immutable_pass "
        "no_tap_drop_pass no_writer_error_pass no_gt_pass diff_scope_pass "
        "audit_scope_pass"
    ).split()
    values = {name: True for name in names}
    passed = evaluate_focused_gate(**values)
    assert passed["DAY8_FOCUSED_TRAVERSAL_EXECUTION_PASS"] is True
    assert passed["DAY9_AUTHORIZED"] is False
    values["scan157_coverage_pass"] = False
    assert evaluate_focused_gate(
        **values
    )["DAY8_FOCUSED_TRAVERSAL_EXECUTION_PASS"] is False
