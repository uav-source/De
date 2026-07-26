import copy

from fastlio2_adapter.contract_aware_direct_comparison import (
    ADAPTER_PRECONDITION_DOMAIN,
    NOT_APPLICABLE,
    PRODUCTION_EXECUTED_DOMAIN,
    classify_direct_equivalence_domain,
    compare_contract_record,
    validate_adapter_precondition_contract,
)
from fastlio2_adapter.direct_production_diagnostic import (
    evaluate_direct_production,
)
from fastlio2_adapter.offline_detector_determinism import (
    evaluate_frozen_observation,
)
from test_runtime_observation_v3 import v3_record


def record_with_rows(count):
    record = v3_record()
    rows = record["detector_pose_jacobian_rows"]
    residual = record["formal_filter_innovation_h"]
    if count <= len(rows):
        record["detector_pose_jacobian_rows"] = rows[:count]
        record["formal_filter_innovation_h"] = residual[:count]
    else:
        while len(rows) < count:
            rows.append(copy.deepcopy(rows[-1]))
            residual.append(float(residual[-1]))
    record["valid_correspondence_count"] = count
    return record


def test_six_by_six_is_production_domain():
    record = record_with_rows(6)
    assert classify_direct_equivalence_domain(record, {}) == (
        PRODUCTION_EXECUTED_DOMAIN
    )


def test_seven_by_six_is_production_domain():
    record = record_with_rows(7)
    assert classify_direct_equivalence_domain(record, {}) == (
        PRODUCTION_EXECUTED_DOMAIN
    )


def test_five_by_six_is_precondition_domain_independent_of_index():
    record = record_with_rows(5)
    record["scan_index"] = 999
    assert classify_direct_equivalence_domain(record, {}) == (
        ADAPTER_PRECONDITION_DOMAIN
    )


def test_five_by_six_adapter_contract_remains_frozen():
    record = record_with_rows(5)
    adapter = evaluate_frozen_observation(record, record_index=284)
    assert adapter["valid"] is False
    assert adapter["invalid_reason"] == "TOO_FEW_CORRESPONDENCES"
    assert validate_adapter_precondition_contract(adapter) == {
        "pass": True,
        "mismatched_fields": [],
    }


def test_precondition_domain_does_not_require_metric_equivalence():
    record = record_with_rows(5)
    adapter = evaluate_frozen_observation(record, record_index=284)
    direct = evaluate_direct_production(record, record_index=284)
    comparison = compare_contract_record(record, adapter, direct)
    assert direct["valid"] is True
    assert comparison["equivalence_domain"] == ADAPTER_PRECONDITION_DOMAIN
    assert comparison["metric_comparison_required"] is False
    assert comparison["metric_equivalence_pass"] == NOT_APPLICABLE
    assert comparison["precondition_contract_pass"] is True


def test_precondition_contract_failure_is_detected():
    record = record_with_rows(5)
    adapter = evaluate_frozen_observation(record, record_index=284)
    direct = evaluate_direct_production(record, record_index=284)
    adapter["invalid_reason"] = "NONE"
    comparison = compare_contract_record(record, adapter, direct)
    assert comparison["precondition_contract_pass"] is False
    assert comparison["metric_equivalence_pass"] == NOT_APPLICABLE


def test_production_metric_mismatch_is_detected():
    record = record_with_rows(6)
    adapter = evaluate_frozen_observation(record, record_index=0)
    direct = evaluate_direct_production(record, record_index=0)
    direct["odi_trans"] += 1.0e-9
    comparison = compare_contract_record(record, adapter, direct)
    assert comparison["metric_equivalence_pass"] is False
    assert comparison["mismatched_fields"] == ["odi_trans"]
