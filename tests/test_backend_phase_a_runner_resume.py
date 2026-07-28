from backend_phase_a_v1_1_test_support import ROOT, fake_result, fixture_points
from zero_perturbation.backend_phase_a_metrics import OPEN3D_BACKEND, PCL_BACKEND
from zero_perturbation.backend_phase_a_v1_1 import execute_fixture_chain


def test_runner_resume_skips_verified_existing_trials(tmp_path):
    calls = {OPEN3D_BACKEND: 0, PCL_BACKEND: 0}

    def counted(backend):
        base = fake_result(backend)

        def run(**arguments):
            calls[backend] += 1
            return base(**arguments)

        return run

    hooks = {backend: counted(backend) for backend in calls}
    execute_fixture_chain(root=ROOT, points=fixture_points(), output_dir=tmp_path, backend_hooks=hooks)
    resumed = execute_fixture_chain(
        root=ROOT,
        points=fixture_points(),
        output_dir=tmp_path,
        resume=True,
        backend_hooks=hooks,
    )
    assert calls == {OPEN3D_BACKEND: 1, PCL_BACKEND: 1}
    assert len(resumed["resumed_trial_ids"]) == 2
    assert set(resumed["completed_trial_ids"]) == set(resumed["resumed_trial_ids"])

