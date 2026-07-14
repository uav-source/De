from pathlib import Path
import sys

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval.detector_stage2a_lock import calibrate_odi_trigger_threshold  # noqa: E402


def test_threshold_is_frozen_from_development_open_control_quantile():
    values = np.arange(1.0, 21.0)
    assert calibrate_odi_trigger_threshold(values, 0.95) == pytest.approx(
        np.quantile(values, 0.95)
    )


def test_threshold_refuses_empty_or_invalid_calibration_inputs():
    with pytest.raises(ValueError, match="Open Control"):
        calibrate_odi_trigger_threshold(np.array([np.nan]))
    with pytest.raises(ValueError, match="strictly between"):
        calibrate_odi_trigger_threshold(np.array([0.1]), 1.0)
