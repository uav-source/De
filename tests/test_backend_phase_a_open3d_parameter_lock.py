from backend_phase_a_test_support import ROOT, artifact_json, protocol
from zero_perturbation.backend_phase_a_protocol import file_sha256


def test_open3d_version_parameters_and_source_are_frozen():
    phase = protocol()
    parameters = phase.data["open3d_parameter_contract"]["parameters"]
    assert parameters["version"] == "0.19.0+b012259"
    assert parameters["maximum_correspondence_distance_m"] == 0.5
    assert parameters["target_normal_estimation"] == {"radius_m": 0.4, "max_nn": 50}
    assert parameters["convergence"] == {
        "relative_fitness": 1.0e-8,
        "relative_rmse": 1.0e-8,
        "max_iteration": 50,
    }
    lock = artifact_json("backend_parameter_contract.json")
    assert lock["OPEN3D_PARAMETER_LOCK_PASS"] is True
    source = phase.data["immutable_inputs"]["open3d_backend"]
    assert file_sha256(ROOT / source["path"]) == source["sha256"]
