from pathlib import Path

import pytest

from eval.stage2_failure_day8 import build_day8_unit_fixture
from eval.stage2_failure_no_gt_audit import (
    ForbiddenGTAccessError,
    GTAccessSentinelMapping,
    execute_online_variant,
)
from eval.synthetic_pipeline_common import load_yaml


ROOT = Path(__file__).resolve().parents[1]


def test_gt_access_sentinel_hides_gt_from_iteration_and_blocks_explicit_access():
    observations, _ = build_day8_unit_fixture(8)
    sentinel = GTAccessSentinelMapping(observations)
    assert "pose_gt" not in list(iter(sentinel))
    assert "axis_per_frame" not in dict(sentinel)
    assert all(name not in {"pose_gt", "axis_per_frame"} for name, _ in sentinel.items())
    with pytest.raises(ForbiddenGTAccessError):
        sentinel["pose_gt"]
    with pytest.raises(ForbiddenGTAccessError):
        sentinel.get("axis_per_frame")
    with pytest.raises(ForbiddenGTAccessError):
        "pose_gt" in sentinel
    assert sentinel.accessed_fields == ("pose_gt", "axis_per_frame", "pose_gt")


def test_normal_online_run_makes_zero_gt_access_attempts():
    observations, motion = build_day8_unit_fixture(8)
    sentinel = GTAccessSentinelMapping(observations)
    day8 = load_yaml(ROOT / "configs/stage2_failure/day8_quick.yaml")
    execute_online_variant(
        sentinel,
        motion,
        load_yaml(ROOT / "configs/detector/odi_stage2a.yaml"),
        load_yaml(ROOT / "configs/update/stage2c_common.yaml"),
        ["huber_full"],
        day8["online_odi_threshold"],
        day8["attenuation_alpha"],
        {
            "run_id": "sentinel",
            "sequence_id": "fixture",
            "sweep": "quick",
            "level": "unit",
            "stress": "no_gt",
            "geometry_seed": 1,
            "sensor_seed": 2,
            "process_seed": 3,
        },
        day8["directional_information_epsilon"],
    )
    assert sentinel.access_attempt_count == 0
