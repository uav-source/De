#!/usr/bin/env python3
"""Create stable SHA-256 manifests without modifying audited files."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple


IGNORED_DIRECTORY_NAMES = {".git", "__pycache__", ".pytest_cache", "results", "data"}


def repository_root() -> Path:
    """Return the repository containing this script."""

    return Path(__file__).resolve().parents[1]


def _relative_path(path: Path, root: Path) -> str:
    return Path(os.path.relpath(str(path), str(root))).as_posix()


def _is_ignored_file(path: Path) -> bool:
    return path.suffix == ".pyc"


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _regular_files(path: Path) -> Iterable[Path]:
    """Yield ordinary files below *path* in deterministic traversal order."""

    if path.is_file() and not path.is_symlink():
        if not _is_ignored_file(path):
            yield path
        return
    if not path.is_dir():
        return

    for current, directory_names, file_names in os.walk(str(path), followlinks=False):
        directory_names[:] = sorted(
            name
            for name in directory_names
            if name not in IGNORED_DIRECTORY_NAMES
            and not (Path(current) / name).is_symlink()
        )
        for file_name in sorted(file_names):
            file_path = Path(current) / file_name
            if _is_ignored_file(file_path) or file_path.is_symlink():
                continue
            try:
                mode = file_path.lstat().st_mode
            except OSError:
                # Keep the path so the normal audit path records the read/stat error.
                yield file_path
                continue
            if stat.S_ISREG(mode):
                yield file_path


def build_manifest(
    paths: Sequence[Path],
    root: Path,
    excluded_paths: Optional[Iterable[Path]] = None,
) -> Tuple[Dict[str, Any], bool]:
    """Build a deterministic manifest and report whether every file was readable."""

    root = root.resolve()
    excluded: Set[Path] = {
        path.resolve() for path in (excluded_paths or [])
    }
    inputs: List[Dict[str, Any]] = []
    file_records: Dict[str, Dict[str, Any]] = {}
    errors: List[Dict[str, str]] = []

    for raw_path in paths:
        path = raw_path if raw_path.is_absolute() else root / raw_path
        path = path.resolve()
        input_record: Dict[str, Any] = {
            "relative_path": _relative_path(path, root),
            "missing": not path.exists(),
            "file_count": 0,
            "size_bytes": 0,
        }
        if input_record["missing"]:
            inputs.append(input_record)
            continue

        input_relative_paths: Set[str] = set()
        for file_path in _regular_files(path):
            resolved_file = file_path.resolve()
            if resolved_file in excluded:
                continue
            relative_path = _relative_path(resolved_file, root)
            try:
                size_bytes = resolved_file.stat().st_size
                sha256 = _hash_file(resolved_file)
            except OSError as exc:
                errors.append(
                    {
                        "relative_path": relative_path,
                        "error": "{}: {}".format(type(exc).__name__, exc),
                    }
                )
                continue
            file_records[relative_path] = {
                "relative_path": relative_path,
                "size_bytes": size_bytes,
                "sha256": sha256,
            }
            input_relative_paths.add(relative_path)

        input_record["file_count"] = len(input_relative_paths)
        input_record["size_bytes"] = sum(
            file_records[relative_path]["size_bytes"]
            for relative_path in input_relative_paths
        )
        inputs.append(input_record)

    files = [file_records[path] for path in sorted(file_records)]
    errors.sort(key=lambda item: (item["relative_path"], item["error"]))
    manifest: Dict[str, Any] = {
        "manifest_version": 1,
        "repository_root": str(root),
        "inputs": inputs,
        "files": files,
        "file_count": len(files),
        "total_size_bytes": sum(item["size_bytes"] for item in files),
        "errors": errors,
    }
    return manifest, not errors


def _text_manifest(manifest: Dict[str, Any]) -> str:
    lines = ["# Stage 1 stable SHA-256 manifest v1"]
    for input_record in manifest["inputs"]:
        if input_record["missing"]:
            lines.append("# MISSING {}".format(input_record["relative_path"]))
    for error in manifest["errors"]:
        lines.append("# ERROR {} {}".format(error["relative_path"], error["error"]))
    lines.extend(
        "{}  {}".format(record["sha256"], record["relative_path"])
        for record in manifest["files"]
    )
    return "\n".join(lines) + "\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="files or directories to audit")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=repository_root(),
        help="base directory used for relative paths",
    )
    parser.add_argument("--json-output", required=True, type=Path)
    parser.add_argument("--sha256-output", required=True, type=Path)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    json_output = args.json_output.resolve()
    sha256_output = args.sha256_output.resolve()
    manifest, readable = build_manifest(
        args.paths,
        args.repo_root,
        excluded_paths=(json_output, sha256_output),
    )

    json_output.parent.mkdir(parents=True, exist_ok=True)
    sha256_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    sha256_output.write_text(_text_manifest(manifest), encoding="utf-8")

    print(
        "audited {} files ({} bytes); missing inputs: {}; read errors: {}".format(
            manifest["file_count"],
            manifest["total_size_bytes"],
            sum(1 for item in manifest["inputs"] if item["missing"]),
            len(manifest["errors"]),
        )
    )
    return 0 if readable else 1


if __name__ == "__main__":
    sys.exit(main())
