import math
from pathlib import Path
from eval.stage2_failure_day12_plot_data import build_all_plot_data, read_merged_rows

ROOT = Path(__file__).resolve().parents[1]
MERGED = ROOT / "results/stage2_failure_analysis/day11b_replay/stage2_failure_day11b_replay_v2/replay_frame_diagnostics_merged.csv"


def test_figure4_uses_fixed_displacement_and_window_gate():
    fields, merged = read_merged_rows(MERGED)
    rows = build_all_plot_data(fields, merged)["day12_fig04_clean_stress_distributions"]
    for row in rows:
        assert math.isclose(float(row["deterministic_jitter"]), ((int(row["frame_index"]) % 7) - 3) * 0.035)
        if row["metric_name"] in {"abs_huber_window_mean", "abs_huber_cusum_signed"}:
            source = next(item for item in merged if item["case_id"] == row["case_id"] and item["frame_index"] == row["frame_index"])
            assert bool(row["included"]) == (source["window_ready"] == "True" and math.isfinite(float(row["metric_value"])))
