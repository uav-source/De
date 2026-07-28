import pytest

from capture_range.anchor_validity_audit import assert_optimizer_snapshot_metadata_safe


def test_optimizer_metadata_guard_accepts_measurement_identity_and_rejects_gt_roles():
    assert_optimizer_snapshot_metadata_safe(
        {
            "scene_variant": "sentinel",
            "geometry_seed": 1,
            "measurement_seed": 2,
            "repeat_index": 0,
        }
    )
    with pytest.raises(RuntimeError, match="GT or direction-role"):
        assert_optimizer_snapshot_metadata_safe({"direction_role": "weak"})
    with pytest.raises(RuntimeError, match="GT or direction-role"):
        assert_optimizer_snapshot_metadata_safe({"pose_gt": [0, 0, 0]})
