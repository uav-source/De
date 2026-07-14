from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval.metric_redesign_stage1b import build_preregistration, load_yaml, write_frozen_json  # noqa: E402
from stage1b_helpers import stage1b_paths  # noqa: E402


def test_preregistration_is_frozen_and_test_seeds_cannot_rewrite_it(tmp_path):
    common = load_yaml(stage1b_paths()["common"])
    prereg = build_preregistration(common, "config-hash", "commit")
    assert prereg["primary_metric"] == "mean_inverse_axis_information"
    assert prereg["test_seeds"] == [404, 505]
    path = tmp_path / "preregistered_analysis.json"
    write_frozen_json(path, prereg, resume=False)
    changed = dict(prereg)
    changed["epsilon"] = 99.0
    with pytest.raises(ValueError):
        write_frozen_json(path, changed, resume=True)
