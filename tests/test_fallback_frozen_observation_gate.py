from fastlio2_adapter.frozen_observation import (
    REMEDIATION_REQUIRED_GATE_FIELDS,
    REQUIRED_GATE_FIELDS,
    evaluate_freeze_gate,
    evaluate_remediation_gate,
)


def facts():
    value = {name: True for name in REQUIRED_GATE_FIELDS}
    value.update(
        {
            "observation_record_count": 3,
            "schema_rejected_record_count": 0,
            "nonfinite_record_count": 0,
            "forbidden_field_count": 0,
            "gt_topic_consumed_count": 0,
            "tap_drop_count": 0,
            "writer_error_count": 0,
            "binary_checksum_failure_count": 0,
            "truncated_record_count": 0,
            "in_call_mutation_count": 0,
            "detector_called": False,
            "odi_computed": False,
            "development_run": False,
            "holdout_run": False,
            "future_test_run": False,
            "commit_created": False,
            "push_performed": False,
        }
    )
    return value


def test_all_gates_authorize_only_offline_determinism():
    gates = evaluate_freeze_gate(facts())
    assert gates["FROZEN_REAL_OBSERVATION_RECORD_PASS"] is True
    assert gates["OFFLINE_PRODUCTION_DETECTOR_DETERMINISM_AUTHORIZED"] is True
    assert gates["DAY6_QUICK_DIAGNOSTICS_AUTHORIZED"] is False


def test_zero_records_fail():
    value = facts()
    value["observation_record_count"] = 0
    assert evaluate_freeze_gate(value)[
        "FROZEN_REAL_OBSERVATION_RECORD_PASS"
    ] is False


def test_binary_checksum_error_fails():
    value = facts()
    value["binary_checksum_failure_count"] = 1
    assert evaluate_freeze_gate(value)["BINARY_INTEGRITY_PASS"] is True
    assert evaluate_freeze_gate(value)[
        "FROZEN_REAL_OBSERVATION_RECORD_PASS"
    ] is False


def test_lifecycle_gate_failure_fails():
    value = facts()
    value["LIFECYCLE_CONSISTENCY_PASS"] = False
    assert evaluate_freeze_gate(value)[
        "OFFLINE_PRODUCTION_DETECTOR_DETERMINISM_AUTHORIZED"
    ] is False


def test_detector_execution_fails_gate():
    value = facts()
    value["detector_called"] = True
    assert evaluate_freeze_gate(value)[
        "FROZEN_REAL_OBSERVATION_RECORD_PASS"
    ] is False


def remediation_facts():
    value = {name: True for name in REMEDIATION_REQUIRED_GATE_FIELDS}
    value.update(
        {
            "fastlio2_modified": False,
            "fastlio2_build_run": False,
            "fastlio2_test_run": False,
            "fastlio2_node_run": False,
            "roscore_run": False,
            "roslaunch_run": False,
            "rosbag_run": False,
            "real_data_reprocessed": False,
            "detector_called": False,
            "odi_computed": False,
            "weak_direction_computed": False,
            "development_run": False,
            "holdout_run": False,
            "future_test_run": False,
            "commit_created": False,
            "push_performed": False,
        }
    )
    return value


def test_fallback_c_requires_every_remediation_gate():
    facts = remediation_facts()
    assert evaluate_remediation_gate(facts)[
        "OFFLINE_PRODUCTION_DETECTOR_DETERMINISM_AUTHORIZED"
    ] is True
    facts["MAIN_AUDIT_CONTENT_PATH_PASS"] = False
    assert evaluate_remediation_gate(facts)[
        "OFFLINE_PRODUCTION_DETECTOR_DETERMINISM_AUTHORIZED"
    ] is False


def test_remediation_day6_stays_false():
    assert evaluate_remediation_gate(remediation_facts())[
        "DAY6_QUICK_DIAGNOSTICS_AUTHORIZED"
    ] is False
