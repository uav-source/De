import pandas as pd

from backend_qualification_test_support import ARTIFACT, qualification_decision


def test_diversity_is_not_falsely_claimed_after_build_gate_stop():
    inventory = pd.read_csv(ARTIFACT / "tables/ideal_matched_snapshot_inventory.csv")
    assert len(inventory) == 0
    decision = qualification_decision()
    assert decision["IDEAL_MATCHED_SNAPSHOT_DIVERSITY_PASS"] is False
    assert decision["IDEAL_MATCHED_SNAPSHOT_DIVERSITY_STATUS"] == "NOT_EVALUATED"

