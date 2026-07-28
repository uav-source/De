from backend_phase_a_test_support import protocol


def test_phase_a_has_only_ideal_matched_without_noise_or_dropout():
    phase = protocol()
    ideal = phase.data["ideal_matched"]
    assert phase.conditions == ("IDEAL_MATCHED",)
    assert ideal["independent_resampling"] is False
    assert ideal["scan_noise_m"] == 0.0
    assert ideal["map_noise_m"] == 0.0
    assert ideal["source_dropout_fraction"] == 0.0
    assert ideal["target_dropout_fraction"] == 0.0
    assert all(row.condition == "IDEAL_MATCHED" for row in phase.planned_snapshots())
