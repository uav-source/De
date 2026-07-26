import copy

from fastlio2_adapter.contract_aware_direct_comparison import (
    REMEDIATION_FALSE_BOUNDARIES,
    REMEDIATION_REQUIRED_GATES,
    REMEDIATION_ZERO_COUNTS,
    evaluate_remediation_gate,
)


def passing_facts():
    facts = {name: True for name in REMEDIATION_REQUIRED_GATES}
    facts.update({name: 0 for name in REMEDIATION_ZERO_COUNTS})
    facts.update({name: False for name in REMEDIATION_FALSE_BOUNDARIES})
    facts.update(
        {
            "fresh_process_run_count": 3,
            "per_run_input_count": [487, 487, 487],
            "per_run_adapter_output_count": [487, 487, 487],
            "per_run_direct_output_count": [487, 487, 487],
            "per_run_adapter_valid_count": [486, 486, 486],
            "per_run_adapter_invalid_count": [1, 1, 1],
            "per_run_direct_valid_count": [487, 487, 487],
            "per_run_direct_invalid_count": [0, 0, 0],
            "production_executed_domain_record_count": 486,
            "adapter_precondition_domain_record_count": 1,
        }
    )
    return facts


def test_complete_remediation_pass_does_not_authorize_day6():
    gates = evaluate_remediation_gate(passing_facts())
    assert gates["PRODUCTION_DETECTOR_DETERMINISM_ON_DIRECT_STREAM_PASS"] is True
    assert gates["ADAPTER_PIPELINE_DETERMINISM_PASS"] is True
    assert gates["FALLBACK_C_PASS"] is True
    assert gates["FULL_ADAPTER_PRODUCTION_CALL_COVERAGE_PASS"] is False
    assert gates["DAY6_QUICK_DIAGNOSTICS_AUTHORIZED"] is False
    assert (
        gates["REAL_REPLAY_FUNCTIONAL_STATISTICAL_TOLERANCE_AUTHORIZED"]
        is False
    )


def test_precondition_contract_failure_closes_gate():
    facts = passing_facts()
    facts["adapter_precondition_contract_mismatch_count"] = 1
    assert evaluate_remediation_gate(facts)["FALLBACK_C_PASS"] is False


def test_production_metric_mismatch_closes_gate():
    facts = passing_facts()
    facts["production_metric_equivalence_mismatch_count"] = 1
    assert evaluate_remediation_gate(facts)["FALLBACK_C_PASS"] is False


def test_identity_or_schema_change_closes_gate():
    for field in (
        "PRODUCTION_DETECTOR_IDENTITY_PASS",
        "FROZEN_INPUT_IDENTITY_PASS",
        "ADAPTER_GUARD_UNCHANGED_PASS",
        "OUTPUT_SCHEMA_PASS",
    ):
        facts = copy.deepcopy(passing_facts())
        facts[field] = False
        assert evaluate_remediation_gate(facts)["FALLBACK_C_PASS"] is False


def test_ros_fast_or_labeled_split_closes_gate():
    for field in (
        "roscore_run",
        "roslaunch_run",
        "rosbag_run",
        "fastlio2_run",
        "development_run",
        "holdout_run",
        "future_test_run",
    ):
        facts = copy.deepcopy(passing_facts())
        facts[field] = True
        assert evaluate_remediation_gate(facts)["FALLBACK_C_PASS"] is False
