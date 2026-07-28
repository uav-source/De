import json

from pcl_backend_v2_test_support import ARTIFACT


def test_v2_stops_after_test_b_rotation_gate_without_phase_authorization():
    decision = json.loads((ARTIFACT / "final_decision.json").read_text())
    assert decision["V2_TEST_A_NONDEGENERATE_IDENTITY_PASS"] is True
    assert decision["V2_TEST_B_KNOWN_SMALL_TRANSFORM_PASS"] is False
    assert decision["V2_TEST_C_PLANAR_DEGENERACY_DIAGNOSTIC_PASS"] is True
    assert decision["PCL_BACKEND_IMPLEMENTATION_VALID"] is False
    assert decision["PCL_BACKEND_PHASE_A_QUALIFICATION_AUTHORIZED"] is False
    assert decision["phase_a_executed"] is False
    assert decision["phase_b_executed"] is False
    assert decision["seed_access_count"] == 0
