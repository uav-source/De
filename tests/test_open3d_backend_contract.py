import inspect

from zero_perturbation.open3d_backend import REQUIRED_OPEN3D_VERSION, run_open3d_full
from zero_perturbation_test_support import development_protocol


def test_open3d_backend_has_one_global_point_to_plane_contract():
    config = development_protocol().section("open3d_registration")
    assert REQUIRED_OPEN3D_VERSION == "0.19.0+b012259"
    assert config["registration_method"] == "point_to_plane"
    assert config["maximum_correspondence_distance_m"] == 0.50
    assert config["scene_specific_parameters"] is False
    assert "scene_variant" not in inspect.signature(run_open3d_full).parameters
