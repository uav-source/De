import json
from pathlib import Path

from eval.stage2_failure_day12_schema import evaluate_day12_v3_gate


ROOT = Path(__file__).resolve().parents[1]
V2_MANIFEST = ROOT / "results/stage2_failure_analysis/day12_figures/stage2_failure_day12_figures_v2/run_manifest.json"


def _passing():
    values = json.loads(V2_MANIFEST.read_text(encoding="utf-8"))
    values.update({
        "DAY12_V3_AXIS_CONTRACT_PASS": True,
        "DAY12_V3_INPUT_LOCK_PASS": True,
        "day12_v2_result_tree_unchanged": True,
        "day11b_v2_result_tree_unchanged": True,
        "v2_v3_plot_data_byte_identical": True,
        "v2_v3_summary_byte_identical": True,
        "v2_v3_captions_byte_identical": True,
        "figure1_pixel_hash_equal_v2_v3": True,
        "figure2_pixel_hash_equal_v2_v3": True,
        "figure3_pixel_hash_changed_v2_v3": True,
        "figure4_pixel_hash_changed_v2_v3": True,
        "source_file_verification_count": 14,
        "provenance_source_rehash_count": 4,
        "source_file_hash_mismatch_count": 0,
        "source_file_missing_count": 0,
        "source_file_path_violation_count": 0,
        "source_file_symlink_count": 0,
        "source_file_schema_failure_count": 0,
        "axis_contract_comparison_count": 12,
        "axis_contract_failure_count": 0,
        "v2_v3_plot_data_value_mismatch_count": 0,
        "figure_change_failure_count": 0,
        "figure3_ylim_lower": 0.0,
        "figure3_ylim_upper": 5.0,
        "figure3_actual_run_max": 5.0,
        "figure4_run_row_ylim_lower": 0.0,
        "figure4_run_row_ylim_upper": 5.0,
        "figure4_run_row_actual_max": 5.0,
        "DAY12_V2_DATA_AUDIT": "PASS",
        "DAY12_V2_REPRODUCIBILITY": "PASS",
        "DAY12_V2_CONTRACT_COMPLETE": False,
    })
    return values


def test_complete_v3_gate_passes():
    assert evaluate_day12_v3_gate(_passing()) is True


def test_modified_v2_or_day11b_tree_fails_gate():
    for field in ("day12_v2_result_tree_unchanged", "day11b_v2_result_tree_unchanged"):
        values = _passing()
        values[field] = False
        assert evaluate_day12_v3_gate(values) is False


def test_axis_input_lock_or_scientific_decision_failure_stops_gate():
    for field in (
        "DAY12_V3_AXIS_CONTRACT_PASS", "DAY12_V3_INPUT_LOCK_PASS",
        "estimator_replayed", "threshold_created", "auroc_computed", "fpr_computed",
    ):
        values = _passing()
        values[field] = not bool(values[field])
        assert evaluate_day12_v3_gate(values) is False
