from pathlib import Path

from eval.stage2_failure_day8 import build_day8_unit_fixture
from eval.stage2_failure_no_gt_audit import (
    compare_online_runs,
    execute_online_variant,
    permute_gt_observations,
)
from eval.synthetic_pipeline_common import load_yaml


ROOT = Path(__file__).resolve().parents[1]


def _run(observations):
    _, motion = build_day8_unit_fixture(8)
    day8 = load_yaml(ROOT / "configs/stage2_failure/day8_quick.yaml")
    return execute_online_variant(
        observations,
        motion,
        load_yaml(ROOT / "configs/detector/odi_stage2a.yaml"),
        load_yaml(ROOT / "configs/update/stage2c_common.yaml"),
        ["huber_full"],
        day8["online_odi_threshold"],
        day8["attenuation_alpha"],
        {
            "run_id": "permuted_gt",
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


def test_permuted_gt_does_not_change_online_outputs():
    observations, _ = build_day8_unit_fixture(8)
    permuted = permute_gt_observations(observations)
    control = _run(observations)
    candidate = _run(permuted)
    rows = compare_online_runs("gt_permuted", control, candidate, 1.0e-12)
    assert all(row["pass"] for row in rows)
