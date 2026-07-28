import pytest

from backend_phase_a_v1_1_test_support import ROOT, fake_result, fixture_points
from zero_perturbation.backend_phase_a_metrics import OPEN3D_BACKEND, PCL_BACKEND
from zero_perturbation.backend_phase_a_v1_1 import (
    DuplicateTrialResult,
    execute_fixture_chain,
)


def test_runner_refuses_duplicate_trial_overwrite_without_resume(tmp_path):
    hooks = {
        OPEN3D_BACKEND: fake_result(OPEN3D_BACKEND),
        PCL_BACKEND: fake_result(PCL_BACKEND),
    }
    execute_fixture_chain(root=ROOT, points=fixture_points(), output_dir=tmp_path, backend_hooks=hooks)
    with pytest.raises(DuplicateTrialResult):
        execute_fixture_chain(root=ROOT, points=fixture_points(), output_dir=tmp_path, backend_hooks=hooks)

