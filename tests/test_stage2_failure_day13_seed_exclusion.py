from copy import deepcopy
from pathlib import Path

import pytest

from eval.stage2_failure_day13_seeds import (
    build_seed_exclusion_manifest,
    validate_seed_exclusion_manifest,
)


ROOT = Path(__file__).resolve().parents[1]


def test_real_historical_seed_scan_is_parseable_and_disjoint():
    manifest = build_seed_exclusion_manifest(ROOT)
    assert manifest["source_paths"]
    assert manifest["parse_errors"] == []
    assert manifest["audit_pass"] is True
    assert manifest["historical_overlap_count"] == 0


def test_edited_or_overlapping_generated_seed_is_rejected():
    manifest = deepcopy(build_seed_exclusion_manifest(ROOT))
    manifest["new_calibration_geometry_seeds"][0] = manifest["historical_geometry_seeds"][0]
    with pytest.raises(ValueError):
        validate_seed_exclusion_manifest(manifest)


def test_calibration_evaluation_seed_overlap_is_rejected():
    manifest = deepcopy(build_seed_exclusion_manifest(ROOT))
    manifest["new_evaluation_sensor_seeds"][0] = manifest["new_calibration_sensor_seeds"][0]
    with pytest.raises(ValueError):
        validate_seed_exclusion_manifest(manifest)
