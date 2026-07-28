import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "artifacts/current/zero_perturbation_phase_a_lock_architecture_v2/tamper_rejection_report.json"


def test_all_23_layer_tampers_are_rejected_pre_cache() -> None:
    value = json.loads(REPORT.read_text())
    assert value["LOCK_ARCHITECTURE_V2_TAMPER_REJECTION_PASS"] is True
    assert value["case_count"] == value["rejected_case_count"] == 23
    assert all(row["cache_read_count"] == 0 for row in value["cases"])

