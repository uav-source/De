import inspect

from backend_qualification_test_support import ROOT
from zero_perturbation.pcl_backend import run_pcl_point_to_plane


def test_pcl_initial_transform_is_required_and_passed_to_align():
    assert "initial_transformation" in inspect.signature(run_pcl_point_to_plane).parameters
    source = (ROOT / "tools/pcl_point_to_plane/pcl_point_to_plane_cli.cpp").read_text()
    assert "icp.align(aligned, initial);" in source
    assert 'config.at("initial_transformation_4x4")' in source

