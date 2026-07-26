import numpy as np

from fastlio2_adapter.day6_eigenspace_stability import (
    compare_reconstruction,
    reconstruct_translation_information,
    reconstruction_pass,
    spearman_summary,
)


def test_translation_information_matches_independent_diagonal_fixture():
    record = {
        "detector_pose_jacobian_rows": np.eye(6).tolist(),
        "measurement_variance_scalar_m2": 0.04,
    }
    result = reconstruct_translation_information(record)
    expected = np.eye(3) * (0.5**2 / 0.04 / 6.0)
    assert np.allclose(result["h_translation"], expected, atol=1.0e-12)
    direct = {
        "translation_eigenvalues_ascending": np.diag(expected).tolist(),
        "primary_weak_direction": result["v1"].tolist(),
        "odi_trans": result["odi_trans"],
        "ais_trans": result["ais_trans"],
        "lambda_min_trans": float(expected[0, 0]),
        "condition_number_trans": result["condition_number"],
    }
    assert reconstruction_pass(compare_reconstruction(result, direct))


def test_correlation_output_is_explicitly_noncausal():
    summary = spearman_summary([1.0, 2.0, 3.0], [3.0, 2.0, 1.0])
    assert summary["spearman_rho"] == -1.0
    assert summary["causal_interpretation"] is False
