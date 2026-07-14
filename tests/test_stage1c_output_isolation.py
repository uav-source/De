from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval.metric_redesign_stage1c import prepare_run_directories  # noqa: E402


def test_stage1c_phases_use_isolated_run_directories(tmp_path):
    sentinel = tmp_path / "results/metric_redesign_stage1c/development/dev/tables/sentinel.csv"
    sentinel.parent.mkdir(parents=True)
    sentinel.write_text("development", encoding="utf-8")
    prepare_run_directories(tmp_path / "data/metric_redesign_stage1c/quick/q", tmp_path / "results/metric_redesign_stage1c/quick/q", False, False)
    assert sentinel.read_text(encoding="utf-8") == "development"
