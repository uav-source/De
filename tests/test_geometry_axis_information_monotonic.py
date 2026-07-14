from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from degen_detector.odi_tracker import compute_metrics_for_sequence  # noqa: E402
from eval.synthetic_pipeline_common import load_yaml  # noqa: E402


def test_raw_axis_information_is_monotonic_for_every_frame(nested_geometry_outputs):
    config = load_yaml(ROOT / "configs/detector/odi_stage2a.yaml")
    values = {
        level: compute_metrics_for_sequence(observations, config)["axis_information_raw"]
        for level, observations in nested_geometry_outputs.items()
    }
    assert np.all(values["L1"] + 1.0e-8 >= values["L2"])
    assert np.all(values["L2"] + 1.0e-8 >= values["L3"])
    assert np.all(values["L3"] + 1.0e-8 >= values["L4"])
