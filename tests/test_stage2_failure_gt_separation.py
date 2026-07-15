import inspect
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


def test_online_logging_runs_without_ground_truth_and_offline_evaluation_fails_separately():
    observations = simple_observations()
    logger = Stage2FailureOnlineLogger(_context())
    output = run_map_lio(
        observations,
        simple_motion(),
        detector_config(),
        update_config(),
        "huber_full",
        0.2,
        0.9,
        failure_logger=logger,
    )
    assert len(logger.records) == observations["timestamps"].size - 1
    assert output["solver_failure_count"] == 0

    with pytest.raises((KeyError, ValueError)):
        evaluate_gt_frame_records(
            logger.records,
            output["prior_poses"],
            output["poses"],
            observations["pose_gt"],
            observations["axis_per_frame"],
        )
