from degen_detector.odi_tracker import evaluate_trigger_direction_state
from eval.interval_validity_audit import ODI_TRIGGER_THRESHOLD


def test_trigger_is_high_odi_greater_equal_frozen_threshold():
    assert ODI_TRIGGER_THRESHOLD == 0.035199792993590634
    assert evaluate_trigger_direction_state(ODI_TRIGGER_THRESHOLD, ODI_TRIGGER_THRESHOLD, False) == (
        True,
        False,
    )
    assert evaluate_trigger_direction_state(ODI_TRIGGER_THRESHOLD - 1e-12, ODI_TRIGGER_THRESHOLD, True) == (
        False,
        False,
    )
