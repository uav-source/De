import pytest

from phase_a_execution_chain_test_support import AUDIT_LOCK, FAKE_HOOKS, FIXTURE_LOCK, ROOT
from zero_perturbation.phase_a_execution_chain_audit import InjectedInfrastructureInterruption, execute_fixture_audit_trials


def test_interruption_then_resume_skips_exactly_two_valid_results(tmp_path):
    output = tmp_path / "interrupted"
    with pytest.raises(InjectedInfrastructureInterruption):
        execute_fixture_audit_trials(root=ROOT, protocol_lock=AUDIT_LOCK, fixture_lock=FIXTURE_LOCK, run_id="resume-test", output_dir=output, interrupt_after_completed=2, backend_hooks=FAKE_HOOKS)
    resumed = execute_fixture_audit_trials(root=ROOT, protocol_lock=AUDIT_LOCK, fixture_lock=FIXTURE_LOCK, run_id="resume-test", output_dir=output, resume=True, backend_hooks=FAKE_HOOKS)
    assert resumed["resume_skipped_valid_result_count"] == 2
    assert resumed["backend_execution_count_this_invocation"] == 4
    assert resumed["fixture_completed_trial_count"] == 6
