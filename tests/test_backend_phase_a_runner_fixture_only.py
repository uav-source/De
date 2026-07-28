from backend_phase_a_v1_1_test_support import ROOT, fake_result, fixture_points
from zero_perturbation.backend_phase_a_metrics import OPEN3D_BACKEND, PCL_BACKEND
from zero_perturbation.backend_phase_a_v1_1 import execute_fixture_chain


def test_runner_fixture_is_explicitly_nonformal(tmp_path):
    manifest = execute_fixture_chain(
        root=ROOT,
        points=fixture_points(),
        output_dir=tmp_path,
        backend_hooks={
            OPEN3D_BACKEND: fake_result(OPEN3D_BACKEND),
            PCL_BACKEND: fake_result(PCL_BACKEND),
        },
    )
    assert manifest["fixture_only"] is True
    assert manifest["is_formal_phase_a"] is False
    assert manifest["fixture_snapshot_count"] == 1
    assert manifest["fixture_trial_count"] == 2

