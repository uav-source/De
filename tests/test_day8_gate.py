from fastlio2_adapter.day8_query_root_cause import evaluate_day8_gate


def _run():
    return {
        "day8_query_trace_validation_pass": True,
        "query_schema_error_count": 0,
        "overflow": {
            "query_summary_overflow": 0, "traversal_token_overflow": 0,
            "formal_result_member_overflow": 0,
            "point_voxel_pair_overflow": 0, "schema_error_count": 0,
        },
    }


def test_gate_requires_four_runs_six_pairs_synthetic_and_static_pass():
    passed = evaluate_day8_gate(
        [_run() for _ in range(4)], [{} for _ in range(6)],
        synthetic_pass=True, static_logic_unchanged=True,
    )
    assert passed["day8_execution_pass"] is True
    assert passed["shadow_replay_participates_in_fast_decisions"] is False
    assert passed["day9_authorized"] is False
    failed = evaluate_day8_gate(
        [_run() for _ in range(4)], [{} for _ in range(5)],
        synthetic_pass=True, static_logic_unchanged=True,
    )
    assert failed["day8_execution_pass"] is False
