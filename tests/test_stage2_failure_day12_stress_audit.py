from pathlib import Path

from eval.stage2_failure_day12_input_audit import _stress_audit
from eval.stage2_failure_day12_plot_data import read_merged_rows

ROOT = Path(__file__).resolve().parents[1]
MERGED = ROOT / "results/stage2_failure_analysis/day11b_replay/stage2_failure_day11b_replay_v2/replay_frame_diagnostics_merged.csv"


def _rows():
    return list(read_merged_rows(MERGED)[1])


def test_saved_stress_has_two_contiguous_twenty_frame_bursts():
    audit = _stress_audit(_rows())
    assert audit["coherent_burst_count"] == 2
    assert audit["coherent_burst_lengths"] == [20, 20]
    assert audit["coherent_offset_abs_m"] == 0.03
    assert audit["coherent_shared_sign_pass"] is True


def test_broken_burst_is_rejected():
    rows = _rows()
    for row in rows:
        if row["stress"] == "coherent_subhuber_slip" and row["sweep"] == "geometry" and row["stress_active"] == "True":
            row["stress_active"] = "False"
            break
    assert _stress_audit(rows)["checks"]["burst_lengths"] is False


def test_wrong_offset_is_rejected():
    rows = _rows()
    for row in rows:
        if row["stress"] == "coherent_subhuber_slip" and row["stress_active"] == "True":
            row["contamination_offset_abs_mean_m"] = "0.02"
    assert _stress_audit(rows)["checks"]["offset"] is False
