import json
from pathlib import Path

import pytest

from eval.stage2_failure_deterministic_case import (
    HISTORICAL_TEST_EXECUTED_STRESS_REGIMES,
    STAGE2C_ALLOWED_STRESS_REGIMES,
    validate_stage2c_source_consistency,
)
from eval.stage2_failure_day11a import load_yaml, validate_day11a_config


ROOT = Path(__file__).resolve().parents[1]


def frozen_sources():
    test_config = load_yaml(ROOT / "configs/update/stage2c_test.yaml")
    manifest = json.loads(
        (ROOT / "artifacts/current/weak_update_stage2c/test_manifest.json").read_text()
    )
    lock = json.loads(
        (
            ROOT / "artifacts/current/weak_update_stage2c/locked/update_lock.json"
        ).read_text()
    )
    stress = load_yaml(ROOT / "configs/update/stage2c_stress.yaml")
    return test_config, manifest, lock, stress


def test_frozen_seed_and_stress_sources_are_consistent():
    value = validate_stage2c_source_consistency(*frozen_sources())
    assert value["seed_source_consistency_pass"] is True
    assert value["stress_source_validation_pass"] is True
    assert value["stage2c_allowed_stress_regimes"] == list(
        STAGE2C_ALLOWED_STRESS_REGIMES
    )
    assert value["historical_test_executed_stress_regimes"] == list(
        HISTORICAL_TEST_EXECUTED_STRESS_REGIMES
    )
    assert set(value["historical_test_executed_stress_regimes"]) < set(
        value["stage2c_allowed_stress_regimes"]
    )


@pytest.mark.parametrize(
    "target",
    ["config", "lock", "manifest_binding"],
)
def test_seed_source_mismatch_is_rejected(target):
    test_config, manifest, lock, stress = frozen_sources()
    if target == "config":
        test_config["geometry_seeds"][0] += 1
    elif target == "lock":
        lock["reserved_test_sensor_seeds"][0] += 1
    else:
        manifest["lock_verification"]["seed_isolation_matched"] = False
    with pytest.raises(ValueError):
        validate_stage2c_source_consistency(test_config, manifest, lock, stress)


def test_manifest_executed_stress_outside_lock_and_config_is_rejected():
    test_config, manifest, lock, stress = frozen_sources()
    manifest["executed_stress_regimes"] = ["clean", "unregistered_stress"]
    with pytest.raises(ValueError, match="executed stress"):
        validate_stage2c_source_consistency(test_config, manifest, lock, stress)


def test_manifest_executed_subset_need_not_equal_three_regime_allowed_set():
    test_config, manifest, lock, stress = frozen_sources()
    value = validate_stage2c_source_consistency(test_config, manifest, lock, stress)
    assert len(value["historical_test_executed_stress_regimes"]) == 2
    assert len(value["stage2c_allowed_stress_regimes"]) == 3


def test_legacy_stage2b_stress_name_is_rejected_not_aliased():
    test_config, manifest, lock, stress = frozen_sources()
    test_config["stress_names"] = ["clean", "axial_correspondence_slip"]
    with pytest.raises(ValueError, match="legacy Stage 2B"):
        validate_stage2c_source_consistency(test_config, manifest, lock, stress)


def test_gross_outlier_control_cannot_enter_day11b_replay_config():
    config = load_yaml(ROOT / "configs/stage2_failure/day11a_case_lock.yaml")
    config["required_replay_stress_regimes"].append("gross_outlier_control")
    with pytest.raises(ValueError, match="freezes|required_replay"):
        validate_day11a_config(config)
