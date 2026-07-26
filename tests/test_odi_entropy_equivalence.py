import numpy as np

from eval.metric_semantics import odi_export_relationship


def test_three_dimensional_odi_has_exact_exported_entropy_relationship():
    odi = np.linspace(0.0, 1.0, 10_001)
    effective_rank, entropy = odi_export_relationship(odi)
    np.testing.assert_array_equal(effective_rank, 3.0 - 2.0 * odi)
    np.testing.assert_array_equal(entropy, np.log(3.0 - 2.0 * odi))
    assert np.all(np.diff(effective_rank) < 0.0)
    assert np.all(np.diff(entropy) < 0.0)
