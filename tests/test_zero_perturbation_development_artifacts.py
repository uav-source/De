from zero_perturbation.verification import REQUIRED_FIGURES, REQUIRED_TABLES


def test_development_compact_artifact_inventory_is_complete():
    assert len(REQUIRED_TABLES) == 17
    assert len(REQUIRED_FIGURES) == 9
    assert "trial_results.csv" in REQUIRED_TABLES
    assert "ideal_matched_control.png" in REQUIRED_FIGURES
