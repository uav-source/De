"""Provenance-aware collision audit for reserved random seeds.

The audit deliberately ignores bare decimal matches.  A value is a collision
only when it occurs in a structured seed field/column or in code that
initializes an RNG (including bootstrap and scene-generation RNGs).
"""

from __future__ import annotations

import ast
import csv
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Set

import yaml


SEED_FIELD_MARKERS = ("seed", "random_state", "rng")
STRUCTURED_SUFFIXES = {".json", ".yaml", ".yml", ".csv"}
SOURCE_SUFFIXES = {".py", ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp"}
IGNORED_DIRECTORIES = {".git", "__pycache__", ".pytest_cache"}


def is_seed_field(name: object) -> bool:
    """Return whether *name* declares seed/RNG provenance."""

    lowered = str(name).strip().lower()
    return any(marker in lowered for marker in SEED_FIELD_MARKERS)


def _candidate_integer(value: object, candidates: Set[int]) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and re.fullmatch(r"[+-]?\d+", value.strip()):
        parsed = int(value.strip())
    else:
        return None
    return parsed if parsed in candidates else None


def _regular_candidate_files(root: Path) -> Iterator[Path]:
    for current, directory_names, file_names in os.walk(str(root), followlinks=False):
        directory_names[:] = sorted(
            name
            for name in directory_names
            if name not in IGNORED_DIRECTORIES
            and not (Path(current) / name).is_symlink()
        )
        for name in sorted(file_names):
            path = Path(current) / name
            if path.is_symlink() or not path.is_file():
                continue
            if path.suffix.lower() in STRUCTURED_SUFFIXES | SOURCE_SUFFIXES:
                yield path


def _contains_candidate_text(path: Path, candidates: Set[int]) -> bool:
    needles = tuple(str(value).encode("ascii") for value in candidates)
    try:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    return False
                if any(needle in chunk for needle in needles):
                    return True
                # Decimal tokens cannot span more than ten bytes for the frozen
                # modulus; retain a short overlap between chunks.
                if len(chunk) == 1024 * 1024:
                    handle.seek(-16, 1)
    except OSError:
        return False


def _structured_collisions(
    value: Any,
    candidates: Set[int],
    relative_path: str,
    field_path: str = "$",
    inside_seed_context: bool = False,
) -> Iterator[Dict[str, Any]]:
    if inside_seed_context:
        candidate = _candidate_integer(value, candidates)
        if candidate is not None:
            yield {
                "seed": candidate,
                "path": relative_path,
                "field": field_path,
                "context": "structured_seed_field",
            }
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = "{}.{}".format(field_path, key)
            yield from _structured_collisions(
                child,
                candidates,
                relative_path,
                child_path,
                inside_seed_context or is_seed_field(key),
            )
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            yield from _structured_collisions(
                child,
                candidates,
                relative_path,
                "{}[{}]".format(field_path, index),
                inside_seed_context,
            )


def _audit_json_or_yaml(path: Path, root: Path, candidates: Set[int]) -> List[Dict[str, Any]]:
    raw = path.read_text(encoding="utf-8", errors="strict")
    if path.suffix.lower() == ".json":
        value = json.loads(raw)
    else:
        value = yaml.safe_load(raw)
    relative = path.relative_to(root).as_posix()
    return list(_structured_collisions(value, candidates, relative))


def _audit_csv(path: Path, root: Path, candidates: Set[int]) -> List[Dict[str, Any]]:
    collisions: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="strict", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            return collisions
        seed_columns = [index for index, name in enumerate(header) if is_seed_field(name)]
        if not seed_columns:
            return collisions
        relative = path.relative_to(root).as_posix()
        for line_number, row in enumerate(reader, start=2):
            for column in seed_columns:
                if column >= len(row):
                    continue
                candidate = _candidate_integer(row[column], candidates)
                if candidate is not None:
                    collisions.append(
                        {
                            "seed": candidate,
                            "path": relative,
                            "field": header[column],
                            "line": line_number,
                            "context": "csv_seed_column",
                        }
                    )
    return collisions


def _dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return "{}.{}".format(parent, node.attr) if parent else node.attr
    return ""


def _literal_candidates(node: ast.AST, candidates: Set[int]) -> Set[int]:
    found: Set[int] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Constant):
            candidate = _candidate_integer(child.value, candidates)
            if candidate is not None:
                found.add(candidate)
    return found


