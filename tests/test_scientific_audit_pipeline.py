from pathlib import Path

from eval.measurement_pilot_scientific_audit import (
    EXPECTED_PILOT_TREE_SHA256,
    REQUIRED_FIGURES,
    REQUIRED_REPORTS,
    REQUIRED_TABLES,
    final_decision,
    tree_sha256,
    write_checksum_manifest,
)


ROOT = Path(__file__).resolve().parents[1]


def test_pipeline_contract_has_complete_outputs_and_category_b_decision():
    assert len(REQUIRED_TABLES) == 16
    assert len(REQUIRED_FIGURES) == 9
    assert len(REQUIRED_REPORTS) == 10
    evidence = {
        "metric_direction_bug_confirmed": True,
        "time_alignment_bug_confirmed": False,
        "frame_transform_bug_confirmed": False,
        "future_error_implementation_bug_confirmed": True,
        "trigger_implementation_bug_confirmed": False,
        "odi_exactly_equivalent": True,
        "odi_monotonically_equivalent": True,
        "pilot_label_invalidated": True,
        "reference_insufficient": True,
        "reliability_validation_sufficient": False,
        "real_domain_threshold_transfer_failed": True,
        "corrected_evaluation_changes_formal_conclusion": False,
        "method_negative_criteria_satisfied": True,
    }
    decision = final_decision(**evidence)
    assert decision["PRIMARY_CONCLUSION_CATEGORY"] == "B"
    assert decision["PILOT_LABEL_INVALIDATED"] is True
    assert decision["EVALUATION_BUG_CONFIRMED"] is False
    assert decision["METHOD_NEGATIVE_CONFIRMED"] is False
    assert decision["SECOND_DATASET_EXPANSION_AUTHORIZED"] is False


def test_decision_rule_is_evidence_driven_for_all_four_primary_categories():
    base = {
        "metric_direction_bug_confirmed": False,
        "time_alignment_bug_confirmed": False,
        "frame_transform_bug_confirmed": False,
        "future_error_implementation_bug_confirmed": False,
        "trigger_implementation_bug_confirmed": False,
        "odi_exactly_equivalent": False,
        "odi_monotonically_equivalent": False,
        "pilot_label_invalidated": False,
        "reference_insufficient": False,
        "reliability_validation_sufficient": False,
        "real_domain_threshold_transfer_failed": False,
        "corrected_evaluation_changes_formal_conclusion": False,
        "method_negative_criteria_satisfied": False,
    }
    category_a = dict(base)
    category_a.update(
        metric_direction_bug_confirmed=True,
        corrected_evaluation_changes_formal_conclusion=True,
    )
    assert final_decision(**category_a)["PRIMARY_CONCLUSION_CATEGORY"] == "A"

    category_b = dict(base, pilot_label_invalidated=True)
    assert final_decision(**category_b)["PRIMARY_CONCLUSION_CATEGORY"] == "B"

    category_c = dict(base, reference_insufficient=True)
    assert final_decision(**category_c)["PRIMARY_CONCLUSION_CATEGORY"] == "C"

    category_d = dict(base, method_negative_criteria_satisfied=True)
    assert final_decision(**category_d)["PRIMARY_CONCLUSION_CATEGORY"] == "D"


def test_original_pilot_tree_is_immutable_and_checksum_manifest_is_complete(tmp_path):
    assert tree_sha256(
        ROOT / "artifacts/current/measurement_real_validation_pilot", ROOT
    ) == EXPECTED_PILOT_TREE_SHA256
    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested/b.txt").write_text("b\n", encoding="utf-8")
    write_checksum_manifest(tmp_path)
    lines = (tmp_path / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    assert [line.split("  ", 1)[1] for line in lines] == ["a.txt", "nested/b.txt"]
