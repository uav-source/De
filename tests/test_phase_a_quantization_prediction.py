from backend_phase_a_v1_2_test_support import synthetic_snapshot, transform
from zero_perturbation.backend_phase_a_v1_2 import quantization_closure


def test_predicted_quantization_explains_actual_reconstruction_error():
    snapshot = synthetic_snapshot()
    parents = snapshot.target_points[snapshot.parent_indices].astype(float)
    report = quantization_closure(
        source_points=snapshot.source_points,
        source_float64=snapshot.source_float64,
        parent_points_map_float64=parents,
        reference_pose=transform(),
    )
    assert report["quantization_closure_pass"] is True
    assert report["reconstruction_error_max_m"] <= report["predicted_quantization_max_m"] + report["float64_guard_max_m"]
