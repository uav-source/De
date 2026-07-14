from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval.metric_redesign_stage1b import prepare_run_directories  # noqa: E402


def test_quick_directory_preparation_preserves_full_sentinel(tmp_path):
    sentinel = tmp_path / "results/metric_redesign_stage1b/full/run_a/tables/sentinel.csv"
    sentinel.parent.mkdir(parents=True)
    sentinel.write_text("immutable-full-result\n", encoding="utf-8")
    prepare_run_directories(
        tmp_path / "data/metric_redesign_stage1b/quick/run_q",
        tmp_path / "results/metric_redesign_stage1b/quick/run_q",
        resume=False,
        overwrite=False,
    )
    assert sentinel.read_text(encoding="utf-8") == "immutable-full-result\n"
