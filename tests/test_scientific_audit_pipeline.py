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
    decision = final_decision()
    assert decision["PRIMARY_CONCLUSION_CATEGORY"] == "B"
    assert decision["PILOT_LABEL_INVALIDATED"] is True
    assert decision["EVALUATION_BUG_CONFIRMED"] is False
    assert decision["METHOD_NEGATIVE_CONFIRMED"] is False
    assert decision["SECOND_DATASET_EXPANSION_AUTHORIZED"] is False


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
