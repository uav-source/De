import numpy as np

from anchor_audit_test_support import ROOT
from capture_range.anchor_validity_audit import (
    absolute_accuracy_valid,
    load_anchor_audit_protocol,
)


def test_anchor_absolute_accuracy_gate_includes_boundaries_and_rejects_excess():
    protocol = load_anchor_audit_protocol(ROOT)
    rotation = np.deg2rad(0.5)
    assert absolute_accuracy_valid(0.02, rotation, protocol) is True
    assert absolute_accuracy_valid(0.0200000001, rotation, protocol) is False
    assert absolute_accuracy_valid(0.02, rotation + 1.0e-12, protocol) is False
