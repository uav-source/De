import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval.detector_stage2a_lock import verify_detector_lock  # noqa: E402
from eval.detector_stage2a import validate_reserved_seeds  # noqa: E402


def test_lock_requires_frozen_threshold(monkeypatch, tmp_path):
    monkeypatch.setattr("eval.detector_stage2a_lock.compute_source_tree_snapshot", lambda paths: ("s", {}))
    monkeypatch.setattr("eval.detector_stage2a_lock.compute_bundle_hash", lambda paths: "c")
    monkeypatch.setattr("eval.detector_stage2a_lock.git_status_clean", lambda root: True)
    with pytest.raises(RuntimeError, match="threshold missing"):
        verify_detector_lock(tmp_path, {"source_tree_sha256": "s", "config_bundle_sha256": "c"})


def test_lock_rejects_reserved_seed_mutation():
    lock = {
        "reserved_test_geometry_seeds": [1709, 1823],
        "reserved_test_sensor_seeds": [55, 66],
    }
    with pytest.raises(RuntimeError, match="geometry seeds"):
        validate_reserved_seeds(
            {"geometry_seeds": [1709, 1907], "sensor_seeds": [55, 66]}, lock
        )
