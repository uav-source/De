import numpy as np
import pytest

from eval.stage2_failure_no_gt_audit import ForbiddenGTAccessError, GTAccessSentinelMapping


def test_gt_sentinel_hides_ground_truth_and_records_forbidden_access():
    source = {
        "timestamps": np.array([0.0]),
        "pose_gt": np.zeros((1, 8)),
        "axis_per_frame": np.ones((1, 3)),
    }
    guarded = GTAccessSentinelMapping(source)
    assert list(guarded) == ["timestamps"]
    with pytest.raises(ForbiddenGTAccessError):
        guarded["pose_gt"]
    assert guarded.access_attempt_count == 1


def test_online_payload_with_no_gt_access_stays_at_zero_attempts():
    guarded = GTAccessSentinelMapping({"timestamps": np.array([0.0]), "pose_gt": np.zeros((1, 8))})
    np.testing.assert_array_equal(guarded["timestamps"], [0.0])
    assert guarded.access_attempt_count == 0
