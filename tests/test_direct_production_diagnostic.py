import copy

from fastlio2_adapter.canonical_detector_output import canonical_json_line
from fastlio2_adapter.direct_production_diagnostic import (
    direct_output_checksum,
    evaluate_direct_production,
    validate_direct_production_output,
)
from fastlio2_adapter.offline_detector_determinism import (
    evaluate_frozen_observation,
    input_component_identity,
)
from test_adapter_precondition_domain import record_with_rows


def test_five_by_six_direct_production_is_finite_and_structured():
    record = record_with_rows(5)
    output = evaluate_direct_production(record, record_index=284)
    assert output["valid"] is True
    assert output["invalid_reason"] == "NONE"
    assert output["jacobian_row_count"] == 5
    assert output["jacobian_column_count"] == 6
    validate_direct_production_output(output)


def test_direct_diagnostic_does_not_modify_adapter_output():
    record = record_with_rows(5)
    adapter = evaluate_frozen_observation(record, record_index=284)
    before = copy.deepcopy(adapter)
    evaluate_direct_production(record, record_index=284)
    assert adapter == before


def test_direct_diagnostic_does_not_modify_input():
    record = record_with_rows(5)
    before = input_component_identity(record)
    evaluate_direct_production(record, record_index=284)
    assert input_component_identity(record) == before


def test_direct_output_canonical_checksum_is_self_excluding():
    record = record_with_rows(5)
    output = evaluate_direct_production(record, record_index=284)
    assert output["direct_output_checksum"] == direct_output_checksum(output)
    first = canonical_json_line(output)
    second = canonical_json_line(
        evaluate_direct_production(record, record_index=284)
    )
    assert first == second


def test_direct_diagnostic_contains_no_process_identity():
    output = evaluate_direct_production(record_with_rows(5), record_index=284)
    for forbidden in (
        "fresh_process_run_id",
        "wall_time",
        "runtime_ns",
        "pid",
        "hostname",
        "created_at",
    ):
        assert forbidden not in output
