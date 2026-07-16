import csv
import json
from pathlib import Path

from eval.stage2_failure_day11b_provenance import compare_v1_v2_scientific_outputs


def _write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _runs(tmp_path):
    v1, v2 = tmp_path / "v1", tmp_path / "v2"
    case = "case"
    for run in (v1, v2):
        case_dir = run / "cases" / case
        for name in (
            "frame_diagnostics_online.csv", "frame_diagnostics_gt.csv",
            "frame_window_statistics.csv",
        ):
            _write_csv(case_dir / name, ("frame_index", "value"), [
                {"frame_index": 1, "value": 0.0}, {"frame_index": 2, "value": "nan"}
            ])
        (case_dir / "trajectory_metrics.json").write_text(
            json.dumps({"metric": 1.0}), encoding="utf-8"
        )
        _write_csv(run / "replay_case_summary.csv", ("case_id", "metric"), [
            {"case_id": case, "metric": 1.0}
        ])
        _write_csv(
            run / "replay_frame_diagnostics_merged.csv",
            ("case_id", "frame_index", "value"),
            [{"case_id": case, "frame_index": 1, "value": 0.0}],
        )
    return v1, v2


def test_identical_scientific_outputs_pass(tmp_path):
    _, summary = compare_v1_v2_scientific_outputs(*_runs(tmp_path))
    assert summary["v1_v2_failure_count"] == 0
    assert summary["v1_v2_max_numeric_difference"] == 0.0


def test_online_change_of_one_e_minus_11_fails(tmp_path):
    v1, v2 = _runs(tmp_path)
    path = v2 / "cases/case/frame_diagnostics_online.csv"
    _write_csv(path, ("frame_index", "value"), [
        {"frame_index": 1, "value": 1.0e-11}, {"frame_index": 2, "value": "nan"}
    ])
    _, summary = compare_v1_v2_scientific_outputs(v1, v2)
    assert summary["v1_v2_failure_count"] > 0
    assert summary["v1_v2_max_numeric_difference"] == 1.0e-11


def test_one_sided_nan_fails(tmp_path):
    v1, v2 = _runs(tmp_path)
    path = v2 / "cases/case/frame_diagnostics_online.csv"
    _write_csv(path, ("frame_index", "value"), [
        {"frame_index": 1, "value": 0.0}, {"frame_index": 2, "value": 0.0}
    ])
    _, summary = compare_v1_v2_scientific_outputs(v1, v2)
    assert summary["v1_v2_failure_count"] > 0


def test_missing_primary_key_fails(tmp_path):
    v1, v2 = _runs(tmp_path)
    path = v2 / "cases/case/frame_diagnostics_online.csv"
    _write_csv(path, ("frame_index", "value"), [{"frame_index": 1, "value": 0.0}])
    _, summary = compare_v1_v2_scientific_outputs(v1, v2)
    assert summary["v1_v2_key_mismatch_count"] > 0


def test_run_id_is_explicitly_excluded_as_non_scientific_provenance(tmp_path):
    v1, v2 = _runs(tmp_path)
    for run, run_id in ((v1, "stage2_failure_day11b_replay_v1"),
                        (v2, "stage2_failure_day11b_replay_v2")):
        path = run / "cases/case/frame_diagnostics_online.csv"
        _write_csv(path, ("frame_index", "value", "run_id"), [
            {"frame_index": 1, "value": 0.0, "run_id": run_id},
            {"frame_index": 2, "value": "nan", "run_id": run_id},
        ])
    _, summary = compare_v1_v2_scientific_outputs(v1, v2)
    assert summary["v1_v2_failure_count"] == 0
