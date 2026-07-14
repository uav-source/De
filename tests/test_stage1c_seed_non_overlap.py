from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval.metric_redesign_stage1c import normalize_phase_config  # noqa: E402
from eval.metric_redesign_stage1b import load_yaml  # noqa: E402
from stage1c_helpers import paths  # noqa: E402


def test_development_and_reserved_test_seeds_are_disjoint():
    development = normalize_phase_config(load_yaml(paths()["development"]))
    test = normalize_phase_config(load_yaml(paths()["test"]))
    for field in ["geometry_seeds", "sensor_seeds", "process_seeds"]:
        assert not (set(development[field]) & set(test[field]))
