import json

from pcl_backend_v3_test_support import ARTIFACT, ROOT, protocol_v3


def test_v3_metric_and_microtest_execution_never_access_seed_schedules():
    protocol = protocol_v3()
    assert protocol["protocol"]["development_seed_access_authorized"] is False
    assert protocol["protocol"]["confirmatory_seed_access_authorized"] is False
    manifest = json.loads((ARTIFACT / "run_manifest.json").read_text())
    assert manifest["seed_access_count"] == 0
    assert manifest["development_run_executed"] is False
    assert manifest["confirmatory_run_executed"] is False
    for relative in (
        "src/zero_perturbation/rotation_metrics.py",
        "tools/pcl_point_to_plane/rotation_metric_v3.hpp",
        "tools/pcl_point_to_plane/rotation_metric_v3_cli.cpp",
        "tools/pcl_point_to_plane/verify_pcl_backend_v3.py",
    ):
        source = (ROOT / relative).read_text().lower()
        assert "seed_schedule" not in source
        assert "geometry_seed" not in source
