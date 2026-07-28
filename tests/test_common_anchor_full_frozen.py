import numpy as np

from anchor_audit_test_support import ROOT
from capture_range.anchor_validity_audit import (
    common_anchor_eligible,
    load_anchor_audit_protocol,
)


def test_common_anchor_eligibility_uses_frozen_absolute_thresholds():
    protocol = load_anchor_audit_protocol(ROOT)
    anchor = np.eye(4)
    boundary = anchor.copy()
    boundary[0, 3] = 0.02
    eligible, translation, rotation = common_anchor_eligible(boundary, anchor, protocol)
    assert eligible is True
    assert translation == 0.02
    assert rotation == 0.0
    outside = anchor.copy()
    outside[0, 3] = 0.0200001
    assert common_anchor_eligible(outside, anchor, protocol)[0] is False
