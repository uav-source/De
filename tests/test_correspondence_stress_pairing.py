import numpy as np

from minibench.correspondence_stress import apply_correspondence_stress
from stage2b_helpers import simple_observations, stress_config


def test_stress_is_reproducible_for_pairing_group():
    obs = simple_observations(frames=12); patches = np.where(obs["is_axial_support"], "a", "s")
    first = apply_correspondence_stress(obs, "axial_correspondence_slip", stress_config(), "stage2b", 7, 8, patches)
    second = apply_correspondence_stress(obs, "axial_correspondence_slip", stress_config(), "stage2b", 7, 8, patches)
    assert first["stress_checksum"].item() == second["stress_checksum"].item()
