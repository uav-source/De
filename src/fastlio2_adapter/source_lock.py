"""Git-aware source identity and expected runtime-output auditing."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SOURCE_LOCK_SCHEMA_VERSION = "GIT_AWARE_SOURCE_LOCK_V2"
RUNTIME_ALLOWLIST_SCHEMA_VERSION = "FASTLIO2_RUNTIME_OUTPUT_ALLOWLIST_V2"

RUNTIME_OUTPUT_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "path": "Log/mat_pre.txt",
        "reason": "FAST-LIO2 matrix pre-update diagnostic output",
        "enabled_condition": "runtime execution may open this file even when runtime_pos_log_enable=false",
        "source_file": "src/laserMapping.cpp",
        "source_symbol": "fout_pre",
        "source_line": 1383,
        "open_mode": "ios::out",
        "included_in_source_lock": False,
    },
    {
        "path": "Log/mat_out.txt",
        "reason": "FAST-LIO2 matrix post-update diagnostic output",
        "enabled_condition": "runtime dependent",
        "source_file": "src/laserMapping.cpp",
        "source_symbol": "fout_out",
        "source_line": 1384,
        "open_mode": "ios::out",
        "included_in_source_lock": False,
    },
    {
        "path": "Log/dbg.txt",
        "reason": "FAST-LIO2 debug runtime output",
        "enabled_condition": "runtime dependent",
        "source_file": "src/laserMapping.cpp",
        "source_symbol": "fout_dbg",
        "source_line": 1385,
        "open_mode": "ios::out",
        "included_in_source_lock": False,
    },
    {
        "path": "Log/imu.txt",
        "reason": "IMU initialization diagnostic output",
        "enabled_condition": "opened after IMU initialization completes",
        "source_file": "src/IMU_Processing.hpp",
        "source_symbol": "fout_imu",
        "source_line": 376,
        "open_mode": "ios::out",
        "included_in_source_lock": False,
    },
    {
        "path": "Log/pos_log.txt",
        "reason": "FAST-LIO2 optional position runtime output",
        "enabled_condition": "runtime_pos_log_enable=true",
        "source_file": "src/laserMapping.cpp",
        "source_symbol": "fp",
        "source_line": 1380,
        "open_mode": "w",
        "included_in_source_lock": False,
    },
    {
        "path": "Log/fast_lio_time_log.csv",
        "reason": "FAST-LIO2 timing runtime output",
        "enabled_condition": "timing log enabled by build/runtime path",
        "source_file": "src/laserMapping.cpp",
        "source_symbol": "fp2",
        "source_line": 1707,
        "open_mode": "w",
        "included_in_source_lock": False,
    },
    {
        "path": "PCD/scans.pcd",
        "reason": "FAST-LIO2 optional accumulated map output",
        "enabled_condition": "pcd_save/pcd_save_en=true; absence is valid when false",
        "source_file": "src/laserMapping.cpp",
        "source_symbol": "pcd_writer.writeBinary",
        "source_line": 1696,
        "open_mode": "binary",
        "included_in_source_lock": False,
    },
)
RUNTIME_OUTPUT_PATHS = tuple(row["path"] for row in RUNTIME_OUTPUT_DEFINITIONS)
RUNTIME_OUTPUT_ROOTS = ("Log", "PCD")


class SourceLockError(RuntimeError):
    """Raised when source identity or runtime-output policy is violated."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _git(root: Path, arguments: Sequence[str]) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode:
        message = completed.stderr.decode("utf-8", "replace").strip()
        raise SourceLockError(f"git {' '.join(arguments)} failed: {message}")
    return completed.stdout


def _split_nul(value: bytes) -> list[str]:
    return [part.decode("utf-8", "surrogateescape") for part in value.split(b"\0") if part]


