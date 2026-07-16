from pathlib import Path

from eval.stage2_failure_day12_plot_data import build_all_plot_data, read_merged_rows, validate_plot_data

ROOT = Path(__file__).resolve().parents[1]
MERGED = ROOT / "results/stage2_failure_analysis/day11b_replay/stage2_failure_day11b_replay_v2/replay_frame_diagnostics_merged.csv"


def test_plot_data_is_complete_and_source_hashes_match():
    fields, rows = read_merged_rows(MERGED)
    data = build_all_plot_data(fields, rows)
    assert [len(data[name]) for name in data] == [312, 312, 312, 1248]
    audit = validate_plot_data(data, fields, rows)
    assert audit["source_row_hash_mismatch_count"] == 0


def test_source_hash_mutation_is_rejected():
    fields, rows = read_merged_rows(MERGED)
    data = {key: [dict(row) for row in value] for key, value in build_all_plot_data(fields, rows).items()}
    data["day12_fig01_innovation_timeline"][0]["source_row_sha256"] = "0" * 64
    assert validate_plot_data(data, fields, rows)["source_row_hash_mismatch_count"] == 1


def test_source_value_mutation_is_rejected_even_with_unchanged_source_hash():
    fields, rows = read_merged_rows(MERGED)
    data = {key: [dict(row) for row in value] for key, value in build_all_plot_data(fields, rows).items()}
    target = data["day12_fig02_prior_posterior_axis_error"][0]
    target["prior_axis_error_abs_m"], target["posterior_axis_error_abs_m"] = (
        target["posterior_axis_error_abs_m"], target["prior_axis_error_abs_m"]
    )
    audit = validate_plot_data(data, fields, rows)
    assert audit["source_row_hash_mismatch_count"] == 0
    assert audit["source_value_mismatch_count"] == 1
    assert audit["plot_data_audit_failure_count"] == 1


def test_missing_figure1_case_is_rejected():
    fields, rows = read_merged_rows(MERGED)
    data = {key: [dict(row) for row in value] for key, value in build_all_plot_data(fields, rows).items()}
    removed_case = data["day12_fig01_innovation_timeline"][0]["case_id"]
    data["day12_fig01_innovation_timeline"] = [
        row for row in data["day12_fig01_innovation_timeline"]
        if row["case_id"] != removed_case
    ]
    assert validate_plot_data(data, fields, rows)["plot_data_audit_failure_count"] == 1


def test_max_run_substitution_and_jitter_or_inclusion_changes_are_rejected():
    fields, rows = read_merged_rows(MERGED)
    data = {key: [dict(row) for row in value] for key, value in build_all_plot_data(fields, rows).items()}
    run_row = next(
        row for row in data["day12_fig03_same_sign_run_timeline"]
        if row["huber_current_same_sign_run_length"] != row["huber_max_same_sign_run_length"]
    )
    run_row["huber_current_same_sign_run_length"] = run_row["huber_max_same_sign_run_length"]
    distribution = data["day12_fig04_clean_stress_distributions"]
    distribution[0]["deterministic_jitter"] = float(distribution[0]["deterministic_jitter"]) + 0.001
    window_row = next(row for row in distribution if row["inclusion_rule"].startswith("window_ready"))
    window_row["included"] = not bool(window_row["included"])
    audit = validate_plot_data(data, fields, rows)
    assert audit["source_value_mismatch_count"] == 3
    assert audit["plot_data_audit_failure_count"] == 2
