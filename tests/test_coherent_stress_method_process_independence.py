from pathlib import Path

import numpy as np

from minibench.correspondence_stress import apply_correspondence_stress
from stage2c_helpers import patch_ids, simple_observations, stress_config


def test_stress_is_deterministic_without_method_or_process_seed():
    observations = simple_observations(frames=30); patches = patch_ids(observations)
    first = apply_correspondence_stress(observations, "coherent_subhuber_slip", stress_config(), "stage2c", 5, 6, patches)
    second = apply_correspondence_stress(observations, "coherent_subhuber_slip", stress_config(), "stage2c", 5, 6, patches)
    assert str(first["stress_checksum"]) == str(second["stress_checksum"])
    source = (Path(__file__).parents[1] / "src/minibench/correspondence_stress.py").read_text()
    signature = source[source.index("def _digest"):]
    assert "method" not in signature and "process_seed" not in signature and "level" not in signature

