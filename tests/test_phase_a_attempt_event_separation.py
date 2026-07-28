from phase_a_execution_chain_test_support import sample_result
from zero_perturbation.phase_a_attempt_events import append_attempt_event, read_attempt_events


def test_attempt_event_is_not_a_trial_result(tmp_path):
    path = tmp_path / "attempt_events.ndjson"
    value = sample_result()
    append_attempt_event(path, planned_trial_id=value["planned_trial_id"], snapshot_id=value["snapshot_id"], backend=value["backend"], event_type="INFRASTRUCTURE_INTERRUPTION", detail="test")
    assert len(read_attempt_events(path)) == 1
    assert not list(tmp_path.glob("*.json"))
