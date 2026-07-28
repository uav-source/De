import inspect

from backend_qualification_test_support import ROOT, qualification_protocol
from zero_perturbation.pcl_backend import run_pcl_point_to_plane


def test_pcl_adapter_has_no_scene_switch_input():
    assert "scene_variant" not in inspect.signature(run_pcl_point_to_plane).parameters
    assert qualification_protocol()["backend_contract"][
        "scene_specific_parameters_forbidden"
    ] is True
    source = (ROOT / "tools/pcl_point_to_plane/pcl_point_to_plane_cli.cpp").read_text()
    assert 'config.at("scene_variant")' not in source

