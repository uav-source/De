import numpy as np

from minibench.correspondence_stress import apply_correspondence_stress
from stage2c_helpers import patch_ids, simple_observations, stress_config


def test_coherent_subhuber_stress_is_axial_and_has_locked_sigma():
    observations = simple_observations(frames=30)
    output = apply_correspondence_stress(observations, "coherent_subhuber_slip", stress_config(), "stage2c", 1, 2, patch_ids(observations))
    mask = output["contamination_mask"]
    assert np.any(mask)
    assert np.all(observations["is_axial_support"][mask])
    assert float(output["injected_slip_sigma"]) == 1.5
    assert np.array_equal(output["R_diag_list"], observations["R_diag_list"])

