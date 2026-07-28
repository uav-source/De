from backend_qualification_test_support import ROOT, qualification_decision


def test_cmake_build_contract_preserves_v1_failure_and_uses_three_v2_verifiers():
    cmake = (ROOT / "tools/pcl_point_to_plane/CMakeLists.txt").read_text()
    assert "find_package(PCL 1.15 REQUIRED" in cmake
    assert "pcl_point_to_plane_cli" in cmake
    assert cmake.count("NAME pcl_v2_") == 3
    assert "pcl_v2_nondegenerate_identity" in cmake
    assert "pcl_v2_known_small_transform" in cmake
    assert "pcl_v2_planar_degeneracy_diagnostic" in cmake
    assert "PASS_REGULAR_EXPRESSION" not in cmake
    assert qualification_decision()["PCL_BACKEND_BUILD_PASS"] is False
