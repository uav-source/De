from backend_phase_a_v1_1_test_support import ROOT, fake_result, fixture_points
from zero_perturbation.backend_phase_a_metrics import OPEN3D_BACKEND, PCL_BACKEND
from zero_perturbation.backend_phase_a_v1_1 import execute_fixture_chain


def test_runner_manifest_id_sets_are_consistent(tmp_path):
    manifest = execute_fixture_chain(
        root=ROOT,
        points=fixture_points(),
        output_dir=tmp_path,
        backend_hooks={
            OPEN3D_BACKEND: fake_result(OPEN3D_BACKEND),
            PCL_BACKEND: fake_result(PCL_BACKEND),
        },
    )
    completed = set(manifest["completed_trial_ids"])
    pending = set(manifest["pending_trial_ids"])
    failed = set(manifest["failed_trial_ids"])
    resumed = set(manifest["resumed_trial_ids"])
    assert len(completed) == 2
    assert not completed & pending
    assert failed <= completed
    assert resumed <= completed