def git_source_paths(root: Path) -> tuple[list[str], set[str], set[str]]:
    combined = _split_nul(
        _git(
            root,
            ["ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        )
    )
    tracked = set(_split_nul(_git(root, ["ls-files", "--cached", "-z"])))
    untracked = set(
        _split_nul(_git(root, ["ls-files", "--others", "--exclude-standard", "-z"]))
    )
    paths = sorted(set(combined), key=os.fsencode)
    if set(paths) != tracked | untracked:
        raise SourceLockError("combined Git source set disagrees with tracked/untracked classification")
    return paths, tracked, untracked


def _source_entry(root: Path, relative: str, tracked: set[str]) -> dict[str, Any]:
    path = root / relative
    entry: dict[str, Any] = {
        "path": relative,
        "tracked": relative in tracked,
        "file_type": "missing",
        "mode": None,
        "size_bytes": None,
        "sha256": None,
        "link_target": None,
    }
    try:
        details = path.lstat()
    except FileNotFoundError:
        return entry
    entry["mode"] = format(stat.S_IMODE(details.st_mode), "04o")
    entry["size_bytes"] = details.st_size
    if stat.S_ISREG(details.st_mode):
        entry["file_type"] = "regular"
        entry["sha256"] = sha256_file(path)
    elif stat.S_ISLNK(details.st_mode):
        entry["file_type"] = "symlink"
        entry["link_target"] = os.readlink(path)
        entry["sha256"] = sha256_bytes(os.fsencode(entry["link_target"]))
    elif stat.S_ISDIR(details.st_mode):
        entry["file_type"] = "directory_or_gitlink"
    else:
        entry["file_type"] = "other"
    return entry


def _submodules(root: Path) -> list[dict[str, str]]:
    raw = _git(root, ["submodule", "status", "--recursive"]).decode("utf-8", "replace")
    rows = []
    for line in raw.splitlines():
        if not line:
            continue
        state = line[0]
        fields = line[1:].split()
        if len(fields) < 2:
            raise SourceLockError(f"unparseable submodule status: {line}")
        rows.append({"path": fields[1], "commit": fields[0], "state": state})
    return sorted(rows, key=lambda row: os.fsencode(row["path"]))


def _optional_sha(root: Path, relative: str) -> str | None:
    path = root / relative
    return sha256_file(path) if path.is_file() else None


def snapshot_source_lock(
    root: Path,
    *,
    repo_alias: str,
    binary_path: Path | None = None,
    binary_path_alias: str | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    paths, tracked, untracked = git_source_paths(root)
    entries = [_source_entry(root, relative, tracked) for relative in paths]
    status = sorted(
        _split_nul(_git(root, ["status", "--porcelain=v1", "-z", "--untracked-files=all"])),
        key=os.fsencode,
    )
    binary = {
        "path_alias": binary_path_alias,
        "exists": bool(binary_path and binary_path.is_file()),
        "size_bytes": binary_path.stat().st_size if binary_path and binary_path.is_file() else None,
        "sha256": sha256_file(binary_path) if binary_path and binary_path.is_file() else None,
    }
    identity = {
        "schema_version": SOURCE_LOCK_SCHEMA_VERSION,
        "repo_alias": repo_alias,
        "source_path_command": "git ls-files --cached --others --exclude-standard -z",
        "repo_commit": _git(root, ["rev-parse", "HEAD"]).decode().strip(),
        "branch": _git(root, ["branch", "--show-current"]).decode().strip(),
        "git_diff_binary_sha256": sha256_bytes(_git(root, ["diff", "--binary", "HEAD"])),
        "git_status_porcelain": status,
        "source_file_count": len(entries),
        "tracked_file_count": len(tracked),
        "untracked_nonignored_file_count": len(untracked),
        "untracked_nonignored_paths": sorted(untracked, key=os.fsencode),
        "submodule_count": len(_submodules(root)),
        "submodule_paths_and_commits": _submodules(root),
        "cmake_lists_sha256": _optional_sha(root, "CMakeLists.txt"),
        "package_xml_sha256": _optional_sha(root, "package.xml"),
        "binary": binary,
        "source_files": entries,
    }
    identity["source_files_sha256"] = sha256_bytes(canonical_json_bytes(entries))
    return identity


def source_lock_mismatches(
    expected: Mapping[str, Any], actual: Mapping[str, Any]
) -> list[dict[str, Any]]:
    fields = (
        "repo_alias",
        "repo_commit",
        "branch",
        "git_diff_binary_sha256",
        "git_status_porcelain",
        "source_file_count",
        "tracked_file_count",
        "untracked_nonignored_file_count",
        "untracked_nonignored_paths",
        "submodule_count",
        "submodule_paths_and_commits",
        "cmake_lists_sha256",
        "package_xml_sha256",
        "binary",
        "source_files_sha256",
        "source_files",
    )
    return [
        {"field": field, "expected": expected.get(field), "actual": actual.get(field)}
        for field in fields
        if expected.get(field) != actual.get(field)
    ]


def write_source_lock(snapshot: Mapping[str, Any], json_path: Path, csv_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_bytes(canonical_json_bytes(snapshot))
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fields = ("path", "tracked", "file_type", "mode", "size_bytes", "sha256", "link_target")
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(snapshot["source_files"])


def runtime_output_allowlist() -> dict[str, Any]:
    return {
        "schema_version": RUNTIME_ALLOWLIST_SCHEMA_VERSION,
        "allowed_paths": list(RUNTIME_OUTPUT_DEFINITIONS),
        "scan_roots": list(RUNTIME_OUTPUT_ROOTS),
    }


def _runtime_record(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.exists() and not path.is_symlink():
        return {"path": relative, "exists": False, "file_type": None, "size_bytes": None, "sha256": None, "mtime_ns": None}
    details = path.lstat()
    regular = stat.S_ISREG(details.st_mode)
    return {
        "path": relative,
        "exists": True,
        "file_type": "regular" if regular else "symlink" if stat.S_ISLNK(details.st_mode) else "other",
        "size_bytes": details.st_size,
        "sha256": sha256_file(path) if regular else None,
        "mtime_ns": details.st_mtime_ns,
    }


def runtime_output_inventory(root: Path) -> dict[str, Any]:
    paths = set(RUNTIME_OUTPUT_PATHS)
    for relative_root in RUNTIME_OUTPUT_ROOTS:
        directory = root / relative_root
        if directory.is_dir():
            for path in directory.rglob("*"):
                if path.is_file() or path.is_symlink():
                    paths.add(path.relative_to(root).as_posix())
    return {
        "schema_version": RUNTIME_ALLOWLIST_SCHEMA_VERSION,
        "records": [_runtime_record(root, relative) for relative in sorted(paths, key=os.fsencode)],
    }


def compare_runtime_inventories(
    before: Mapping[str, Any], after: Mapping[str, Any]
) -> dict[str, Any]:
    before_rows = {row["path"]: row for row in before["records"]}
    after_rows = {row["path"]: row for row in after["records"]}
    paths = sorted(set(before_rows) | set(after_rows), key=os.fsencode)
    missing = {"path": None, "exists": False, "file_type": None, "size_bytes": None, "sha256": None, "mtime_ns": None}
    changed = []
    for relative in paths:
        old = dict(before_rows.get(relative, {**missing, "path": relative}))
        new = dict(after_rows.get(relative, {**missing, "path": relative}))
        if old != new:
            changed.append({"path": relative, "before": old, "after": new})
    unexpected = [row for row in changed if row["path"] not in RUNTIME_OUTPUT_PATHS]
    return {
        "allowlist_pass": not unexpected,
        "changed_paths": [row["path"] for row in changed],
        "allowed_changed_paths": [row["path"] for row in changed if row["path"] in RUNTIME_OUTPUT_PATHS],
        "unexpected_runtime_output_count": len(unexpected),
        "unexpected_changes": unexpected,
        "changes": changed,
    }


def clear_allowed_runtime_outputs(root: Path) -> list[dict[str, Any]]:
    actions = []
    for relative in RUNTIME_OUTPUT_PATHS:
        path = root / relative
        before = _runtime_record(root, relative)
        if path.exists() or path.is_symlink():
            if not path.is_file() and not path.is_symlink():
                raise SourceLockError(f"allowlisted runtime output is not a file: {relative}")
            path.unlink()
            action = "deleted"
        else:
            action = "already_absent"
        actions.append({"path": relative, "action": action, "before": before})
    return actions


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))
