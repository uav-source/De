import numpy as np

from minibench.correspondence_stress import apply_correspondence_stress
from stage2c_helpers import patch_ids, simple_observations, stress_config


def test_coherent_stress_offsets_have_one_shared_sign():
    observations = simple_observations(frames=30)
    output = apply_correspondence_stress(observations, "coherent_subhuber_slip", stress_config(), "stage2c", 1, 2, patch_ids(observations))
    offsets = output["contamination_offset_m"][output["contamination_mask"]]
    assert np.unique(np.sign(offsets)).tolist() == [int(output["shared_burst_sign"])]

