from pathlib import Path

import pytest

from eval.stage2_failure_day11b_lock import verify_day11a_case_lock
from eval.stage2_failure_day11b_plan import build_replay_plan, validate_replay_plan


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "results/stage2_failure_analysis/day11a_case_lock/stage2_failure_day11a_case_lock_v1/deterministic_diagnostic_case_lock.json"


@pytest.mark.parametrize("name", ["axial_correspondence_slip", "gross_outlier_control"])
def test_non_replay_stress_names_are_rejected(name):
    verification = verify_day11a_case_lock(ROOT, LOCK)
    rows = list(build_replay_plan(verification))
    rows[0] = {**rows[0], "stress": name}
    with pytest.raises(ValueError, match="matrix|stress"):
        validate_replay_plan(rows, verification)


def test_alias_cannot_convert_a_legacy_name_into_the_frozen_name():
    verification = verify_day11a_case_lock(ROOT, LOCK)
    rows = list(build_replay_plan(verification))
    alias_input = "axial_correspondence_slip"
    rows[0] = {**rows[0], "stress": alias_input}
    with pytest.raises(ValueError):
        validate_replay_plan(rows, verification)
