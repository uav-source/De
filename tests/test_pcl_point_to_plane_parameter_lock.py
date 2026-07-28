from backend_qualification_test_support import qualification_protocol
from zero_perturbation.pcl_backend import frozen_parameters


def test_pcl_point_to_plane_parameters_match_the_frozen_contract():
    section = qualification_protocol()["pcl_iterative_closest_point_with_normals"]
    value = frozen_parameters(section)
    assert value["normal_estimation"] == {"method": "KSearch", "k": 50}
    assert value["icp"] == {
        "maximum_correspondence_distance_m": 0.50,
        "maximum_iterations": 50,
        "transformation_epsilon": 1.0e-10,
        "euclidean_fitness_epsilon": 1.0e-10,
        "use_reciprocal_correspondences": False,
        "use_symmetric_objective": False,
        "enforce_same_direction_normals": True,
    }

