import json

from backend_qualification_test_support import ROOT


def test_isolated_pcl_dependency_probe_is_real_and_open3d_env_is_unchanged():
    report = ROOT / "reports/zero_perturbation_pcl_environment"
    versions = json.loads((report / "package_versions.json").read_text())
    probes = (report / "pkg_config_versions.txt").read_text()
    assert versions["dependency_ready"] is True
    assert versions["packages"]["pcl"] == "1.15.1"
    assert versions["required_pkg_config_probe"]["stdout"] == "1.15.1"
    assert "pcl_registration=1.15.1" in probes
    assert versions["open3d_environment_modified"] is False

