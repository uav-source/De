from pathlib import Path

from eval.synthetic_pipeline_common import load_yaml
from eval.weak_update_stage2b import METHODS, build_stage2b_specs, normalize_phase_config


ROOT = Path(__file__).resolve().parents[1]


def test_quick_pipeline_contract_has_all_scenes_stresses_and_methods():
    common = load_yaml(ROOT / "configs/update/stage2b_common.yaml")
    quick = normalize_phase_config(load_yaml(ROOT / "configs/update/stage2b_quick.yaml"))
    specs = build_stage2b_specs(common, quick["geometry_seeds"][0], "quick")
    assert len(specs) == 9
    assert {spec["level"] for spec in specs} == {"OC", "L1", "L2", "L3", "L4", "O1", "O2", "O3", "O4"}
    assert common["stress_names"] == ["clean", "axial_correspondence_slip"]
    assert METHODS == common["method_list"]
    assert quick["expected_sensor_stress_blocks"] == 18
    assert quick["expected_method_trials"] == 180

