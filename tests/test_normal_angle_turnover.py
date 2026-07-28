from types import SimpleNamespace

import numpy as np
import pytest

from zero_perturbation.correspondence_turnover import normal_angle_turnover


def test_normal_angle_turnover_is_axial_and_common_index_only():
    initial = SimpleNamespace(
        accepted_scan_indices=np.array([1, 2]),
        plane_normals=np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]),
    )
    final = SimpleNamespace(
        accepted_scan_indices=np.array([1, 3]),
        plane_normals=np.array([[-1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]),
    )
    result = normal_angle_turnover(initial, final)
    assert result["normal_angle_common_count"] == 1
    assert result["median_normal_angle_change_deg"] == pytest.approx(0.0)
