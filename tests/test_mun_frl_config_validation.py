from pathlib import Path

import pytest
import yaml

from fastlio2_adapter.mun_frl_contract import validate_mun_frl_config


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/real_data/mun_frl_lighthouse.yaml"


def _config():
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def test_checked_in_mun_frl_fastlio2_config_matches_frozen_contract():
    validate_mun_frl_config(_config())


@pytest.mark.parametrize(
    "section,key,bad_value",
    [
        ("preprocess", "scan_line", 32),
        ("preprocess", "timestamp_unit", 2),
        ("common", "time_sync_en", True),
        ("common", "time_offset_lidar_to_imu", 0.0),
    ],
)
def test_mun_frl_config_rejects_known_incompatible_values(
    section, key, bad_value
):
    config = _config()
    config[section][key] = bad_value
    with pytest.raises(ValueError):
        validate_mun_frl_config(config)


def test_bag_path_is_runtime_configurable_not_machine_hardcoded():
    dataset = _config()["dataset"]
    assert dataset["bag_argument"] == "--bag"
    assert dataset["bag_environment_variable"] == "MUN_FRL_BAG"
    assert "/home/" not in CONFIG_PATH.read_text(encoding="utf-8")

