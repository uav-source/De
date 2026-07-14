import numpy as np

from minibench.correspondence_stress import apply_correspondence_stress
from stage2b_helpers import simple_observations, stress_config


def test_selected_patch_slip_persists_for_eight_frames():
    observations = simple_observations(frames=12)
    axial = observations["is_axial_support"]
    patches = np.where(axial, "axial_patch", "shell_patch")
    output = apply_correspondence_stress(observations, "axial_correspondence_slip", stress_config(), "stage2b", 1, 2, patches)
    active_frames = np.flatnonzero(np.any(output["contamination_mask"], axis=1))
    assert active_frames.size == 8
    assert np.all(np.diff(active_frames) == 1)
    assert output["contaminated_patch_burst_start_frames"].tolist() == [int(active_frames[0])]
    assert output["contaminated_patch_burst_signs"].tolist()[0] in {-1, 1}
