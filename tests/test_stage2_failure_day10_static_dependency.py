from pathlib import Path

from eval.stage2_failure_no_gt_audit import audit_static_dependencies


ROOT = Path(__file__).resolve().parents[1]


def test_day10_static_dependency_audit_passes_current_online_path():
    audit = audit_static_dependencies(ROOT)
    assert audit["audit_pass"] is True
    assert audit["parse_failures"] == []
    assert audit["forbidden_imports"] == []
    assert audit["forbidden_signature_parameters"] == []
    assert audit["forbidden_online_schema_fields"] == []


def test_static_audit_detects_forbidden_import_and_signature_parameter():
    logging_path = "src/eval/stage2_failure_logging.py"
    map_path = "src/minibench/map_lio.py"
    logging_source = (ROOT / logging_path).read_text(encoding="utf-8")
    map_source = (ROOT / map_path).read_text(encoding="utf-8")
    audit = audit_static_dependencies(
        ROOT,
        source_overrides={
            logging_path: logging_source
            + "\nfrom eval.stage2_failure_gt_metrics import evaluate_gt_frame_records\n",
            map_path: map_source + "\ndef run_map_lio(pose_gt):\n    return pose_gt\n",
        },
    )
    assert audit["audit_pass"] is False
    assert len(audit["forbidden_imports"]) == 2
    assert audit["forbidden_signature_parameters"] == [
        {"file": map_path, "api": "run_map_lio", "parameter": "pose_gt"}
    ]


def test_static_audit_rejects_parse_failure_and_forbidden_schema_token():
    target = "src/eval/stage2_failure_window_stats.py"
    audit = audit_static_dependencies(
        ROOT,
        source_overrides={target: "def broken(:\n"},
        online_schema_fields=["schema_version", "pose_gt"],
    )
    assert audit["audit_pass"] is False
    assert len(audit["parse_failures"]) == 1
    assert audit["forbidden_online_schema_fields"] == ["pose_gt"]
