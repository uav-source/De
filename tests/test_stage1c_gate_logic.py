from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from eval.metric_redesign_stage1c import authorization_decisions  # noqa: E402


def test_detector_and_prediction_authorizations_are_independent():
    assert authorization_decisions(True, True, True, "PREDICTION_FAIL") == {
        "WEAK_UPDATE_AUTHORIZED": True,
        "RISK_WARNING_AUTHORIZED": False,
    }
    assert authorization_decisions(True, True, False, "PREDICTION_PASS") == {
        "WEAK_UPDATE_AUTHORIZED": False,
        "RISK_WARNING_AUTHORIZED": True,
    }
    assert authorization_decisions(True, True, True, "PREDICTION_PASS") == {
        "WEAK_UPDATE_AUTHORIZED": True,
        "RISK_WARNING_AUTHORIZED": True,
    }
    assert not any(authorization_decisions(False, True, True, "PREDICTION_PASS").values())