def _rng_call(call: ast.Call) -> bool:
    name = _dotted_name(call.func).lower()
    direct_rng = (
        ".random" in name
        or name.startswith("random.")
        or "default_rng" in name
        or "mt19937" in name
        or "bootstrap" in name
    )
    seeded_keyword = any(is_seed_field(keyword.arg or "") for keyword in call.keywords)
    return direct_rng or seeded_keyword


def _audit_python(path: Path, root: Path, candidates: Set[int]) -> List[Dict[str, Any]]:
    source = path.read_text(encoding="utf-8", errors="strict")
    tree = ast.parse(source, filename=str(path))
    relative = path.relative_to(root).as_posix()
    collisions: List[Dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _rng_call(node):
            continue
        for candidate in sorted(_literal_candidates(node, candidates)):
            collisions.append(
                {
                    "seed": candidate,
                    "path": relative,
                    "field": _dotted_name(node.func),
                    "line": int(getattr(node, "lineno", 0)),
                    "context": "python_rng_initialization",
                }
            )
    return collisions


def _audit_cpp(path: Path, root: Path, candidates: Set[int]) -> List[Dict[str, Any]]:
    collisions: List[Dict[str, Any]] = []
    pattern = re.compile(r"seed|rng|random|mt19937|bootstrap", re.IGNORECASE)
    relative = path.relative_to(root).as_posix()
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8", errors="strict").splitlines(), start=1
    ):
        if not pattern.search(line):
            continue
        for candidate in sorted(candidates):
            if re.search(r"(?<!\d){}(?!\d)".format(candidate), line):
                collisions.append(
                    {
                        "seed": candidate,
                        "path": relative,
                        "field": "source_line",
                        "line": line_number,
                        "context": "cpp_rng_initialization",
                    }
                )
    return collisions


def audit_seed_provenance(
    root: Path,
    candidate_seeds: Iterable[int],
    excluded_paths: Sequence[Path] = (),
) -> Dict[str, Any]:
    """Audit candidate seeds only in formally seed-bearing contexts."""

    root = Path(root).resolve()
    candidates = {int(value) for value in candidate_seeds}
    excluded = {
        (path if path.is_absolute() else root / path).resolve() for path in excluded_paths
    }
    collisions: List[Dict[str, Any]] = []
    scanned = {"json_yaml": 0, "csv": 0, "python": 0, "cpp": 0}
    parse_errors: List[Dict[str, str]] = []
    for path in _regular_candidate_files(root):
        if path.resolve() in excluded or not _contains_candidate_text(path, candidates):
            continue
        suffix = path.suffix.lower()
        try:
            if suffix in {".json", ".yaml", ".yml"}:
                scanned["json_yaml"] += 1
                collisions.extend(_audit_json_or_yaml(path, root, candidates))
            elif suffix == ".csv":
                scanned["csv"] += 1
                collisions.extend(_audit_csv(path, root, candidates))
            elif suffix == ".py":
                scanned["python"] += 1
                collisions.extend(_audit_python(path, root, candidates))
            else:
                scanned["cpp"] += 1
                collisions.extend(_audit_cpp(path, root, candidates))
        except (OSError, UnicodeError, csv.Error, json.JSONDecodeError, yaml.YAMLError, SyntaxError) as error:
            parse_errors.append(
                {"path": path.relative_to(root).as_posix(), "error": str(error)}
            )
    collisions.sort(
        key=lambda row: (int(row["seed"]), row["path"], row.get("line", 0), row["field"])
    )
    return {
        "audit_version": "seed_provenance_context_v1",
        "definition": {
            "structured_fields": list(SEED_FIELD_MARKERS),
            "csv_columns": list(SEED_FIELD_MARKERS),
            "code_contexts": [
                "np.random/numpy.random/random.seed/default_rng/mt19937",
                "seeded RNG calls",
                "bootstrap initialization",
                "scene-generator RNG initialization",
            ],
            "bare_numeric_matches_are_collisions": False,
        },
        "candidate_seeds": sorted(candidates),
        "scanned_candidate_files": scanned,
        "collision_count": len(collisions),
        "collisions": collisions,
        "parse_errors": sorted(parse_errors, key=lambda row: row["path"]),
        "derived_seed_provenance_collision": bool(collisions),
    }

