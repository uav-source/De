from backend_phase_a_test_support import protocol


def test_phase_a_plans_exactly_open3d_and_pcl():
    phase = protocol()
    assert phase.backends == (
        "open3d_point_to_plane",
        "pcl_iterative_closest_point_with_normals",
    )
    counts = phase.self_audit()
    assert counts["OPEN3D_PLANNED_TRIAL_COUNT"] == 210
    assert counts["PCL_PLANNED_TRIAL_COUNT"] == 210
