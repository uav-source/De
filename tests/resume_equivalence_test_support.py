from __future__ import annotations

import copy

from phase_a_execution_chain_test_support import sample_result


def result_pair():
    value = sample_result()
    return copy.deepcopy(value), copy.deepcopy(value)


def analysis_output():
    return {
        "attempt_event_count": 12,
        "backend_inventory": [{"backend": "open3d_point_to_plane", "failure_count": 0, "success_count": 3, "trial_count": 3}],
        "decision": {"PHASE_A_EXECUTION_CHAIN_FIXTURE_PASS": True},
        "failure_inventory": [{"count": 6, "failure_classification": "NONE"}],
        "input_pairing_audit": [{"checksum_match": True}],
        "rotation_summary": [{"backend": "open3d_point_to_plane", "count": 3, "maximum": 0.0, "median": 0.0, "q95_linear": 0.0}],
        "runtime_summary": [{"backend": "open3d_point_to_plane", "count": 3, "maximum": 2.0, "median": 1.0, "q95_linear": 1.9}],
        "snapshot_ids": ["a", "b", "c"],
        "translation_summary": [{"backend": "open3d_point_to_plane", "count": 3, "maximum": 0.0, "median": 0.0, "q95_linear": 0.0}],
        "trial_count": 6,
        "trial_ids": [f"trial-{i}" for i in range(6)],
    }
