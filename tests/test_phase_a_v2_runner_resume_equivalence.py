import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "artifacts/current/zero_perturbation_phase_a_lock_architecture_v2/resume_equivalence_report.json"


def test_fixture_fresh_resume_are_scientifically_equivalent() -> None:
    value = json.loads(REPORT.read_text())
    assert value["RESUME_SCIENTIFIC_EQUIVALENCE_PASS"] is True
    assert value["resume_skipped_valid_result_count"] == 2
    assert value["resume_reexecuted_valid_result_count"] == 0

