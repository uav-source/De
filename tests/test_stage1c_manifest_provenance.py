from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval.metric_redesign_stage1c import append_analysis_history  # noqa: E402


def test_manifest_preserves_data_generation_and_appends_analysis(monkeypatch):
    manifest = {"data_generation": {"data_generation_git_commit": "old"}, "analysis_history": []}
    monkeypatch.setattr("eval.metric_redesign_stage1c.git_commit", lambda _root: "analysis")
    monkeypatch.setattr("eval.metric_redesign_stage1c.compute_source_tree_hash", lambda _paths: "hash")
    append_analysis_history(manifest, ROOT)
    assert manifest["data_generation"]["data_generation_git_commit"] == "old"
    assert manifest["analysis_history"][0]["analysis_git_commit"] == "analysis"
