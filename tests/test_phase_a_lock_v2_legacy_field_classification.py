from pathlib import Path

from zero_perturbation.phase_a_lock_architecture_v2 import legacy_field_classification


ROOT = Path(__file__).resolve().parents[1]


def test_all_legacy_paths_are_uniquely_classified() -> None:
    rows, summary = legacy_field_classification(ROOT)
    assert summary["LEGACY_LOCK_FIELD_CLASSIFICATION_PASS"] is True
    assert len(rows) == summary["legacy_field_total_count"] == 84
    assert summary["unclassified_field_count"] == 0
    assert summary["multiply_classified_field_count"] == 0

