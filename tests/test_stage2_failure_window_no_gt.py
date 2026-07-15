import inspect
import json
from pathlib import Path

from eval import stage2_failure_day8 as day8
from eval import stage2_failure_day9 as day9
from eval.stage2_failure_window_schema import WINDOW_FIELDS


ROOT = Path(__file__).resolve().parents[1]


def test_day9_has_no_offline_evaluator_dependency_or_offline_schema_fields():
    signature = inspect.signature(day9.run_stage2_failure_day9)
    forbidden = {"pose_gt", "axis_per_frame", "gt_axis", "scene_label", "oracle_axis"}
    assert forbidden.isdisjoint(signature.parameters)
    source = Path(inspect.getsourcefile(day9)).read_text(encoding="utf-8")
    assert "stage2_failure_gt_metrics" not in source
    assert all("gt" not in name.lower().split("_") for name in WINDOW_FIELDS)


def test_removing_or_adding_fake_gt_csv_does_not_change_day9_output(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(day8, "git_status_clean", lambda root: True)
    monkeypatch.setattr(day9, "git_status_clean", lambda root: True)
    day8_manifest = day8.run_stage2_failure_day8(
        ROOT,
        "day8_no_gt_source",
        tmp_path / "day8",
    )
    day8_dir = tmp_path / "day8/day8_no_gt_source"
    online_path = day8_dir / "frame_diagnostics_online.csv"
    source_manifest_path = day8_dir / "run_manifest.json"
    offline_path = day8_dir / "frame_diagnostics_gt.csv"
    offline_path.unlink()

    first = day9.run_stage2_failure_day9(
        ROOT,
        online_path,
        source_manifest_path,
        "without_gt_file",
        tmp_path / "day9",
    )
    assert first["DAY9_WINDOW_STATS_PASS"] is True
    assert first["gt_file_read"] is False
    assert first["gt_field_read"] is False
    first_csv = (
        tmp_path / "day9/without_gt_file/frame_window_statistics.csv"
    ).read_bytes()

    offline_path.write_text(
        json.dumps({"fabricated": True}) + "\n",
        encoding="utf-8",
    )
    second = day9.run_stage2_failure_day9(
        ROOT,
        online_path,
        source_manifest_path,
        "with_fake_gt_file",
        tmp_path / "day9",
    )
    second_csv = (
        tmp_path / "day9/with_fake_gt_file/frame_window_statistics.csv"
    ).read_bytes()
    assert second["DAY9_WINDOW_STATS_PASS"] is True
    assert first_csv == second_csv
