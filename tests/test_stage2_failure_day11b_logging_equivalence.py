import copy

import numpy as np

from eval.stage2_failure_day11b_schema import compare_logging_runs
from eval.stage2_failure_no_gt_audit import FRAME_DIAGNOSTIC_FIELDS


def _result():
    diagnostic = {name: 0.0 for name in FRAME_DIAGNOSTIC_FIELDS}
    diagnostic.update({
        "frame_index": 1, "degeneracy_triggered": False,
        "primary_direction_stable": True, "actionable_direction": False,
    })
    return {
        "prior_poses": np.zeros((2, 8)), "poses": np.zeros((2, 8)),
        "applied_deltas": np.zeros((2, 6)), "full_deltas": np.zeros((2, 6)),
        "covariances": np.zeros((2, 6, 6)),
        "detector_triggered": np.zeros(2, dtype=bool),
        "actionable_direction": np.zeros(2, dtype=bool),
        "frame_diagnostics": [diagnostic], "failure_frame_records": [],
        "solver_failure_count": 0, "strategy": "huber_full",
    }


def test_identical_logging_runs_pass_with_exact_checksums():
    first = _result()
    second = copy.deepcopy(first)
    audit = compare_logging_runs("case", first, second, [])
    assert audit["pass"] is True
    assert audit["checksum_mismatch_count"] == 0


def test_trajectory_change_of_one_e_minus_11_is_rejected():
    first = _result()
    second = copy.deepcopy(first)
    second["poses"][1, 1] = 1.0e-11
    audit = compare_logging_runs("case", first, second, [])
    assert audit["pass"] is False
    assert audit["max_trajectory_difference"] == 1.0e-11


def test_covariance_and_delta_changes_are_rejected():
    for field, index in (("covariances", (1, 0, 0)), ("applied_deltas", (1, 0)), ("full_deltas", (1, 0))):
        first = _result()
        second = copy.deepcopy(first)
        second[field][index] = 1.0e-11
        assert compare_logging_runs("case", first, second, [])["pass"] is False
