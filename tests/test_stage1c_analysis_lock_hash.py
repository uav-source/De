from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval.analysis_lock import compute_source_tree_hash  # noqa: E402


def test_source_hash_changes_for_source_but_not_unrelated_log(tmp_path):
    source = tmp_path / "src"
    source.mkdir()
    code = source / "metric.py"
    code.write_text("VALUE = 1\n", encoding="utf-8")
    first = compute_source_tree_hash([source])
    (tmp_path / "run.log").write_text("unrelated", encoding="utf-8")
    assert compute_source_tree_hash([source]) == first
    code.write_text("VALUE = 2\n", encoding="utf-8")
    assert compute_source_tree_hash([source]) != first
