import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/current/zero_perturbation_phase_a_execution_chain_audit_v1_2"


def test_execution_chain_v1_2_fresh_resume_equivalence_passes():
    report = json.loads((ARTIFACT / "resume_scientific_equivalence_report.json").read_text())
    resume = json.loads((ARTIFACT / "resume_audit.json").read_text())
    assert report["fresh_trial_count"] == report["resumed_trial_count"] == 6
    assert report["exact_field_mismatch_count"] == 0
    assert report["numeric_difference_outside_tolerance_count"] == 0
    assert report["RESUME_SCIENTIFIC_EQUIVALENCE_PASS"] is True
    assert resume["RESUME_SKIPPED_VALID_RESULT_COUNT"] == 2
    assert resume["RESUME_REEXECUTED_VALID_RESULT_COUNT"] == 0
