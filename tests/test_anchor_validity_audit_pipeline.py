import hashlib
import json

import pytest

from capture_range.anchor_validity_pipeline import (
    FIGURE_FILES,
    TABLE_FILES,
    TOP_LEVEL_FILES,
    verify_anchor_validity_audit_output,
)


def _write_complete_fixture(root):
    tables = root / "tables"
    figures = root / "figures"
    tables.mkdir(parents=True)
    figures.mkdir()
    for name in TABLE_FILES:
        (tables / name).write_text("header\n", encoding="utf-8")
    for name in FIGURE_FILES:
        (figures / name).write_bytes(b"\x89PNG\r\n\x1a\n")
    (root / "anchor_validity_report.md").write_text("# audit\n", encoding="utf-8")
    (root / "run_manifest.json").write_text(
        json.dumps({"formal_zero_row_count": 420, "noise_ablation_row_count": 1680}) + "\n",
        encoding="utf-8",
    )
    (root / "final_decision.json").write_text(
        json.dumps({"CONFIRMATORY_TEST_AUTHORIZED": False}) + "\n",
        encoding="utf-8",
    )
    paths = sorted(path for path in root.rglob("*") if path.is_file())
    lines = [
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(root).as_posix()}"
        for path in paths
    ]
    (root / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_pipeline_output_contract_requires_exact_files_checksums_and_fixed_test_false(tmp_path):
    artifact = tmp_path / "audit"
    _write_complete_fixture(artifact)
    verified = verify_anchor_validity_audit_output(artifact)
    assert verified["decision"]["CONFIRMATORY_TEST_AUTHORIZED"] is False
    assert len(TABLE_FILES) == 11
    assert len(FIGURE_FILES) == 6
    assert set(TOP_LEVEL_FILES) == {
        "anchor_validity_report.md",
        "run_manifest.json",
        "final_decision.json",
        "SHA256SUMS",
    }
    (artifact / "tables" / TABLE_FILES[0]).write_text("changed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum mismatch"):
        verify_anchor_validity_audit_output(artifact)
