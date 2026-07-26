import tarfile
from pathlib import Path

from fastlio2_adapter.frozen_observation_archive import (
    audit_archive,
    audit_archive_modes,
    audit_tree,
    build_deterministic_archive,
    verify_internal_sha256s,
    write_internal_sha256s,
)


def source_tree(tmp_path: Path) -> Path:
    root = tmp_path / "frozen"
    root.mkdir()
    (root / "record.json").write_text('{"pass":true}\n')
    return root


def test_internal_sha256s_round_trip(tmp_path):
    root = source_tree(tmp_path)
    assert write_internal_sha256s(root) == 1
    assert verify_internal_sha256s(root)["internal_hash_pass"] is True


def test_internal_sha256_detects_mutation(tmp_path):
    root = source_tree(tmp_path)
    write_internal_sha256s(root)
    (root / "record.json").write_text("changed\n")
    assert verify_internal_sha256s(root)["internal_hash_failure_count"] == 1


def test_deterministic_tar_twice_has_same_sha(tmp_path):
    root = source_tree(tmp_path)
    write_internal_sha256s(root)
    first = build_deterministic_archive(
        root, tmp_path / "a.tar", tmp_path / "a.tar.gz"
    )
    second = build_deterministic_archive(
        root, tmp_path / "b.tar", tmp_path / "b.tar.gz"
    )
    assert first == second


def test_tree_rejects_bag_and_symlink(tmp_path):
    root = source_tree(tmp_path)
    (root / "clip.bag").write_bytes(b"bag")
    (root / "link").symlink_to(root / "record.json")
    audit = audit_tree(root)
    assert audit["bag_file_count"] == 1
    assert audit["symbolic_link_count"] == 1
    assert audit["tree_scope_pass"] is False


def test_archive_rejects_detector_output(tmp_path):
    root = source_tree(tmp_path)
    (root / "detector_output.json").write_text("{}\n")
    with tarfile.open(tmp_path / "bad.tar.gz", "w:gz") as archive:
        archive.add(root, arcname=root.name)
    audit = audit_archive(tmp_path / "bad.tar.gz")
    assert audit["detector_output_file_count"] == 1
    assert audit["archive_scope_pass"] is False


def test_archive_root_0775_fails_mode_audit(tmp_path):
    root = source_tree(tmp_path)
    root.chmod(0o775)
    audit = audit_archive_modes(root)
    assert audit["root_mode"] == "0775"
    assert audit["archive_mode_normalization_pass"] is False


def test_archive_root_0755_and_files_0644_pass(tmp_path):
    root = source_tree(tmp_path)
    root.chmod(0o755)
    (root / "record.json").chmod(0o644)
    assert audit_archive_modes(root)["archive_mode_normalization_pass"] is True
