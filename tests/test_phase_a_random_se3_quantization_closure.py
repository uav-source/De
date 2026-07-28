import numpy as np

from zero_perturbation.backend_phase_a_v1_2 import (
    canonical_target,
    quantization_closure,
    source_from_parent_indices,
)


def test_independent_random_se3_cases_close_without_bytewise_requirement():
    rng = np.random.default_rng(908172635)
    bytewise_mismatch_cases = 0
    for _ in range(12):
        matrix = rng.normal(size=(3, 3))
        q, _ = np.linalg.qr(matrix)
        if np.linalg.det(q) < 0:
            q[:, 0] *= -1
        pose = np.eye(4, dtype="<f8")
        pose[:3, :3] = q
        pose[:3, 3] = rng.uniform(-3.0, 3.0, 3)
        target = canonical_target(rng.uniform(-10.0, 10.0, (127, 3)))
        indices = np.arange(len(target), dtype="<i8")
        source, source_f64, parents = source_from_parent_indices(target, indices, pose)
        roundtrip = ((q @ source.astype(float).T).T + pose[:3, 3]).astype("<f4")
        bytewise_mismatch_cases += int(not np.array_equal(roundtrip, target))
        report = quantization_closure(source_points=source, source_float64=source_f64, parent_points_map_float64=parents, reference_pose=pose)
        assert report["quantization_closure_pass"] is True
        assert report["max_normalized_closure_ratio"] <= 1.0
    assert bytewise_mismatch_cases >= 10
