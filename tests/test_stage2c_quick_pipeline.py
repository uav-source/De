from pathlib import Path

from eval.synthetic_pipeline_common import load_yaml
from eval.weak_update_stage2c import METHODS, build_stage2c_specs, normalize_phase_config


ROOT = Path(__file__).resolve().parents[1]


def test_quick_contract_has_nine_scenes_three_stresses_and_five_methods():
    common = load_yaml(ROOT / "configs/update/stage2c_common.yaml")
    quick = normalize_phase_config(load_yaml(ROOT / "configs/update/stage2c_quick.yaml"))
    specs = build_stage2c_specs(common, quick["geometry_seeds"][0], "quick")
    assert len(specs) == 9
    assert {spec["level"] for spec in specs} == {
        "OC", "L1", "L2", "L3", "L4", "O1", "O2", "O3", "O4",
    }
    assert quick["stress_names"] == [
        "clean", "coherent_subhuber_slip", "gross_outlier_control",
    ]
    assert METHODS == common["method_list"]
    assert quick["expected_sensor_stress_blocks"] == 27
    assert quick["expected_method_trials"] == 270
