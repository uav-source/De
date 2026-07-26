import importlib.util
import json
from pathlib import Path

from test_readonly_runtime_observation_schema import runtime_record


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/45_evaluate_fastlio2_runtime_records.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("day5_runtime_pipeline", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_real_record_pipeline_runs_twice_and_matches_checksums(tmp_path):
    records = [runtime_record(), runtime_record()]
    records[1]["scan_index"] = 2
    input_path = tmp_path / "observations.jsonl"
    input_path.write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )
    summary = load_runner().evaluate_file(input_path, tmp_path / "detector")
    assert summary["valid_observation_record_count"] == 2
    assert summary["detector_output_count"] == 2
    assert summary["invalid_observation_record_count"] == 0
    assert summary["detector_repeat_checksum_mismatch_count"] == 0
    assert summary["input_bag_read"] is False
    assert summary["deferred_information_read"] is False
    first = (tmp_path / "detector/detector_outputs_pass1.jsonl").read_bytes()
    second = (tmp_path / "detector/detector_outputs_pass2.jsonl").read_bytes()
    assert first == second


def test_invalid_runtime_record_is_preserved_not_silently_dropped(tmp_path):
    record = runtime_record()
    record["future_frame"] = 1
    input_path = tmp_path / "observations.jsonl"
    input_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    summary = load_runner().evaluate_file(input_path, tmp_path / "detector")
    assert summary["invalid_observation_record_count"] == 1
    assert summary["detector_output_count"] == 0
    invalid = (tmp_path / "detector/invalid_runtime_records.jsonl").read_text()
    assert "forbidden" in invalid
