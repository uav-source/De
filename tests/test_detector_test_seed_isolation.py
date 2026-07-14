from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval.detector_stage2a import normalize_phase_config, validate_seed_contract  # noqa: E402
from eval.synthetic_pipeline_common import load_yaml  # noqa: E402


def test_development_and_reserved_test_seeds_are_disjoint():
    development = normalize_phase_config(
        load_yaml(ROOT / "configs/redesign/detector_stage2a_development.yaml")
    )
    test = normalize_phase_config(load_yaml(ROOT / "configs/redesign/detector_stage2a_test.yaml"))
    assert set(development["geometry_seeds"]).isdisjoint(test["geometry_seeds"])
    assert set(development["sensor_seeds"]).isdisjoint(test["sensor_seeds"])
    assert len(test["geometry_seeds"]) == 10
    assert test["sensor_seeds"] == [55, 66]
    assert test["expected_sensor_runs"] == 180


def test_test_phase_refuses_any_reserved_seed_change():
    config = normalize_phase_config(load_yaml(ROOT / "configs/redesign/detector_stage2a_test.yaml"))
    config["geometry_seeds"][0] = 9999
    with pytest.raises(RuntimeError, match="reserved geometry_seeds changed"):
        validate_seed_contract(ROOT, "test", config)
