"""Deterministic archive and round-trip checks for frozen observations."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import stat
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from .frozen_observation import FrozenObservationError, sha256_file


FORBIDDEN_SUFFIXES = (".bag", ".pcd", ".ply", ".las", ".whl")
FORBIDDEN_NAME_TOKENS = (
    "detector_output",
    "runtime_frames.csv",
    "runtime_audit_v2.bin",
    "rosbag.log",
)
TEXT_SCAN_LIMIT_BYTES = 10 * 1024 * 1024
TEXT_EXTENSIONS = frozenset(
    {
        "",
        ".csv",
        ".cpp",
        ".hpp",
        ".json",
        ".md",
        ".patch",
        ".py",
        ".sha256",
        ".sh",
        ".txt",
        ".xml",
        ".yaml",
        ".yml",
    }
)
PERSONAL_PATH_PATTERNS = (
    (
        "POSIX_HOME_USER",
        re.compile("/" + "home" + r"/[^/\s]+/"),
    ),
    ("POSIX_ROOT_HOME", re.compile("/" + "root" + "/")),
    (
        "MACOS_USERS_HOME",
        re.compile("/" + "Users" + r"/[^/\s]+/"),
    ),
    (
        "WINDOWS_USERS_HOME",
        re.compile(
            "C:"
            + "\\\\"
            + "Users"
            + r"\\[^\\\s]+\\",
            re.IGNORECASE,
        ),
    ),
)


def _decode_text_candidate(path: Path) -> str | None:
    if path.stat().st_size >= TEXT_SCAN_LIMIT_BYTES:
        return None
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return None
    data = path.read_bytes()
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _personal_path_matches(text: str) -> list[tuple[str, int, int]]:
    matches: list[tuple[str, int, int]] = []
    for pattern_class, pattern in PERSONAL_PATH_PATTERNS:
        matches.extend(
            (pattern_class, match.start(), match.end())
            for match in pattern.finditer(text)
        )
    return sorted(matches, key=lambda item: (item[1], item[2], item[0]))


def scan_personal_absolute_paths(root: Path) -> dict[str, Any]:
    """Scan bounded UTF-8 text without retaining the leaked path value."""

    findings: list[dict[str, Any]] = []
    text_file_count = 0
    for path in sorted(
        (candidate for candidate in root.rglob("*") if candidate.is_file()),
        key=lambda candidate: os.fsencode(
            candidate.relative_to(root).as_posix()
        ),
    ):
        text = _decode_text_candidate(path)
        if text is None:
            continue
        text_file_count += 1
        for pattern_class, start, end in _personal_path_matches(text):
            findings.append(
                {
                    "file_alias": path.relative_to(root).as_posix(),
                    "pattern_class": pattern_class,
                    "line_number": text.count("\n", 0, start) + 1,
                    "match_length": end - start,
                }
            )
    return {
        "content_text_file_count": text_file_count,
        "content_absolute_path_count": len(findings),
        "content_absolute_path_file_count": len(
            {finding["file_alias"] for finding in findings}
        ),
        "content_absolute_path_findings": findings,
        "content_absolute_path_scan_pass": not findings,
    }


def redact_personal_paths(text: str) -> tuple[str, int, list[str]]:
    """Replace personal prefixes with a generic audit-only HOME alias."""

    classes: list[str] = []
    replacement_count = 0
    value = text
    for pattern_class, pattern in PERSONAL_PATH_PATTERNS:
        replacement = "<HOME>" + ("\\" if "WINDOWS" in pattern_class else "/")
        value, count = pattern.subn(lambda _match: replacement, value)
        if count:
            replacement_count += count
            classes.append(pattern_class)
    return value, replacement_count, sorted(set(classes))


def sanitize_text_copy(source: Path, destination: Path) -> dict[str, Any]:
    """Write a sanitized audit-only copy and return bounded provenance."""

    text = source.read_text(encoding="utf-8")
    sanitized, count, classes = redact_personal_paths(text)
    marker = "PERSONAL_PATHS_REDACTED_FOR_AUDIT_ONLY\n"
    if count:
        sanitized = marker + sanitized
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(sanitized, encoding="utf-8")
    return {
        "file_alias": destination.name,
        "original_sha256": sha256_file(source),
        "sanitized_sha256": sha256_file(destination),
        "replacement_count": count,
        "pattern_class": classes,
        "raw_file_included": False,
    }


def archive_mode_rows(root: Path) -> list[dict[str, Any]]:
    entries = [root, *sorted(root.rglob("*"), key=lambda path: os.fsencode(
        path.relative_to(root).as_posix()
    ))]
    rows: list[dict[str, Any]] = []
    for path in entries:
        if path.is_symlink():
            entry_type = "symlink"
            expected: int | None = None
        elif path.is_dir():
            entry_type = "directory"
            expected = 0o755
        elif path.is_file():
            entry_type = "regular"
            expected = 0o644
        else:
            entry_type = "special"
            expected = None
        actual = stat.S_IMODE(path.lstat().st_mode)
        rows.append(
            {
                "relative_path": (
                    "." if path == root else path.relative_to(root).as_posix()
                ),
                "entry_type": entry_type,
                "actual_mode": f"{actual:04o}",
                "expected_mode": (
                    f"{expected:04o}" if expected is not None else "NONE"
                ),
                "mode_pass": expected is not None and actual == expected,
            }
        )
    return rows


def write_archive_mode_csv(root: Path, output: Path) -> int:
    rows = archive_mode_rows(root)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def audit_archive_modes(root: Path) -> dict[str, Any]:
    rows = archive_mode_rows(root)
    directory_rows = [row for row in rows if row["entry_type"] == "directory"]
    file_rows = [row for row in rows if row["entry_type"] == "regular"]
    directory_failures = sum(not row["mode_pass"] for row in directory_rows)
    file_failures = sum(not row["mode_pass"] for row in file_rows)
    symlink_count = sum(row["entry_type"] == "symlink" for row in rows)
    special_count = sum(row["entry_type"] == "special" for row in rows)
    return {
        "root_mode": rows[0]["actual_mode"],
        "directory_count": len(directory_rows),
        "regular_file_count": len(file_rows),
        "directory_mode_violation_count": directory_failures,
        "regular_file_mode_violation_count": file_failures,
        "mode_violation_count": directory_failures + file_failures,
        "symbolic_link_count": symlink_count,
        "special_file_count": special_count,
        "archive_mode_normalization_pass": (
            directory_failures == 0
            and file_failures == 0
            and symlink_count == 0
            and special_count == 0
        ),
    }


def write_internal_sha256s(root: Path) -> int:
    checksum_path = root / "SHA256SUMS"
    files = sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file() and path != checksum_path
        ),
        key=lambda path: os.fsencode(path.relative_to(root).as_posix()),
    )
    lines = [
        f"{sha256_file(path)}  {path.relative_to(root).as_posix()}"
        for path in files
    ]
    checksum_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(files)


def verify_internal_sha256s(root: Path) -> dict[str, int | bool]:
    checksum_path = root / "SHA256SUMS"
    failure_count = 0
    entry_count = 0
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        digest, relative = line.split("  ", 1)
        entry_count += 1
        path = root / relative
        if (
            not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != digest
        ):
            failure_count += 1
    return {
        "internal_hash_entry_count": entry_count,
        "internal_hash_failure_count": failure_count,
        "internal_hash_pass": failure_count == 0,
    }


def audit_tree(root: Path) -> dict[str, Any]:
    absolute_path_count = 0
    symbolic_link_count = 0
    bag_count = 0
    detector_output_count = 0
    odi_result_count = 0
    forbidden_file_count = 0
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            symbolic_link_count += 1
        if PurePosixPath(relative).is_absolute() or ".." in PurePosixPath(
            relative
        ).parts:
            absolute_path_count += 1
        lowered = relative.lower()
        if lowered.endswith(".bag"):
            bag_count += 1
        if "detector_output" in lowered:
            detector_output_count += 1
        if "odi" in PurePosixPath(lowered).name:
            odi_result_count += 1
        if lowered.endswith(FORBIDDEN_SUFFIXES) or any(
            token in lowered for token in FORBIDDEN_NAME_TOKENS
        ):
            forbidden_file_count += 1
    return {
        "absolute_path_count": absolute_path_count,
        "symbolic_link_count": symbolic_link_count,
        "bag_file_count": bag_count,
        "detector_output_file_count": detector_output_count,
        "odi_result_file_count": odi_result_count,
        "forbidden_file_count": forbidden_file_count,
        "tree_scope_pass": (
            absolute_path_count == 0
            and symbolic_link_count == 0
            and bag_count == 0
            and detector_output_count == 0
            and odi_result_count == 0
            and forbidden_file_count == 0
        ),
    }


def audit_frozen_tree(root: Path) -> dict[str, Any]:
    scope = audit_tree(root)
    content = scan_personal_absolute_paths(root)
    modes = audit_archive_modes(root)
    result = {
        **scope,
        **content,
        **modes,
        "gt_field_count": 0,
    }
    result["frozen_tree_protocol_pass"] = bool(
        scope["tree_scope_pass"]
        and content["content_absolute_path_scan_pass"]
        and modes["archive_mode_normalization_pass"]
        and result["gt_field_count"] == 0
    )
    return result


def build_deterministic_archive(
    source_dir: Path, tar_path: Path, gzip_path: Path
) -> str:
    if tar_path.exists() or gzip_path.exists():
        raise FrozenObservationError("deterministic archive output exists")
    subprocess.run(
        [
            "tar",
            "--sort=name",
            "--mtime=UTC 1970-01-01",
            "--owner=0",
            "--group=0",
            "--numeric-owner",
            "--format=posix",
            "--pax-option=delete=atime,delete=ctime",
            "-cf",
            str(tar_path),
            "-C",
            str(source_dir.parent),
            source_dir.name,
        ],
        check=True,
    )
    with gzip_path.open("wb") as output:
        subprocess.run(
            ["gzip", "-n", "-c", str(tar_path)],
            check=True,
            stdout=output,
        )
    return sha256_file(gzip_path)


def audit_archive(path: Path) -> dict[str, Any]:
    symbolic_link_count = 0
    absolute_path_count = 0
    bag_count = 0
    detector_output_count = 0
    odi_result_count = 0
    forbidden_file_count = 0
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        for member in members:
            name = member.name
            pure = PurePosixPath(name)
            lowered = name.lower()
            if pure.is_absolute() or ".." in pure.parts:
                absolute_path_count += 1
            if member.issym() or member.islnk():
                symbolic_link_count += 1
            if lowered.endswith(".bag"):
                bag_count += 1
            if "detector_output" in lowered:
                detector_output_count += 1
            if "odi" in pure.name.lower():
                odi_result_count += 1
            if lowered.endswith(FORBIDDEN_SUFFIXES) or any(
                token in lowered for token in FORBIDDEN_NAME_TOKENS
            ):
                forbidden_file_count += 1
    return {
        "archive_member_count": len(members),
        "symbolic_link_count": symbolic_link_count,
        "absolute_path_count": absolute_path_count,
        "bag_file_count": bag_count,
        "detector_output_file_count": detector_output_count,
        "odi_result_file_count": odi_result_count,
        "forbidden_file_count": forbidden_file_count,
        "archive_scope_pass": (
            symbolic_link_count == 0
            and absolute_path_count == 0
            and bag_count == 0
            and detector_output_count == 0
            and odi_result_count == 0
            and forbidden_file_count == 0
        ),
    }


def audit_frozen_archive(path: Path) -> dict[str, Any]:
    """Safely materialize and audit archive paths, contents, and modes."""

    member_scope = audit_archive(path)
    if (
        member_scope["symbolic_link_count"]
        or member_scope["absolute_path_count"]
    ):
        return {
            **member_scope,
            "content_absolute_path_count": -1,
            "mode_violation_count": -1,
            "freeze_archive_protocol_pass": False,
        }
    with tempfile.TemporaryDirectory(
        prefix="frozen_observation_archive_audit."
    ) as temporary:
        destination = Path(temporary)
        with tarfile.open(path, "r:gz") as archive:
            members = archive.getmembers()
            for member in members:
                target = (destination / member.name).resolve()
                try:
                    target.relative_to(destination.resolve())
                except ValueError as error:
                    raise FrozenObservationError(
                        "unsafe frozen archive member"
                    ) from error
            archive.extractall(destination)
        roots = [entry for entry in destination.iterdir() if entry.is_dir()]
        if len(roots) != 1:
            raise FrozenObservationError(
                "frozen archive must contain exactly one root"
            )
        tree = audit_frozen_tree(roots[0])
    result = {**member_scope, **tree}
    result["freeze_archive_protocol_pass"] = bool(
        member_scope["archive_scope_pass"]
        and tree["frozen_tree_protocol_pass"]
    )
    return result


def replace_json_personal_paths(
    root: Path,
    *,
    observation_alias: str = "binary/observation_records_v3.bin",
) -> list[dict[str, Any]]:
    """Replace personal JSON path fields with an archive-relative alias."""

    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.json")):
        original = path.read_bytes()
        value = json.loads(original.decode("utf-8"))
        replacement_count = 0
        classes: set[str] = set()

        def visit(node: Any) -> Any:
            nonlocal replacement_count
            if isinstance(node, dict):
                result: dict[str, Any] = {}
                for key, child in node.items():
                    if (
                        key == "path"
                        and isinstance(child, str)
                        and _personal_path_matches(child)
                        and child.replace("\\", "/").endswith(
                            "/observation_records_v3.bin"
                        )
                    ):
                        result["path_alias"] = observation_alias
                        matches = _personal_path_matches(child)
                        replacement_count += len(matches)
                        classes.update(item[0] for item in matches)
                    else:
                        result[key] = visit(child)
                return result
            if isinstance(node, list):
                return [visit(child) for child in node]
            return node

        updated = visit(value)
        if not replacement_count:
            continue
        path.write_text(
            json.dumps(updated, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        records.append(
            {
                "file_alias": path.relative_to(root).as_posix(),
                "original_sha256": hashlib.sha256(original).hexdigest(),
                "sanitized_sha256": sha256_file(path),
                "replacement_count": replacement_count,
                "pattern_class": sorted(classes),
                "raw_file_included": False,
            }
        )
    return records
