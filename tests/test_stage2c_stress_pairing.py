import numpy as np

from minibench.correspondence_stress import apply_correspondence_stress
from stage2c_helpers import patch_ids, simple_observations, stress_config


def test_stress_pairing_and_open_control_zero_contamination():
    observations = simple_observations(frames=30); patches = patch_ids(observations)
    checksums = [str(apply_correspondence_stress(observations, "coherent_subhuber_slip", stress_config(), "stage2c", 9, 10, patches)["stress_checksum"]) for _method in range(5)]
    assert len(set(checksums)) == 1
    open_control = simple_observations(frames=30)
    open_control["is_axial_support"][:] = False
    shell_ids = np.full(open_control["is_axial_support"].shape, "shell")
    stressed = apply_correspondence_stress(open_control, "coherent_subhuber_slip", stress_config(), "stage2c", 9, 10, shell_ids)
    assert not np.any(stressed["contamination_mask"])
    clean = apply_correspondence_stress(observations, "clean", stress_config(), "stage2c", 9, 10, patches)
    for field in observations:
        assert np.array_equal(clean[field], observations[field])
