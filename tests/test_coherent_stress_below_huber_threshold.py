import numpy as np

from minibench.correspondence_stress import apply_correspondence_stress
from minibench.update_strategies import huber_weights
from stage2c_helpers import patch_ids, simple_observations, stress_config


def test_coherent_stress_is_below_huber_threshold():
    observations = simple_observations(frames=30)
    output = apply_correspondence_stress(observations, "coherent_subhuber_slip", stress_config(), "stage2c", 3, 4, patch_ids(observations))
    mask = output["contamination_mask"]
    stressed_residual = observations["r_list"][mask] - output["contamination_offset_m"][mask]
    weights = huber_weights(stressed_residual, observations["R_diag_list"][mask], 2.5)
    assert float(output["injected_slip_sigma"]) < 2.5
    assert np.mean(weights < 1.0) <= 0.30

