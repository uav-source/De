from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval.metric_redesign_stage1c import run_stage1c  # noqa: E402
from stage1c_helpers import paths  # noqa: E402


def test_reserved_test_pipeline_refuses_without_analysis_lock(tmp_path):
    with pytest.raises(RuntimeError, match="analysis-lock"):
        run_stage1c(ROOT, "test", "refuse", paths()["common"], paths()["test"], paths()["detector"], paths()["motion"])
