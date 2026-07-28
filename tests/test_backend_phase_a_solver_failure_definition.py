import pytest

from zero_perturbation.backend_phase_a_metrics import (
    OPEN3D_BACKEND,
    PCL_BACKEND,
    solver_failure_reasons,
)


CHECKSUMS = {"source_checksum": "s", "target_checksum": "t"}


def test_unexecuted_trial_is_not_counted_as_zero_solver_failures():
    with pytest.raises(ValueError, match="NOT_EVALUATED"):
        solver_failure_reasons(OPEN3D_BACKEND, None, CHECKSUMS)


def test_open3d_and_pcl_failure_vocabularies_are_backend_specific():
    open3d = solver_failure_reasons(OPEN3D_BACKEND, {}, CHECKSUMS)
    pcl = solver_failure_reasons(PCL_BACKEND, {}, CHECKSUMS)
    assert "NONFINITE_INLIER_RMSE" in open3d
    assert "PCL_NOT_CONVERGED" in pcl
    assert "INVALID_NORMALS" in pcl
    assert "SNAPSHOT_OR_INPUT_CHECKSUM_MISMATCH" in open3d
