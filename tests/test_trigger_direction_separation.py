from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from degen_detector.odi_tracker import evaluate_trigger_direction_state  # noqa: E402


def test_trigger_and_direction_stability_are_independent():
    assert evaluate_trigger_direction_state(0.8, 0.5, False) == (True, False)
    assert evaluate_trigger_direction_state(0.2, 0.5, True) == (False, False)
    assert evaluate_trigger_direction_state(0.8, 0.5, True) == (True, True)
