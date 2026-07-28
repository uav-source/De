import numpy as np

from zero_perturbation.statistics import systematic_fraction_translation


def test_systematic_fraction_is_null_for_zero_denominator():
    assert systematic_fraction_translation(np.zeros((10, 3))) is None
