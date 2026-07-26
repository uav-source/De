from pathlib import Path

from fastlio2_adapter.frozen_observation_archive import (
    redact_personal_paths,
    sanitize_text_copy,
    scan_personal_absolute_paths,
)


def personal_path(prefix: str, user: str, suffix: str = "file.json") -> str:
    return prefix + user + "/" + suffix


def test_posix_and_macos_personal_paths_are_detected(tmp_path: Path):
    root = tmp_path / "tree"
    root.mkdir()
    values = [
        personal_path("/" + "home" + "/", "lj"),
        "/" + "root" + "/secret.txt",
        personal_path("/" + "Users" + "/", "name"),
    ]
    (root / "paths.txt").write_text("\n".join(values), encoding="utf-8")
    audit = scan_personal_absolute_paths(root)
    assert audit["content_absolute_path_count"] == 3
    assert audit["content_absolute_path_scan_pass"] is False


def test_windows_personal_path_is_detected(tmp_path: Path):
    root = tmp_path / "tree"
    root.mkdir()
    value = "C:" + "\\" + "Users" + "\\" + "name" + "\\" + "file.txt"
    (root / "path.txt").write_text(value, encoding="utf-8")
    assert scan_personal_absolute_paths(root)[
        "content_absolute_path_count"
    ] == 1


def test_aliases_and_system_paths_pass(tmp_path: Path):
    root = tmp_path / "tree"
    root.mkdir()
    (root / "paths.txt").write_text(
        "$HOME/data\n<HOME>/data\n/opt/ros/noetic\n/usr/bin/python\n",
        encoding="utf-8",
    )
    assert scan_personal_absolute_paths(root)[
        "content_absolute_path_scan_pass"
    ] is True


def test_binary_file_is_not_decoded_as_text(tmp_path: Path):
    root = tmp_path / "tree"
    root.mkdir()
    payload = (
        b"\0"
        + ("/" + "home" + "/lj/private").encode("utf-8")
    )
    (root / "records.bin").write_bytes(payload)
    audit = scan_personal_absolute_paths(root)
    assert audit["content_text_file_count"] == 0
    assert audit["content_absolute_path_count"] == 0


def test_redaction_manifest_does_not_retain_raw_path(tmp_path: Path):
    source = tmp_path / "raw.txt"
    destination = tmp_path / "sanitized.txt"
    source.write_text(
        personal_path("/" + "home" + "/", "lj"),
        encoding="utf-8",
    )
    record = sanitize_text_copy(source, destination)
    assert record["replacement_count"] == 1
    assert record["raw_file_included"] is False
    assert "original_sha256" in record
    assert "sanitized_sha256" in record
    serialized = str(record)
    assert "private" not in serialized
    assert not scan_personal_absolute_paths(tmp_path)[
        "content_absolute_path_scan_pass"
    ]
    sanitized, count, _classes = redact_personal_paths(
        source.read_text(encoding="utf-8")
    )
    assert count == 1
    assert sanitized.startswith("<HOME>/")
