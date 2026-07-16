from pathlib import Path
from eval.stage2_failure_day12_plot_data import build_all_plot_data, read_merged_rows

ROOT = Path(__file__).resolve().parents[1]
MERGED = ROOT / "results/stage2_failure_analysis/day11b_replay/stage2_failure_day11b_replay_v2/replay_frame_diagnostics_merged.csv"


def test_figure3_uses_current_run_and_retains_max_only_for_audit():
    fields, merged = read_merged_rows(MERGED)
    rows = build_all_plot_data(fields, merged)["day12_fig03_same_sign_run_timeline"]
    assert "huber_current_same_sign_run_length" in rows[0]
    assert "huber_max_same_sign_run_length" in rows[0]
    assert any(row["huber_current_same_sign_run_length"] != row["huber_max_same_sign_run_length"] for row in rows)
