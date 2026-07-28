from backend_phase_a_test_support import ROOT, artifact_json, protocol
from zero_perturbation.backend_phase_a_protocol import file_sha256


def test_pcl_v3_parameters_and_cli_source_are_frozen():
    phase = protocol()
    parameters = phase.data["pcl_parameter_contract"]["parameters"]
    assert parameters["version"] == "1.15.1"
    assert parameters["normal_estimation"]["k"] == 50
    assert parameters["icp"] == {
        "maximum_correspondence_distance_m": 0.5,
        "maximum_iterations": 50,
        "transformation_epsilon": 1.0e-10,
        "euclidean_fitness_epsilon": 1.0e-10,
        "use_reciprocal_correspondences": False,
        "use_symmetric_objective": False,
        "enforce_same_direction_normals": True,
    }
    lock = artifact_json("backend_parameter_contract.json")
    assert lock["PCL_PARAMETER_LOCK_PASS"] is True
    source = phase.data["immutable_inputs"]["pcl_cli"]
    assert file_sha256(ROOT / source["path"]) == source["sha256"]
