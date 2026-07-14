from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval.detector_stage2a import build_specs, normalize_phase_config  # noqa: E402
from eval.synthetic_pipeline_common import load_yaml  # noqa: E402


def test_quick_contract_has_nine_detector_only_sensor_runs():
    common = load_yaml(ROOT / "configs/redesign/detector_stage2a_common.yaml")
    quick = normalize_phase_config(load_yaml(ROOT / "configs/redesign/detector_stage2a_quick.yaml"))
    specs = build_specs(common, quick["geometry_seeds"][0], "quick")
    assert len(specs) * len(quick["sensor_seeds"]) == quick["expected_sensor_runs"] == 9
    assert [spec["level"] for spec in specs] == [
        "OC", "L1", "L2", "L3", "L4", "O1", "O2", "O3", "O4"
    ]
    assert not any("process" in key for key in quick)
