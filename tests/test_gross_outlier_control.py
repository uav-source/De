import numpy as np

from minibench.correspondence_stress import apply_correspondence_stress
from minibench.update_strategies import huber_weights
from stage2c_helpers import patch_ids, simple_observations, stress_config


def test_gross_outlier_control_is_more_often_huber_downweighted():
    observations = simple_observations(frames=30); patches = patch_ids(observations)
    gross = apply_correspondence_stress(observations, "gross_outlier_control", stress_config(), "stage2c", 7, 8, patches)
    mask = gross["contamination_mask"]
    residual = observations["r_list"][mask] - gross["contamination_offset_m"][mask]
    weights = huber_weights(residual, observations["R_diag_list"][mask], 2.5)
    assert float(gross["injected_slip_sigma"]) == 4.0
    assert np.mean(weights < 1.0) > 0.30

