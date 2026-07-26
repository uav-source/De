import numpy as np
from scipy.stats import rankdata

from eval.metric_semantics import RANDOM_EQUIVALENCE_SEED, odi_export_relationship


def test_fixed_seed_random_spectra_have_identical_odi_and_negative_entropy_ranks():
    rng = np.random.default_rng(RANDOM_EQUIVALENCE_SEED)
    eig = np.exp(rng.uniform(-12, 12, size=(10_000, 3)))
    epsilon = np.maximum(np.mean(eig, axis=1) * 1e-6, 1e-6)
    probabilities = (eig + epsilon[:, None]) / np.sum(eig + epsilon[:, None], axis=1, keepdims=True)
    entropy = -np.sum(probabilities * np.log(probabilities), axis=1)
    odi = 1.0 - (np.exp(entropy) - 1.0) / 2.0
    rank, exported_entropy = odi_export_relationship(odi)
    assert np.array_equal(rankdata(odi), rankdata(-entropy))
    assert np.array_equal(exported_entropy, np.log(rank))
