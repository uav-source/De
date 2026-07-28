from backend_qualification_test_support import qualification_decision, qualification_manifest


def test_pipeline_stopped_before_phase_a_and_phase_b():
    decision = qualification_decision()
    manifest = qualification_manifest()
    assert decision["phase_a_executed"] is False
    assert decision["phase_b_executed"] is False
    assert decision["ideal_matched_snapshot_count"] == 0
    assert decision["ideal_matched_trial_count"] == 0
    assert manifest["full_development_run_executed"] is False

