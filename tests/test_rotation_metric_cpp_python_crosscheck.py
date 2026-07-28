import json

from pcl_backend_v3_test_support import ARTIFACT


def test_cpp_eigen_and_python_numpy_rotation_metrics_crosscheck():
    for name in ("a", "b"):
        result = json.loads((ARTIFACT / f"test_{name}_result.json").read_text())
        assert result["ROTATION_METRIC_CROSSCHECK_PASS"] is True
        assert result["smaller_value_selection_used"] is False
        assert result["rotation_metric_abs_difference_rad"] <= 1.0e-10
        assert result["cpp_rotation_metric"]["projection_reflection_handling"] == (
            "D=diag(1,1,sign(det(U*V^T)))"
        )
