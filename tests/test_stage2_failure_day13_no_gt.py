import pytest

from eval.stage2_failure_no_gt_audit import ForbiddenGTAccessError, GTAccessSentinelMapping


def test_gt_sentinel_hides_truth_and_counts_attempts():
    value = GTAccessSentinelMapping({"online": 1, "pose_gt": 2, "axis_per_frame": 3})
    assert list(value) == ["online"]
    with pytest.raises(ForbiddenGTAccessError):
        value["pose_gt"]
    assert value.access_attempt_count == 1
