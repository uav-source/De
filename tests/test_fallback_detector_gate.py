import copy

from fastlio2_adapter.offline_detector_determinism import evaluate_gate


def passing_facts():
    facts = {
        name: True
        for name in (
            "FROZEN_INPUT_IDENTITY_PASS",
            "PRODUCTION_DETECTOR_IDENTITY_PASS",
            "PRODUCTION_DETECTOR_ENTRYPOINT_CONFIRMED",
            "OBSERVATION_SCHEMA_REUSE_PASS",
            "DETECTOR_OUTPUT_SCHEMA_REUSE_PASS",
            "THIN_ADAPTER_PASS",
            "JACOBIAN_NO_DOUBLE_REORDER_PASS",
            "VARIANCE_MAPPING_PASS",
            "PRIOR_COVARIANCE_NOT_USED_PASS",
            "RESIDUAL_NOT_USED_BY_DETECTOR_CONFIRMED",
            "DIRECT_PRODUCTION_EQUIVALENCE_PASS",
            "INPUT_IMMUTABILITY_PASS",
            "OUTPUT_COUNT_COMPLETENESS_PASS",
            "OUTPUT_SCHEMA_PASS",
            "NO_GT_PASS",
            "DETECTOR_ARTIFACT_IMMUTABILITY_PASS",
            "FRESH_PROCESS_RUN_COMPLETENESS_PASS",
            "PER_RECORD_CHECKSUM_DETERMINISM_PASS",
            "CANONICAL_JSON_BYTE_DETERMINISM_PASS",
            "WHOLE_FILE_SHA_DETERMINISM_PASS",
            "DEGEN_TARGETED_TEST_PASS",
            "DEGEN_FULL_TEST_PASS",
            "DIFF_SCOPE_PASS",
        )
    }
    for name in (
        "missing_output_count",
        "duplicate_output_count",
        "schema_rejected_output_count",
        "detector_exception_count",
        "input_mutation_count",
        "direct_equivalence_mismatch_count",
        "per_record_checksum_mismatch_count",
        "json_line_mismatch_count",
        "whole_file_sha_mismatch_count",
        "forbidden_field_count",
        "gt_topic_consumed_count",
    ):
        facts[name] = 0
    for name in (
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
        "commit_created",
        "push_performed",
    ):
        facts[name] = False
    facts["fresh_process_run_count"] = 3
    facts["per_run_input_count"] = [487, 487, 487]
    facts["per_run_output_count"] = [487, 487, 487]
    return facts


def test_all_fallback_c_gates_pass_without_authorizing_day6():
    gates = evaluate_gate(passing_facts())
    assert gates["OFFLINE_PRODUCTION_DETECTOR_DETERMINISM_PASS"] is True
    assert gates["FALLBACK_C_PASS"] is True
    assert gates["DAY6_FALLBACK_FUNCTIONAL_DIAGNOSTICS_RECOMMENDED"] is True
    assert gates["DAY6_QUICK_DIAGNOSTICS_AUTHORIZED"] is False
    assert (
        gates["REAL_REPLAY_FUNCTIONAL_STATISTICAL_TOLERANCE_AUTHORIZED"]
        is False
    )


def test_any_required_gate_failure_closes_fallback_c():
    facts = passing_facts()
    facts["DIRECT_PRODUCTION_EQUIVALENCE_PASS"] = False
    gates = evaluate_gate(facts)
    assert gates["OFFLINE_PRODUCTION_DETECTOR_DETERMINISM_PASS"] is False
    assert gates["FALLBACK_C_PASS"] is False
    assert gates["DAY6_FALLBACK_FUNCTIONAL_DIAGNOSTICS_RECOMMENDED"] is False


def test_any_count_failure_closes_fallback_c():
    facts = passing_facts()
    facts["input_mutation_count"] = 1
    assert evaluate_gate(facts)["FALLBACK_C_PASS"] is False


def test_ros_or_fast_execution_closes_fallback_c():
    for field in ("roscore_run", "roslaunch_run", "rosbag_run", "fastlio2_run"):
        facts = copy.deepcopy(passing_facts())
        facts[field] = True
        assert evaluate_gate(facts)["FALLBACK_C_PASS"] is False


def test_three_complete_runs_are_mandatory():
    facts = passing_facts()
    facts["fresh_process_run_count"] = 2
    assert evaluate_gate(facts)["FALLBACK_C_PASS"] is False
