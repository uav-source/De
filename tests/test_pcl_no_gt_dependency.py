import inspect

from backend_qualification_test_support import ROOT, qualification_decision
from zero_perturbation.pcl_backend import run_pcl_point_to_plane


def test_pcl_backend_rejects_gt_and_has_no_gt_argument():
    parameters = inspect.signature(run_pcl_point_to_plane).parameters
    assert not {"gt", "ground_truth", "reference_error", "weak_direction"} & set(parameters)
    source = (ROOT / "tools/pcl_point_to_plane/pcl_point_to_plane_cli.cpp").read_text()
    assert '"ground_truth"' in source and '"offline_error"' in source
    assert qualification_decision()["gt_optimization_leakage_count"] == 0

