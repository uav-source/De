import pytest

from fastlio2_adapter.day8_final_plot_contract import (
    PLOT_INPUT_SCHEMA_VERSION,
    validate_plot_inputs,
)


def documents():
    pair = {
        "left_run_id": "r1",
        "right_run_id": "r2",
        "left_identity_count": 1,
        "right_identity_count": 1,
        "common_identity_count": 1,
        "aligned_prefix_length": 1,
        "strict_identity_formal_member_set_divergence_count": 0,
        "formal_result_order_only_divergence_count": 0,
        "root_cause_classification":
            "NO_STRICT_IDENTITY_FORMAL_RESULT_DIVERGENCE_REPRODUCED",
    }
    return {
        "pairwise_final_query_comparison": [],
        "pairwise_final_strict_identity_summary": {
            "pair_count": 6, "pairs": [dict(pair) for _ in range(6)]
        },
        "pairwise_final_first_divergence": {"pairs": []},
        "pairwise_final_root_cause_classification": {"pairs": []},
        "root_cause_summary": {
            "root_cause_classification":
                "NO_STRICT_IDENTITY_FORMAL_RESULT_DIVERGENCE_REPRODUCED",
            "first_strict_formal_member_set_divergence": None,
            "first_divergent_traversal_token": None,
            "missing_expected_point_witness": None,
        },
        "token_coverage": {
            "runs": {}, "FULL_WINDOW_DETAILED_TOKEN_COVERAGE_PASS": True
        },
        "shadow_accounting": {
            "runs": {}, "SHADOW_STATE_ACCOUNTING_PASS": True
        },
        "instrumentation_cost": {
            "runs": {}, "instrumentation_timing_perturbation_present": True
        },
        "null_token_contract_audit": {
            "failure_count": 0,
            "NULL_TOKEN_SEMANTICS_FULLY_PROPAGATED_PASS": True,
        },
        "random_replay_route_decision": {
            "RANDOM_REAL_REPLAY_ROUTE_STATUS":
                "CLOSED_AFTER_FINAL_FULL_WINDOW_BATCH",
            "FURTHER_RANDOM_REAL_REPLAY_AUTHORIZED": False,
        },
    }


def test_formal_plot_contract_passes_without_alternate_input():
    value = validate_plot_inputs(documents())
    assert value["schema_version"] == PLOT_INPUT_SCHEMA_VERSION
    assert value["uses_formal_analysis_outputs_only"]
    assert not value["alternate_scientific_input_used"]


def test_missing_scientific_document_fails_closed():
    value = documents()
    value.pop("token_coverage")
    with pytest.raises(ValueError):
        validate_plot_inputs(value)
