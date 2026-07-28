from phase_a_execution_chain_test_support import actual_execution_chain


def test_audit_never_plans_or_executes_native(actual_execution_chain):
    assert actual_execution_chain["manifest"]["NATIVE_EXECUTION_COUNT"] == 0
    assert all(row["backend"] in {"open3d_point_to_plane", "pcl_point_to_plane"} for row in actual_execution_chain["analysis"]["trial_inventory"])
