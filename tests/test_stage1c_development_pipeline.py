from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval.metric_redesign_stage1c import build_stage1c_specs, normalize_phase_config  # noqa: E402
from eval.synthetic_pipeline_common import load_yaml  # noqa: E402
from stage1c_helpers import paths  # noqa: E402


def test_development_schedule_has_ninety_sensor_runs():
    common = load_yaml(paths()["common"])
    development = normalize_phase_config(load_yaml(paths()["development"]))
    specs = build_stage1c_specs(common, development, "development")
    assert len(specs) == 45
    assert len(specs) * len(development["sensor_seeds"]) == 90
    assert len(specs) * len(development["sensor_seeds"]) * len(development["process_seeds"]) == 2700
    assert development["expected_unique_noise_sequences"] == 900
    assert 606 not in development["geometry_seeds"]
