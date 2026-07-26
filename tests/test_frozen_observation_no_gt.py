from fastlio2_adapter.frozen_observation import (
    forbidden_field_paths,
    forbidden_topic_count,
)


def test_clean_record_has_no_forbidden_fields():
    assert forbidden_field_paths({"scan_index": 1, "rows": [1, 2]}) == []


def test_nested_ground_truth_field_is_rejected():
    assert forbidden_field_paths({"meta": {"pose_gt": [0, 0, 0]}})


def test_detector_and_future_fields_are_rejected():
    found = forbidden_field_paths(
        {"detector_output": {}, "future_scan": 2, "ODI": 0.1}
    )
    assert len(found) == 3


def test_gt_topic_scan_is_case_insensitive():
    assert forbidden_topic_count(["Subscriptions:\n * /VICON/Pose"]) == 1
    assert forbidden_topic_count(["Subscriptions:\n * /livox/imu"]) == 0
