from pathlib import Path

from eval.synthetic_pipeline_common import load_yaml


ROOT = Path(__file__).resolve().parents[1]


def test_gross_control_is_read_from_frozen_stage2c_config():
    config = load_yaml(ROOT / "configs/update/stage2c_stress.yaml")
    gross = config["stress_regimes"]["gross_outlier_control"]
    assert gross["slip_sigma"] == 4.0
    assert gross["burst_length_frames"] == 8
