import csv
import json
from pathlib import Path

import pytest

from eval import stage2_failure_day8 as day8
from eval import stage2_failure_day9 as day9
from eval.analysis_lock import sha256_file
from eval.stage2_failure_schema import FRAME_KEY_FIELDS


ROOT = Path(__file__).resolve().parents[1]


def test_day9_quick_pipeline_validates_source_and_writes_one_to_one_rows(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(day8, "git_status_clean", lambda root: True)
    monkeypatch.setattr(day9, "git_status_clean", lambda root: True)
    day8.run_stage2_failure_day8(
        ROOT,
        "day8_day9_source",
        tmp_path / "day8",
    )
    source_dir = tmp_path / "day8/day8_day9_source"
    online_path = source_dir / "frame_diagnostics_online.csv"
    source_manifest_path = source_dir / "run_manifest.json"
    manifest = day9.run_stage2_failure_day9(
        ROOT,
        online_path,
        source_manifest_path,
        "pytest_day9_quick",
        tmp_path / "day9",
    )
    output_dir = tmp_path / "day9/pytest_day9_quick"
    output_path = output_dir / "frame_window_statistics.csv"
    manifest_path = output_dir / "run_manifest.json"
    summary_path = output_dir / "day9_quick_summary.json"
    assert all(path.exists() for path in [output_path, manifest_path, summary_path])

    with online_path.open(newline="", encoding="utf-8") as handle:
        input_rows = list(csv.DictReader(handle))
    with output_path.open(newline="", encoding="utf-8") as handle:
        output_rows = list(csv.DictReader(handle))
    input_keys = [tuple(row[name] for name in FRAME_KEY_FIELDS) for row in input_rows]
    output_keys = [tuple(row[name] for name in FRAME_KEY_FIELDS) for row in output_rows]
    assert input_keys == output_keys
    assert len(input_rows) == len(output_rows) == 14

    written = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert written == manifest
    assert manifest["DAY9_WINDOW_STATS_PASS"] is True
    assert manifest["input_row_count"] == manifest["output_row_count"] == 14
    assert manifest["group_count"] == 2
    assert manifest["duplicate_key_count"] == 0
    assert manifest["ordering_violation_count"] == 0
    assert manifest["frame_key_one_to_one"] is True
    assert manifest["causal_prefix_equivalence_pass"] is True
    assert manifest["group_isolation_pass"] is True
    assert manifest["raw_huber_state_isolated"] is True
    assert manifest["nonfinite_violation_count"] == 0
    assert manifest["gt_file_read"] is False
    assert manifest["gt_field_read"] is False
    assert manifest["reserved_test_run_performed"] is False
    assert manifest["historical_artifacts_unchanged"] is True
    assert manifest["source_online_log_sha256"] == sha256_file(online_path)


def test_day9_refuses_source_manifest_hash_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(day8, "git_status_clean", lambda root: True)
    monkeypatch.setattr(day9, "git_status_clean", lambda root: True)
    day8.run_stage2_failure_day8(
        ROOT,
        "day8_tamper_source",
        tmp_path / "day8",
    )
    source_dir = tmp_path / "day8/day8_tamper_source"
    online_path = source_dir / "frame_diagnostics_online.csv"
    online_path.write_text(
        online_path.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="SHA-256"):
        day9.run_stage2_failure_day9(
            ROOT,
            online_path,
            source_dir / "run_manifest.json",
            "refuse_tamper",
            tmp_path / "day9",
        )
