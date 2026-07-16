from pathlib import Path

from eval.stage2_failure_day12_input_audit import EXTERNAL_KEY, _stress_audit
from eval.stage2_failure_day12_plot_data import read_merged_rows

ROOT = Path(__file__).resolve().parents[1]
MERGED = ROOT / "results/stage2_failure_analysis/day11b_replay/stage2_failure_day11b_replay_v2/replay_frame_diagnostics_merged.csv"


def test_method_expanded_and_external_counts_are_distinct():
    audit = _stress_audit(read_merged_rows(MERGED)[1])
    assert audit["method_expanded_contaminated_measurement_count"] == 872
    assert audit["external_unique_contaminated_measurement_count"] == 436
    assert audit["method_expanded_stress_active_frame_count"] == 80
    assert audit["external_unique_stress_active_frame_count"] == 40


def test_external_deduplication_key_excludes_method():
    assert "method" not in EXTERNAL_KEY
