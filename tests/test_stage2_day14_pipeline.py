import json
from pathlib import Path

from eval import stage2_day14_decision as day14


ROOT = Path(__file__).resolve().parents[1]
DAY13_V2 = ROOT / "artifacts/current/stage2_day13_analysis_correction_v2"


def test_frozen_evidence_pipeline_is_reproducible_and_fails_stage2(tmp_path, monkeypatch):
    monkeypatch.setattr(day14, "_git_worktree_clean", lambda root: True)
    first = day14.finalize_stage2_day14(
        ROOT, ROOT / "configs/stage2/day14_decision.yaml", DAY13_V2,
        tmp_path / "first", report_path=tmp_path / "first_report.md",
    )
    second = day14.finalize_stage2_day14(
        ROOT, ROOT / "configs/stage2/day14_decision.yaml", DAY13_V2,
        tmp_path / "second", report_path=tmp_path / "second_report.md",
    )
    for name in (
        "stage2_gate_summary.json", "stage2_metric_summary.csv",
        "stage2_evidence_index.csv", "stage2_final_decision.md",
        "stage2_transition_plan.md",
    ):
        assert (tmp_path / "first" / name).read_bytes() == (
            tmp_path / "second" / name
        ).read_bytes()
    gate = first["gate_summary"]
    assert gate["SEPARABILITY_GATE"] == "FAIL"
    assert gate["CROSS_GEOMETRY_GATE"] == "PASS"
    assert gate["CAUSAL_CONSISTENCY_GATE"] == "FAIL"
    assert gate["NO_GT_GATE"] == "PASS"
    assert gate["STAGE2_GATE"] == "FAIL"
    assert gate["COHERENT_BIAS_HARMFUL_MECHANISM_SUPPORTED"] is True
    assert gate["COHERENT_BIAS_STABLY_ONLINE_DETECTABLE"] is False
    assert first["manifest"]["DAY14_DECISION_PASS"] is True
    assert first["manifest"]["STAGE2_GATE"] == "FAIL"
