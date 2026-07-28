import pytest

from phase_a_execution_chain_test_support import sample_result
from zero_perturbation.phase_a_trial_result_writer import write_phase_a_trial_result
from zero_perturbation.phase_a_trial_resume import CorruptExistingResult, validate_existing_trial_result_for_resume


def test_resume_rejects_truncated_json(tmp_path):
    value = sample_result()
    path, digest = write_phase_a_trial_result(tmp_path, value)
    path.write_text("{", encoding="utf-8")
    entry = {"path": path.name, "planned_trial_id": value["planned_trial_id"], "sha256": digest}
    with pytest.raises(CorruptExistingResult):
        validate_existing_trial_result_for_resume(path, manifest_entry=entry, expected=value)
