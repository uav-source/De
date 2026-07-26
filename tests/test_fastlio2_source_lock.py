from __future__ import annotations

import copy
import json
import os
import subprocess
from pathlib import Path

from fastlio2_adapter.source_lock import (
    RUNTIME_OUTPUT_PATHS,
    canonical_json_bytes,
    compare_runtime_inventories,
    runtime_output_allowlist,
    runtime_output_inventory,
    snapshot_source_lock,
    source_lock_mismatches,
)


def run(*args, cwd):
    subprocess.run(args, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def repository(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    run("git", "init", "-q", cwd=root)
    run("git", "config", "user.name", "fixture", cwd=root)
    run("git", "config", "user.email", "fixture@example.invalid", cwd=root)
    (root / ".gitignore").write_text("Log/*.txt\nLog/*.csv\nPCD/*.pcd\nbuild/\ndevel/\ninstall/\n")
    (root / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.0)\n")
    (root / "package.xml").write_text("<package/>\n")
    (root / "tracked.cpp").write_text("int value = 1;\n")
    run("git", "add", ".", cwd=root)
    run("git", "commit", "-qm", "fixture", cwd=root)
    return root


def snapshot(root: Path, binary: Path | None = None):
    return snapshot_source_lock(
        root,
        repo_alias="FAST_LIO",
        binary_path=binary,
        binary_path_alias="$FAST_WS/devel/lib/fast_lio/fastlio_mapping" if binary else None,
    )


def test_tracked_file_modification_fails_source_lock(tmp_path):
    root = repository(tmp_path); before = snapshot(root)
    (root / "tracked.cpp").write_text("int value = 2;\n")
    assert source_lock_mismatches(before, snapshot(root))


def test_tracked_file_deletion_fails_source_lock(tmp_path):
    root = repository(tmp_path); before = snapshot(root)
    (root / "tracked.cpp").unlink()
    after = snapshot(root)
    assert source_lock_mismatches(before, after)
    assert next(row for row in after["source_files"] if row["path"] == "tracked.cpp")["file_type"] == "missing"


def test_nonignored_untracked_cpp_fails_source_lock(tmp_path):
    root = repository(tmp_path); before = snapshot(root)
    (root / "new.cpp").write_text("int extra;\n")
    after = snapshot(root)
    assert after["untracked_nonignored_paths"] == ["new.cpp"]
    assert source_lock_mismatches(before, after)


def test_ignored_mat_pre_change_does_not_change_source_lock(tmp_path):
    root = repository(tmp_path); (root / "Log").mkdir()
    path = root / "Log/mat_pre.txt"; path.write_text("before\n")
    before = snapshot(root); path.write_text("after\n")
    assert source_lock_mismatches(before, snapshot(root)) == []


def test_allowed_runtime_output_change_passes_allowlist(tmp_path):
    root = repository(tmp_path); (root / "Log").mkdir()
    before = runtime_output_inventory(root)
    (root / "Log/mat_pre.txt").write_text("runtime\n")
    result = compare_runtime_inventories(before, runtime_output_inventory(root))
    assert result["allowlist_pass"] is True
    assert result["changed_paths"] == ["Log/mat_pre.txt"]


def test_unknown_log_output_fails_allowlist(tmp_path):
    root = repository(tmp_path); (root / "Log").mkdir()
    before = runtime_output_inventory(root)
    (root / "Log/unexpected.bin").write_bytes(b"unexpected")
    result = compare_runtime_inventories(before, runtime_output_inventory(root))
    assert result["allowlist_pass"] is False
    assert result["unexpected_runtime_output_count"] == 1


def test_disabled_pcd_output_may_be_absent(tmp_path):
    root = repository(tmp_path)
    result = compare_runtime_inventories(runtime_output_inventory(root), runtime_output_inventory(root))
    assert result["allowlist_pass"] is True
    pcd = next(row for row in runtime_output_inventory(root)["records"] if row["path"] == "PCD/scans.pcd")
    assert pcd["exists"] is False


def test_submodule_commit_change_fails_source_lock_comparison(tmp_path):
    root = repository(tmp_path); before = snapshot(root); after = copy.deepcopy(before)
    before["submodule_count"] = after["submodule_count"] = 1
    before["submodule_paths_and_commits"] = [{"path": "include/ikd-Tree", "commit": "a" * 40, "state": " "}]
    after["submodule_paths_and_commits"] = [{"path": "include/ikd-Tree", "commit": "b" * 40, "state": " "}]
    assert any(row["field"] == "submodule_paths_and_commits" for row in source_lock_mismatches(before, after))


def test_binary_sha_change_fails_same_source_identity(tmp_path):
    root = repository(tmp_path); binary = tmp_path / "fastlio_mapping"; binary.write_bytes(b"before")
    before = snapshot(root, binary); binary.write_bytes(b"after")
    assert any(row["field"] == "binary" for row in source_lock_mismatches(before, snapshot(root, binary)))


def test_file_mode_change_fails_source_lock(tmp_path):
    root = repository(tmp_path); before = snapshot(root)
    os.chmod(root / "tracked.cpp", 0o755)
    assert source_lock_mismatches(before, snapshot(root))


def test_source_lock_output_is_byte_sorted_and_deterministic(tmp_path):
    root = repository(tmp_path)
    (root / "z.cpp").write_text("z\n"); (root / "a.cpp").write_text("a\n")
    first = snapshot(root); second = snapshot(root)
    paths = [row["path"] for row in first["source_files"]]
    assert paths == sorted(paths, key=os.fsencode)
    assert canonical_json_bytes(first) == canonical_json_bytes(second)


def test_git_config_and_remote_url_are_not_recorded(tmp_path):
    root = repository(tmp_path)
    run("git", "remote", "add", "origin", "https://example.invalid/private.git", cwd=root)
    encoded = canonical_json_bytes(snapshot(root)).decode()
    assert ".git/config" not in encoded
    assert "example.invalid" not in encoded
    assert "private.git" not in encoded


def test_personal_absolute_path_is_not_recorded(tmp_path):
    root = repository(tmp_path)
    encoded = canonical_json_bytes(snapshot(root)).decode()
    assert str(root) not in encoded
    assert "/home/lj" not in encoded


def test_runtime_allowlist_is_exact_and_excluded_from_source_lock():
    value = runtime_output_allowlist()
    assert tuple(row["path"] for row in value["allowed_paths"]) == RUNTIME_OUTPUT_PATHS
    assert all(row["included_in_source_lock"] is False for row in value["allowed_paths"])
