import inspect

from zero_perturbation.native_backend import run_native_pair
from zero_perturbation.open3d_backend import run_open3d_full


def test_backend_interfaces_exclude_scene_and_theoretical_gt_inputs():
    forbidden = ("scene", "weak", "direction", "ground_truth", "gt_")
    for function in (run_native_pair, run_open3d_full):
        names = tuple(inspect.signature(function).parameters)
        assert not any(token in name for name in names for token in forbidden)
