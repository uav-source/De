import importlib.util
import json
from pathlib import Path

from test_runtime_observation_v3 import v3_record


ROOT = Path(__file__).resolve().parents[1]


def load_detector_runner():
    spec = importlib.util.spec_from_file_location(
        "day5_v3_detector_runner",
        ROOT / "scripts/45_evaluate_fastlio2_runtime_records.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_v3_pipeline_outputs_one_detector_record_per_observation(tmp_path):
    records = [v3_record(), v3_record()]
    records[1]["scan_index"] += 1
    path = tmp_path / "observations.jsonl"
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )
    summary = load_detector_runner().evaluate_file(path, tmp_path / "detector")
    assert summary["schema_rejected_record_count"] == 0
    assert summary["observation_record_count"] == 2
    assert summary["detector_output_count"] == 2
    assert summary["detector_output_missing_count"] == 0
    assert summary["detector_repeat_checksum_mismatch_count"] == 0


def test_detector_invalid_is_not_dropped(tmp_path):
    record = v3_record()
    record["detector_pose_jacobian_rows"] = record[
        "detector_pose_jacobian_rows"
    ][:3]
    record["formal_filter_innovation_h"] = record[
        "formal_filter_innovation_h"
    ][:3]
    record["valid_correspondence_count"] = 3
    path = tmp_path / "observations.jsonl"
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    summary = load_detector_runner().evaluate_file(path, tmp_path / "detector")
    assert summary["schema_rejected_record_count"] == 0
    assert summary["detector_output_count"] == 1
    assert summary["detector_invalid_count"] == 1


def test_matrix_is_fail_closed_and_fixed_to_quick_sequences():
    text = (ROOT / "scripts/47_run_day5_remediation_matrix.sh").read_text()
    baseline_gate = text.index("BASELINE_STATUS")
    capture_root = text.index("CAPTURE_ROOT")
    capture_gate = text.index("CAPTURE_STATUS")
    export_root = text.index("EXPORT_ROOT")
    assert baseline_gate < capture_root < capture_gate < export_root
    assert "multihyp_day5_equivalence_v1" not in text
    assert "multihyp_day5_equivalence_v2" not in text
    assert "avia_quick_shack" in text
    assert "avia_outdoor_run_100hz" in text
    assert "Development" not in text
    assert "Holdout" not in text
    assert "Future Test" not in text
