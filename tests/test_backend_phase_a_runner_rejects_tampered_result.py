import json

import pytest

from backend_phase_a_v1_1_test_support import ROOT, fake_result, fixture_points
from zero_perturbation.backend_phase_a_metrics import OPEN3D_BACKEND, PCL_BACKEND
from zero_perturbation.backend_phase_a_v1_1 import (
    CorruptExistingResult,
    execute_fixture_chain,
)


def test_runner_resume_rejects_tampered_result(tmp_path):
    hooks = {
        OPEN3D_BACKEND: fake_result(OPEN3D_BACKEND),
        PCL_BACKEND: fake_result(PCL_BACKEND),
    }
    execute_fixture_chain(root=ROOT, points=fixture_points(), output_dir=tmp_path, backend_hooks=hooks)
    path = next((tmp_path / "trials").glob("*.json"))
    payload = json.loads(path.read_text())
    payload["planned_trial_id"] = "tampered"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CorruptExistingResult):
        execute_fixture_chain(
            root=ROOT,
            points=fixture_points(),
            output_dir=tmp_path,
            resume=True,
            backend_hooks=hooks,
        )

