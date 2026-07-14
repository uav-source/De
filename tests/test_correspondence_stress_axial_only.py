import numpy as np

from minibench.correspondence_stress import apply_correspondence_stress
from stage2b_helpers import simple_observations, stress_config


def test_axial_slip_contaminates_only_axial_support():
    observations = simple_observations(frames=12)
    shape = observations["is_axial_support"].shape
    patches = np.empty(shape, dtype="U8")
    for col in range(shape[1]): patches[:, col] = f"p{col % 4}"
    output = apply_correspondence_stress(observations, "axial_correspondence_slip", stress_config(), "stage2b", 1, 2, patches)
    assert np.any(output["contamination_mask"])
    assert np.all(observations["is_axial_support"][output["contamination_mask"]])
    assert np.all(np.abs(output["contamination_offset_m"][output["contamination_mask"]]) == 0.08)
