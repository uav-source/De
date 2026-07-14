import numpy as np

from minibench.correspondence_stress import apply_correspondence_stress
from stage2b_helpers import simple_observations, stress_config


def test_clean_stress_changes_nothing():
    observations = simple_observations(frames=12)
    patches = np.full(observations["is_axial_support"].shape, "p", dtype="U4")
    output = apply_correspondence_stress(observations, "clean", stress_config(), "stage2b", 1, 2, patches)
    assert np.array_equal(output["plane_points_world"], observations["plane_points_world"])
    assert not np.any(output["contamination_mask"])
