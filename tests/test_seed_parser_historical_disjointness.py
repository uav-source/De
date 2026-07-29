from pathlib import Path

from eval.stage2_failure_day13_seeds import build_seed_exclusion_manifest
from eval.synthetic_pipeline_common import load_yaml


ROOT = Path(__file__).resolve().parents[1]


def test_seed_parser_preserves_legacy_namespaces_and_disjointness() -> None:
    manifest = build_seed_exclusion_manifest(ROOT)
    assert manifest["parse_errors"] == []
    assert manifest["historical_source_parse_pass"] is True
    assert manifest["historical_overlap_count"] == 0
    assert manifest["calibration_evaluation_overlap_count"] == 0
    assert manifest["new_internal_duplicate_count"] == 0
    assert manifest["audit_pass"] is True

    development = load_yaml(ROOT / "configs/update/stage2c_development.yaml")
    reserved_test = load_yaml(ROOT / "configs/update/stage2c_test.yaml")
    for seed_type in ("geometry", "sensor", "process"):
        development_values = set(development[f"{seed_type}_seeds"])
        test_values = set(reserved_test[f"{seed_type}_seeds"])
        historical = set(manifest[f"historical_{seed_type}_seeds"])
        assert development_values <= historical
        assert test_values <= historical
        assert development_values.isdisjoint(test_values)

    assert {1850310744, 1957656152, 1334931069} <= set(
        manifest["historical_geometry_seeds"]
    )
    assert {217775206, 1664898153} <= set(manifest["historical_sensor_seeds"])
