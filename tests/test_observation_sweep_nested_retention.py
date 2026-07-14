from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from minibench.observation_simulator import simulate_observation_degradation  # noqa: E402
from stage1c_helpers import make_observation_sequence, paths  # noqa: E402


def test_observation_retention_is_nested_with_fixed_final_point_count(tmp_path):
    sequence_dir = make_observation_sequence(tmp_path)
    outputs = [
        simulate_observation_degradation(sequence_dir, paths()["detector"], 11, probability, 8)
        for probability in [1.0, 0.4, 0.1, 0.02]
    ]
    for output in outputs[1:]:
        assert np.array_equal(output["candidate_uniforms"], outputs[0]["candidate_uniforms"])
        assert np.array_equal(output["candidate_is_axial"], outputs[0]["candidate_is_axial"])
        assert output["packed_J"].shape == outputs[0]["packed_J"].shape
    masks = [output["retained_axial_candidate_mask"] for output in outputs]
    assert np.all(~masks[3] | masks[2]) and np.all(~masks[2] | masks[1]) and np.all(~masks[1] | masks[0])
    fractions = [float(np.mean(output["is_axial_support"])) for output in outputs]
    assert fractions[0] > fractions[1] > fractions[2] > fractions[3]
