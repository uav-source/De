import numpy as np

from anchor_audit_test_support import ROOT
from capture_range.anchor_validity_audit import (
    EXPECTED_CANDIDATES,
    load_anchor_audit_protocol,
    pose_from_json,
    pose_json,
    repeat_cluster_count,
)


def test_candidate_set_pose_serialization_and_repeat_clustering_are_frozen():
    protocol = load_anchor_audit_protocol(ROOT)
    assert tuple(protocol.section("anchor_candidates")["candidates_in_order"]) == EXPECTED_CANDIDATES
    pose = np.eye(4)
    np.testing.assert_array_equal(pose_from_json(pose_json(pose)), pose)
    near = pose.copy()
    near[0, 3] = 0.01
    far = pose.copy()
    far[0, 3] = 0.05
    assert repeat_cluster_count([pose, near], protocol) == 1
    assert repeat_cluster_count([pose, far], protocol) == 2
