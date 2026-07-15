import csv
import json
from pathlib import Path

import pytest

from eval import stage2_failure_day8 as day8
from eval import stage2_failure_day9 as day9
from eval.analysis_lock import sha256_file
from eval.stage2_failure_schema import FRAME_KEY_FIELDS


ROOT = Path(__file__).resolve().parents[1]


def _source_row(frame, valid=True):
    return {
        "schema_version": day9.ONLINE_SCHEMA_VERSION,
        "run_id": "source",
        "sequence_id": "sequence",
        "sweep": "quick",
        "level": "unit",
        "stress": "fixture",
        "geometry_seed": 1,
        "sensor_seed": 2,
        "process_seed": 3,
        "method": "huber_full",
        "frame_index": frame,
        "timestamp": frame * 0.1,
        "weak_direction_valid": valid,
        "weak_innovation_valid": valid,
        "primary_direction_stable": valid,
        "degeneracy_triggered": False,
        "actionable_direction": False,
        "odi_trans": 0.1,
        "primary_eigengap_ratio": 0.2,
        "weak_innovation_z_raw": 1.0,
        "weak_innovation_z_huber": 0.8,
    }


def _run_with_source_rows(tmp_path, monkeypatch, rows, run_id):
    online_path = tmp_path / f"{run_id}_online.csv"
    source_manifest_path = tmp_path / f"{run_id}_manifest.json"
    online_path.write_text("fixture\n", encoding="utf-8")
    source_manifest_path.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(day9, "git_status_clean", lambda root: True)
    monkeypatch.setattr(day9, "read_online_csv", lambda path: rows)
    monkeypatch.setattr(
        day9,
        "validate_source_manifest",
        lambda manifest_path, log_path: {"online_log_row_count": len(rows)},
    )
    return day9.run_stage2_failure_day9(
        ROOT,
        online_path,
        source_manifest_path,
        run_id,
        tmp_path / "day9",
    )


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


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("sign_zero_epsilon", 1.1e-12),
        ("moment_epsilon", 0.9e-12),
    ],
)
def test_day9_quick_config_freezes_epsilon_parameters(name, value):
    config = day9.load_yaml(ROOT / "configs/stage2_failure/day9_quick.yaml")
    config[name] = value
    with pytest.raises(ValueError, match="epsilon is frozen"):
        day9._validate_day9_quick_config(config)


def test_day9_gate_rejects_all_invalid_inputs(tmp_path, monkeypatch):
    rows = [_source_row(frame, valid=False) for frame in range(1, 7)]
    manifest = _run_with_source_rows(tmp_path, monkeypatch, rows, "all_invalid")
    assert manifest["valid_input_row_count"] == 0
    assert manifest["window_ready_row_count"] == 0
    assert manifest["DAY9_WINDOW_STATS_PASS"] is False


def test_day9_gate_rejects_valid_inputs_without_a_full_window(tmp_path, monkeypatch):
    rows = [_source_row(frame) for frame in range(1, 5)]
    manifest = _run_with_source_rows(tmp_path, monkeypatch, rows, "no_full_window")
    assert manifest["valid_input_row_count"] == 4
    assert manifest["window_ready_row_count"] == 0
    assert manifest["DAY9_WINDOW_STATS_PASS"] is False
