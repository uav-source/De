import numpy as np

from zero_perturbation.statistics import repeatability_covariance


def test_repeatability_covariance_uses_sample_ddof_one():
    values = np.array([[0.0, 0.0, 0.0], [2.0, 0.0, 0.0]])
    covariance = repeatability_covariance(values, ddof=1)
    assert np.array_equal(covariance, np.diag([2.0, 0.0, 0.0]))
