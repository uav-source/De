from pathlib import Path

from fastlio2_adapter.frozen_observation_archive import audit_archive_modes


def normalized_tree(tmp_path: Path) -> Path:
    root = tmp_path / "frozen"
    child = root / "index"
    child.mkdir(parents=True)
    (child / "record.csv").write_text("record_index\n", encoding="utf-8")
    root.chmod(0o755)
    child.chmod(0o755)
    (child / "record.csv").chmod(0o644)
    return root


def test_normalized_tree_passes(tmp_path: Path):
    assert audit_archive_modes(normalized_tree(tmp_path))[
        "archive_mode_normalization_pass"
    ] is True


def test_child_directory_wrong_mode_fails(tmp_path: Path):
    root = normalized_tree(tmp_path)
    (root / "index").chmod(0o775)
    audit = audit_archive_modes(root)
    assert audit["directory_mode_violation_count"] == 1
    assert audit["archive_mode_normalization_pass"] is False


def test_regular_file_wrong_mode_fails(tmp_path: Path):
    root = normalized_tree(tmp_path)
    (root / "index/record.csv").chmod(0o664)
    audit = audit_archive_modes(root)
    assert audit["regular_file_mode_violation_count"] == 1
    assert audit["archive_mode_normalization_pass"] is False
