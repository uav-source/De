from backend_qualification_test_support import ROOT, qualification_protocol
from zero_perturbation.pcl_backend import frozen_parameters


def test_pcl_normal_estimation_is_single_threaded_and_contract_is_stable():
    source = (ROOT / "tools/pcl_point_to_plane/pcl_point_to_plane_cli.cpp").read_text()
    assert "setNumberOfThreads(1)" in source
    section = qualification_protocol()["pcl_iterative_closest_point_with_normals"]
    assert frozen_parameters(section) == frozen_parameters(section)

