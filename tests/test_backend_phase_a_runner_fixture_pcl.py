from backend_phase_a_v1_1_test_support import actual_fixture_run
from zero_perturbation.backend_phase_a_metrics import PCL_BACKEND


def test_runner_fixture_pcl_identity_passes(actual_fixture_run):
    row = actual_fixture_run["results"][PCL_BACKEND]
    assert row["fixture_only"] is True
    assert row["solver_failed"] is False
    assert row["finite_output"] is True
    assert row["translation_update_m"] <= 1e-8
    assert row["rotation_update_rad"] <= 1e-8

