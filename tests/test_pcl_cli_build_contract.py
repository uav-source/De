from backend_qualification_test_support import ROOT, qualification_decision


def test_cmake_build_contract_and_failed_identity_gate_are_preserved():
    cmake = (ROOT / "tools/pcl_point_to_plane/CMakeLists.txt").read_text()
    assert "find_package(PCL 1.15 REQUIRED" in cmake
    assert "pcl_identical_cloud_identity" in cmake
    assert "pcl_point_to_plane_cli" in cmake
    assert qualification_decision()["PCL_BACKEND_BUILD_PASS"] is False

