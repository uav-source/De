import json

import pytest

from phase_a_execution_chain_test_support import AUDIT_LOCK, FAKE_HOOKS, FIXTURE_LOCK, ROOT
from zero_perturbation.phase_a_execution_chain_audit import InjectedInfrastructureInterruption, execute_fixture_audit_trials
from zero_perturbation.phase_a_trial_resume import CorruptExistingResult


def test_tampered_result_is_rejected_without_overwrite_or_continuation(tmp_path):
    output = tmp_path / "tamper"
    with pytest.raises(InjectedInfrastructureInterruption):
        execute_fixture_audit_trials(root=ROOT, protocol_lock=AUDIT_LOCK, fixture_lock=FIXTURE_LOCK, run_id="tamper-test", output_dir=output, interrupt_after_completed=1, backend_hooks=FAKE_HOOKS)
    manifest = json.loads((output / "raw_result_manifest.json").read_text())
    entry = next(iter(manifest["results"].values()))
    path = output / "raw_results" / entry["path"]
    value = json.loads(path.read_text())
    value["snapshot_lock_sha256"] = "b" * 64
    path.write_text(json.dumps(value, sort_keys=True) + "\n")
    tampered = path.read_bytes()
    with pytest.raises(CorruptExistingResult):
        execute_fixture_audit_trials(root=ROOT, protocol_lock=AUDIT_LOCK, fixture_lock=FIXTURE_LOCK, run_id="tamper-test", output_dir=output, resume=True, backend_hooks=FAKE_HOOKS)
    assert path.read_bytes() == tampered
    assert len(list((output / "raw_results").glob("*.json"))) == 1
