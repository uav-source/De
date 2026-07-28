from backend_phase_a_v1_1_test_support import ROOT, fake_result, fixture_points
from zero_perturbation.backend_phase_a_metrics import OPEN3D_BACKEND, PCL_BACKEND
from zero_perturbation.backend_phase_a_v1_1 import execute_fixture_chain


def test_runner_atomically_writes_complete_json_without_tmp_residue(tmp_path):
    execute_fixture_chain(
        root=ROOT,
        points=fixture_points(),
        output_dir=tmp_path,
        backend_hooks={
            OPEN3D_BACKEND: fake_result(OPEN3D_BACKEND),
            PCL_BACKEND: fake_result(PCL_BACKEND),
        },
    )
    assert len(list((tmp_path / "trials").glob("*.json"))) == 2
    assert not list(tmp_path.rglob("*.tmp"))

