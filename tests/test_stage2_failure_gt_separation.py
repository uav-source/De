import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from eval.stage2_failure_gt_metrics import evaluate_gt_frame_records
from eval.stage2_failure_logging import Stage2FailureOnlineLogger
from eval.stage2_failure_schema import ONLINE_FIELDS
from minibench.map_lio import run_map_lio
from stage2c_helpers import detector_config, simple_motion, simple_observations, update_config


def _context():
    return {
        "run_id": "separation",
        "sequence_id": "online_only",
        "sweep": "quick",
        "level": "unit",
        "stress": "clean",
        "geometry_seed": 10,
        "sensor_seed": 11,
        "process_seed": 12,
        "method": "huber_full",
    }


def test_online_logger_signature_and_schema_have_no_offline_inputs():
    signature = inspect.signature(Stage2FailureOnlineLogger.log_frame)
    forbidden = {"pose_gt", "axis_per_frame", "gt_axis", "scene_label", "oracle_axis"}
    assert forbidden.isdisjoint(signature.parameters)
    assert all("gt" not in name.lower().split("_") for name in ONLINE_FIELDS)
    source = Path(inspect.getsourcefile(Stage2FailureOnlineLogger)).read_text(encoding="utf-8")
    assert "stage2_failure_gt_metrics" not in source


def test_removing_ground_truth_does_not_change_estimator_or_online_logging():
    observations_with_gt = simple_observations()
    frame_count = observations_with_gt["timestamps"].size
    pose_gt = np.zeros((frame_count, 8), dtype=float)
    pose_gt[:, 0] = observations_with_gt["timestamps"]
    pose_gt[:, 7] = 1.0
    observations_with_gt["pose_gt"] = pose_gt
    observations_with_gt["axis_per_frame"] = np.tile(
        np.array([1.0, 0.0, 0.0]),
        (frame_count, 1),
    )
    observations_without_gt = {
        name: value.copy()
        for name, value in observations_with_gt.items()
        if name not in {"pose_gt", "axis_per_frame"}
    }
    logger_with_gt = Stage2FailureOnlineLogger(_context())
    logger_without_gt = Stage2FailureOnlineLogger(_context())
    output_with_gt = run_map_lio(
        observations_with_gt,
        simple_motion(),
        detector_config(),
        update_config(),
        "huber_full",
        0.2,
        0.9,
        failure_logger=logger_with_gt,
    )
    output_without_gt = run_map_lio(
        observations_without_gt,
        simple_motion(),
        detector_config(),
        update_config(),
        "huber_full",
        0.2,
        0.9,
        failure_logger=logger_without_gt,
    )

    for name in [
        "prior_poses",
        "poses",
        "applied_deltas",
        "full_deltas",
        "covariances",
    ]:
        difference = np.max(
            np.abs(output_with_gt[name] - output_without_gt[name])
        )
        assert difference <= 1.0e-12
    np.testing.assert_array_equal(
        output_with_gt["detector_triggered"],
        output_without_gt["detector_triggered"],
    )
    np.testing.assert_array_equal(
        output_with_gt["actionable_direction"],
        output_without_gt["actionable_direction"],
    )
    assert json.dumps(
        list(logger_with_gt.records), sort_keys=True, allow_nan=True
    ) == json.dumps(
        list(logger_without_gt.records), sort_keys=True, allow_nan=True
    )

    gt_records = evaluate_gt_frame_records(
        logger_with_gt.records,
        output_with_gt["prior_poses"],
        output_with_gt["poses"],
        observations_with_gt["pose_gt"],
        observations_with_gt["axis_per_frame"],
    )
    assert len(gt_records) == frame_count - 1

    with pytest.raises(KeyError):
        evaluate_gt_frame_records(
            logger_without_gt.records,
            output_without_gt["prior_poses"],
            output_without_gt["poses"],
            observations_without_gt["pose_gt"],
            observations_without_gt["axis_per_frame"],
        )
