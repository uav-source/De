#!/usr/bin/env python3
"""Consolidate private material and build the canonical Degen-LIO package.

The default mode is repeatable: it refreshes the full-history Git bundle,
project state, integrity inventories, pytest result, and the canonical ZIP.
The optional ``--consolidate-sources`` mode performs the one-time, verified
migration from the legacy external/private locations before packaging.
"""

from __future__ import annotations

import argparse
import csv
import fnmatch
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


ARCHIVE_DATE = "20260722"
CANONICAL_ZIP_NAME = "Degen-LIO-full-current.zip"
PRIVATE_DIRS = ("_private", "_backups", "_archives", "_package")
DAY3_PRIOR_ART_FILES = (
    "01_search_protocol.md",
    "02_search_log.csv",
    "03_patent_candidates.csv",
    "04_non_patent_candidates.csv",
    "05_top_patent_claim_charts.md",
    "06_closest_prior_art_matrix.md",
    "07_combination_attack_matrix.md",
    "08_novelty_inventiveness_risk.md",
    "09_recommended_claim_boundary.md",
    "10_agent_questions.md",
)
DAY3_CORE_PATHS = (
    "_private/patent1/prior_art/06_closest_prior_art_matrix.md",
    "_private/patent1/prior_art/07_combination_attack_matrix.md",
    "_private/patent1/prior_art/08_novelty_inventiveness_risk.md",
    "_private/patent1/prior_art/09_recommended_claim_boundary.md",
    "reports/stage1/day3_prior_art_gate_20260722.md",
)
REQUIRED_FILE_PATHS = (
    "_backups/git_bundles/Degen-LIO-full-history.bundle",
    "_package/project_state.md",
    "_package/full_manifest.json",
    "_package/full_sha256.txt",
)
REQUIRED_PREFIXES = (
    "_private/patent1/current/",
    "_private/patent1/prior_art/",
    "reports/stage1/",
    "artifacts/current/detector_stage2a/",
    "artifacts/current/weak_update_stage2c/",
    "artifacts/history/stage1c_confirmatory_no_go/",
    "artifacts/history/stage2b_column_scaling_no_go/",
)
EMPTY_DIRS_TO_ARCHIVE = (
    "_private/patent1/filing",
    "_private/patent1/rendered_checks",
    "reports/consolidation",
)
SKIP_DIR_NAMES = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    ".venv",
    "venv",
    "env",
    "node_modules",
}
SKIP_SUFFIXES = {".pyc", ".pyo"}
TEXT_SCAN_SUFFIXES = {
    ".cfg",
    ".conf",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
MIGRATION_REPORT = "_backups/manifests/single_root_migration_20260722.json"
REVIEW_EXPORT_NAMES = (
    "day1_baseline_audit.md",
    "day2_traceability_gate.md",
    "day3_prior_art_gate.md",
    "closest_prior_art_matrix.md",
    "combination_attack_matrix.md",
    "novelty_inventiveness_risk.md",
    "recommended_claim_boundary.md",
    "patent1_current_text.md",
    "patent1_formula_inventory.csv",
    "patent1_revision_report.md",
    "project_state.md",
    "packaging_report.md",
    "critical_file_hashes.csv",
)
REVIEW_ROOT_FILES = (
    "PACKAGE_AUDIT.md",
    "PACKAGE_CONTENTS.txt",
    "REVIEW_INDEX.md",
    "REVIEW_MANIFEST.csv",
)
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
XML_NAMESPACES = {"w": W_NS, "m": M_NS}


class PackagingError(RuntimeError):
    """A safety or package-integrity condition failed."""


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(
    args: list[str],
    *,
    cwd: Path,
    check: bool = True,
    text: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=cwd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=text,
    )
    if check and result.returncode != 0:
        command = " ".join(args)
        raise PackagingError(
            f"command failed ({result.returncode}): {command}\n{result.stdout}"
        )
    return result


def project_root_from_script() -> Path:
    root = Path(__file__).resolve().parents[1]
    expected = Path.home().resolve() / "Degen-LIO"
    git_root = Path(
        run(["git", "rev-parse", "--show-toplevel"], cwd=root).stdout.strip()
    ).resolve()
    if root != expected or git_root != expected:
        raise PackagingError(
            f"project root must be {expected}; script={root}, git={git_root}"
        )
    return root


def ensure_layout(root: Path) -> None:
    paths = (
        "_private/patent1/current",
        "_private/patent1/history",
        "_private/patent1/prior_art",
        "_private/patent1/filing",
        "_private/patent1/rendered_checks",
        "_private/stage1",
        "_backups/git_bundles",
        "_backups/test_logs",
        "_backups/manifests",
        "_archives/legacy_packages",
        "_package",
        "reports/consolidation",
    )
    for relative in paths:
        (root / relative).mkdir(parents=True, exist_ok=True)


def private_tracked_files(root: Path) -> list[str]:
    result = run(
        ["git", "ls-files", "-z", *[f"{item}/**" for item in PRIVATE_DIRS]],
        cwd=root,
    )
    return sorted(item for item in result.stdout.split("\0") if item)


def assert_private_untracked(root: Path) -> None:
    tracked = private_tracked_files(root)
    if tracked:
        raise PackagingError(
            "private/package paths are Git-tracked; refusing to continue:\n"
            + "\n".join(tracked)
        )


def review_tracked_files(root: Path) -> list[str]:
    result = run(
        [
            "git",
            "ls-files",
            "-z",
            "review_exports/**",
            *REVIEW_ROOT_FILES,
        ],
        cwd=root,
    )
    return sorted(item for item in result.stdout.split("\0") if item)


def assert_review_untracked(root: Path) -> None:
    tracked = review_tracked_files(root)
    if tracked:
        raise PackagingError(
            "readable review exports are Git-tracked; refusing to continue:\n"
            + "\n".join(tracked)
        )


def patent_destination(root: Path, relative_inside_patent: Path) -> Path:
    parts = relative_inside_patent.parts
    name = relative_inside_patent.name
    if parts and parts[0] == "prior_art":
        return root / "_private/patent1/prior_art" / Path(*parts[1:])
    if "v1_1" in name.lower() and name.lower().endswith(".docx"):
        return root / "_private/patent1/history" / name
    if "v1.1" in name.lower() and name.lower().endswith(".docx"):
        return root / "_private/patent1/history" / name
    if "v1_2" in name.lower() or "v1.2" in name.lower():
        return root / "_private/patent1/current" / name
    return root / "_private/patent1/filing" / relative_inside_patent


def backup_destination(root: Path, source_relative: Path) -> Path:
    name = source_relative.name
    if name.endswith(".bundle"):
        return root / "_backups/git_bundles" / name
    if name.endswith(".log"):
        return root / "_backups/test_logs" / name
    if name == "sha256.txt" and "day1" in source_relative.as_posix().lower():
        return root / "_backups/manifests/day1-logs-sha256.txt"
    safe_name = source_relative.as_posix().replace("/", "__")
    return root / "_backups/manifests" / safe_name


@dataclass
class MigrationState:
    original_git_head: str
    started_at: str = field(default_factory=now_iso)
    completed_at: str | None = None
    external_private_ip_found: bool = False
    external_private_ip_migrated: bool = False
    external_backups_found: bool = False
    external_backups_migrated: bool = False
    old_private_stage1_found: bool = False
    old_private_stage1_migrated: bool = False
    sources: list[dict[str, Any]] = field(default_factory=list)
    deduplicated: list[dict[str, str]] = field(default_factory=list)
    conflicts: list[dict[str, str]] = field(default_factory=list)
    legacy_archives: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "original_git_head": self.original_git_head,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "external_private_ip_found": self.external_private_ip_found,
            "external_private_ip_migrated": self.external_private_ip_migrated,
            "external_backups_found": self.external_backups_found,
            "external_backups_migrated": self.external_backups_migrated,
            "old_private_stage1_found": self.old_private_stage1_found,
            "old_private_stage1_migrated": self.old_private_stage1_migrated,
            "source_mappings": self.sources,
            "deduplicated": self.deduplicated,
            "conflicts": self.conflicts,
            "legacy_archives": self.legacy_archives,
        }


def write_migration_state(root: Path, state: MigrationState) -> None:
    report_path = root / MIGRATION_REPORT
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(state.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def conflict_path(destination: Path, digest: str) -> Path:
    candidate = destination.with_name(f"{destination.name}.conflict_{digest[:8]}")
    counter = 2
    while candidate.exists() and sha256_file(candidate) != digest:
        candidate = destination.with_name(
            f"{destination.name}.conflict_{digest[:8]}_{counter}"
        )
        counter += 1
    return candidate


def verified_copy(
    root: Path,
    source: Path,
    destination: Path,
    state: MigrationState,
) -> Path:
    source_hash = sha256_file(source)
    requested_destination = destination
    action = "COPIED"
    if destination.exists():
        destination_hash = sha256_file(destination)
        if destination_hash == source_hash:
            action = "DEDUPLICATED"
            state.deduplicated.append(
                {
                    "source": str(source),
                    "retained": destination.relative_to(root).as_posix(),
                    "sha256": source_hash,
                }
            )
        else:
            destination = conflict_path(destination, source_hash)
            if destination.exists():
                action = "DEDUPLICATED_CONFLICT_COPY"
                state.deduplicated.append(
                    {
                        "source": str(source),
                        "retained": destination.relative_to(root).as_posix(),
                        "sha256": source_hash,
                    }
                )
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                action = "CONFLICT_PRESERVED"
                state.conflicts.append(
                    {
                        "source": str(source),
                        "requested_destination": requested_destination.relative_to(
                            root
                        ).as_posix(),
                        "preserved_as": destination.relative_to(root).as_posix(),
                        "sha256": source_hash,
                    }
                )
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    if not destination.is_file() or sha256_file(destination) != source_hash:
        raise PackagingError(f"post-copy SHA-256 verification failed: {source}")
    state.sources.append(
        {
            "source_origin": str(source),
            "destination": destination.relative_to(root).as_posix(),
            "size_bytes": source.stat().st_size,
            "sha256": source_hash,
            "action": action,
        }
    )
    return destination


def verify_mappings(root: Path, mappings: Iterable[dict[str, Any]]) -> None:
    failures = []
    for item in mappings:
        destination = root / item["destination"]
        if not destination.is_file() or sha256_file(destination) != item["sha256"]:
            failures.append(item["destination"])
    if failures:
        raise PackagingError(
            "migration destination verification failed:\n" + "\n".join(failures)
        )


def remove_verified_source(
    root: Path,
    source: Path,
    mappings: list[dict[str, Any]],
    *,
    rename_first: bool,
) -> None:
    verify_mappings(root, mappings)
    removal_target = source
    if rename_first:
        removal_target = source.with_name(f"{source.name}.migrated-{ARCHIVE_DATE}")
        if removal_target.exists():
            raise PackagingError(f"migration staging path already exists: {removal_target}")
        source.rename(removal_target)
        verify_mappings(root, mappings)
    shutil.rmtree(removal_target)


def migrate_tree(
    root: Path,
    source: Path,
    mapper: Any,
    state: MigrationState,
    *,
    rename_first: bool,
) -> bool:
    if not source.is_dir():
        return False
    start = len(state.sources)
    for file_path in sorted(path for path in source.rglob("*") if path.is_file()):
        relative = file_path.relative_to(source)
        verified_copy(root, file_path, mapper(relative), state)
    new_mappings = state.sources[start:]
    # Persist the verified destination map before any source directory is
    # renamed or removed, so an interrupted migration remains auditable.
    verify_mappings(root, new_mappings)
    write_migration_state(root, state)
    remove_verified_source(
        root, source, new_mappings, rename_first=rename_first
    )
    return True


def map_external_private(root: Path, relative: Path) -> Path:
    if relative.parts and relative.parts[0] == "patent1":
        return patent_destination(root, Path(*relative.parts[1:]))
    return root / "_private/stage1" / relative


def map_old_private(root: Path, relative: Path) -> Path:
    parts = relative.parts
    if relative.as_posix() == "README_PRIVATE.md":
        return root / "_private/stage1/README_PRIVATE_STAGE1_LEGACY.md"
    if parts and parts[0] == "patent1":
        return patent_destination(root, Path(*parts[1:]))
    if parts[:2] == ("backups", "day1_logs"):
        return backup_destination(root, Path(*parts[1:]))
    if parts[:2] == ("backups", "git_bundle"):
        return backup_destination(root, relative)
    if relative.as_posix() == "manifest.json":
        return root / "_backups/manifests/private_stage1_manifest.json"
    if relative.as_posix() == "sha256.txt":
        return root / "_backups/manifests/private_stage1_sha256.txt"
    if parts and parts[0] == "stage1_reports_copy":
        return root / "_private/stage1/reports_copy" / Path(*parts[1:])
    return root / "_private/stage1/legacy_private_stage1" / relative


def archive_legacy_zips(root: Path, state: MigrationState) -> None:
    parent = root.parent
    destination_dir = root / "_archives/legacy_packages"
    candidates = sorted(parent.glob("Degen-LIO*.zip"))
    for source in candidates:
        if source.name == CANONICAL_ZIP_NAME:
            continue
        source_hash = sha256_file(source)
        destination = verified_copy(
            root, source, destination_dir / source.name, state
        )
        state.legacy_archives.append(
            {
                "original_path": str(source),
                "archived_path": destination.relative_to(root).as_posix(),
                "size_bytes": source.stat().st_size,
                "sha256": source_hash,
            }
        )
        if sha256_file(destination) != source_hash:
            raise PackagingError(f"legacy ZIP verification failed: {source}")
        source.unlink()


def write_private_readme(root: Path) -> None:
    text = f"""# Private project material

This directory is part of the canonical private Degen-LIO project package.
It contains unpublished patent drafts, prior-art search records, and private
Stage 1 evidence copies. Treat the contents as confidential and do not add
them to Git or publish them before patent-counsel review.

The directory is excluded only through `.git/info/exclude`; that local rule
does not modify the public `.gitignore`. The canonical private delivery is
`~/{CANONICAL_ZIP_NAME}`. Patent documents and prior-art conclusions are copied
byte-for-byte and are not edited by the packaging workflow.

Current frozen scientific status remains: Stage 2A detector confirmed;
Stage 1C risk prediction and Stage 2B/2C update candidates rejected/no-go;
FAST-LIO2 integration and risk warning unauthorized.
"""
    (root / "_private/README_PRIVATE.md").write_text(text, encoding="utf-8")


def consolidate_sources(root: Path) -> MigrationState:
    ensure_layout(root)
    assert_private_untracked(root)
    head = run(["git", "rev-parse", "HEAD"], cwd=root).stdout.strip()
    state = MigrationState(original_git_head=head)

    external_private = root.parent / "Degen-LIO-private-IP"
    state.external_private_ip_found = external_private.is_dir()
    if state.external_private_ip_found:
        state.external_private_ip_migrated = migrate_tree(
            root,
            external_private,
            lambda relative: map_external_private(root, relative),
            state,
            rename_first=True,
        )
        write_migration_state(root, state)

    external_backups = root.parent / "Degen-LIO-backups"
    state.external_backups_found = external_backups.is_dir()
    if state.external_backups_found:
        state.external_backups_migrated = migrate_tree(
            root,
            external_backups,
            lambda relative: backup_destination(root, relative),
            state,
            rename_first=True,
        )
        write_migration_state(root, state)

    old_private = root / "_private_stage1"
    state.old_private_stage1_found = old_private.is_dir()
    if state.old_private_stage1_found:
        state.old_private_stage1_migrated = migrate_tree(
            root,
            old_private,
            lambda relative: map_old_private(root, relative),
            state,
            rename_first=False,
        )
        write_migration_state(root, state)

    archive_legacy_zips(root, state)
    write_private_readme(root)
    verify_mappings(root, state.sources)
    state.completed_at = now_iso()
    write_migration_state(root, state)
    return state


def load_migration(root: Path) -> dict[str, Any]:
    path = root / MIGRATION_REPORT
    if not path.is_file():
        return {
            "original_git_head": run(
                ["git", "rev-parse", "HEAD"], cwd=root
            ).stdout.strip(),
            "external_private_ip_found": False,
            "external_private_ip_migrated": False,
            "external_backups_found": False,
            "external_backups_migrated": False,
            "old_private_stage1_found": False,
            "old_private_stage1_migrated": False,
            "source_mappings": [],
            "deduplicated": [],
            "conflicts": [],
            "legacy_archives": [],
        }
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def excluded_parts(relative: Path) -> bool:
    parts = relative.parts
    if any(part in SKIP_DIR_NAMES for part in parts):
        return True
    if len(parts) >= 2 and parts[:2] == ("_archives", "legacy_packages"):
        return True
    if relative.suffix.lower() in SKIP_SUFFIXES:
        return True
    return False


def included_files(root: Path) -> list[Path]:
    result = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if excluded_parts(relative):
            continue
        result.append(path)
    return sorted(result, key=lambda item: item.relative_to(root).as_posix())


def xml_local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def xml_attribute(element: ET.Element | None, namespace: str, name: str) -> str | None:
    if element is None:
        return None
    return element.get(f"{{{namespace}}}{name}") or element.get(name)


def math_child(element: ET.Element, name: str) -> ET.Element | None:
    return next((child for child in element if xml_local_name(child) == name), None)


def omml_to_text(element: ET.Element) -> str:
    """Render Word OMML as readable, deliberately plain mathematical text."""

    name = xml_local_name(element)
    if name == "t":
        return element.text or ""
    if name.endswith("Pr") or name in {
        "ctrlPr",
        "count",
        "jc",
        "limLoc",
        "mcJc",
        "plcHide",
        "scr",
        "sepChr",
        "sty",
    }:
        return ""

    def rendered(child_name: str) -> str:
        child = math_child(element, child_name)
        return omml_to_text(child) if child is not None else ""

    if name == "f":
        return f"({rendered('num')})/({rendered('den')})"
    if name == "sSub":
        return f"{rendered('e')}_{{{rendered('sub')}}}"
    if name == "sSup":
        return f"{rendered('e')}^{{{rendered('sup')}}}"
    if name == "sSubSup":
        return (
            f"{rendered('e')}_{{{rendered('sub')}}}^{{{rendered('sup')}}}"
        )
    if name == "d":
        properties = math_child(element, "dPr")
        beginning = "("
        ending = ")"
        if properties is not None:
            beginning = xml_attribute(
                math_child(properties, "begChr"), M_NS, "val"
            ) or beginning
            ending = xml_attribute(
                math_child(properties, "endChr"), M_NS, "val"
            ) or ending
        return f"{beginning}{rendered('e')}{ending}"
    if name == "acc":
        properties = math_child(element, "accPr")
        accent = "^"
        if properties is not None:
            accent = xml_attribute(math_child(properties, "chr"), M_NS, "val") or accent
        return f"{accent}({rendered('e')})"
    if name == "nary":
        properties = math_child(element, "naryPr")
        operator = "Σ"
        if properties is not None:
            operator = xml_attribute(math_child(properties, "chr"), M_NS, "val") or operator
        subscript = rendered("sub")
        superscript = rendered("sup")
        bounds = f"_{{{subscript}}}" if subscript else ""
        bounds += f"^{{{superscript}}}" if superscript else ""
        return f"{operator}{bounds} {rendered('e')}"
    if name == "limLow":
        return f"{rendered('e')}_{{{rendered('lim')}}}"
    if name == "limUpp":
        return f"{rendered('e')}^{{{rendered('lim')}}}"
    if name == "m":
        rows = []
        for row in (child for child in element if xml_local_name(child) == "mr"):
            cells = [
                omml_to_text(child)
                for child in row
                if xml_local_name(child) == "e"
            ]
            rows.append("[" + ", ".join(cells) + "]")
        return "[" + "; ".join(rows) + "]"
    if name == "rad":
        degree = rendered("deg")
        prefix = f"root[{degree}]" if degree else "sqrt"
        return f"{prefix}({rendered('e')})"
    if name == "func":
        return f"{rendered('fName')}({rendered('e')})"

    return "".join(omml_to_text(child) for child in element)


def normalize_inline_text(text: str) -> str:
    text = text.replace("\u00a0", " ").replace("\r", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()


def paragraph_text(paragraph: ET.Element) -> str:
    parts: list[str] = []

    def visit(element: ET.Element) -> None:
        name = xml_local_name(element)
        if element.tag == f"{{{M_NS}}}oMath":
            parts.append(omml_to_text(element))
            return
        if element.tag in {f"{{{W_NS}}}t", f"{{{M_NS}}}t"}:
            parts.append(element.text or "")
            return
        if element.tag == f"{{{W_NS}}}tab":
            parts.append("\t")
            return
        if element.tag == f"{{{W_NS}}}br":
            parts.append("\n")
            return
        if name in {"pPr", "rPr", "oMathParaPr"}:
            return
        for child in element:
            visit(child)

    visit(paragraph)
    return normalize_inline_text("".join(parts))


def docx_style_map(styles_root: ET.Element) -> dict[str, dict[str, Any]]:
    styles: dict[str, dict[str, Any]] = {}
    for style in styles_root.findall("w:style", XML_NAMESPACES):
        style_id = xml_attribute(style, W_NS, "styleId") or ""
        name_node = style.find("w:name", XML_NAMESPACES)
        outline_node = style.find("w:pPr/w:outlineLvl", XML_NAMESPACES)
        outline = xml_attribute(outline_node, W_NS, "val")
        styles[style_id] = {
            "name": xml_attribute(name_node, W_NS, "val") or "",
            "outline": int(outline) if outline and outline.isdigit() else None,
        }
    return styles


def paragraph_style(
    paragraph: ET.Element, styles: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    style_node = paragraph.find("w:pPr/w:pStyle", XML_NAMESPACES)
    style_id = xml_attribute(style_node, W_NS, "val") or ""
    return styles.get(style_id, {"name": "", "outline": None})


def formula_parse_status(formula: ET.Element, rendered: str) -> tuple[str, list[str]]:
    known_math_tags = {
        "acc",
        "accPr",
        "begChr",
        "chr",
        "count",
        "ctrlPr",
        "d",
        "dPr",
        "deg",
        "den",
        "e",
        "endChr",
        "f",
        "fName",
        "fPr",
        "func",
        "jc",
        "lim",
        "limLoc",
        "limLow",
        "limLowPr",
        "limUpp",
        "m",
        "mc",
        "mcJc",
        "mcPr",
        "mcs",
        "mPr",
        "mr",
        "nary",
        "naryPr",
        "num",
        "oMath",
        "oMathPara",
        "oMathParaPr",
        "plcHide",
        "r",
        "rad",
        "rPr",
        "sSub",
        "sSubPr",
        "sSubSup",
        "sSubSupPr",
        "sSup",
        "sSupPr",
        "scr",
        "sepChr",
        "sty",
        "sub",
        "sup",
        "t",
    }
    unknown = sorted(
        {
            xml_local_name(item)
            for item in formula.iter()
            if item.tag.startswith(f"{{{M_NS}}}")
            and xml_local_name(item) not in known_math_tags
        }
    )
    if not rendered or unknown:
        return "FORMULA_PARSE_PARTIAL", unknown
    return "PARSED_TEXT", []


def markdown_table(table: ET.Element) -> list[str]:
    rows = []
    for row in table.findall("w:tr", XML_NAMESPACES):
        cells = []
        for cell in row.findall("w:tc", XML_NAMESPACES):
            value = "<br>".join(
                filter(None, (paragraph_text(p) for p in cell.findall("w:p", XML_NAMESPACES)))
            )
            cells.append(value.replace("|", "\\|").replace("\n", "<br>"))
        if cells:
            rows.append(cells)
    if not rows:
        return []
    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    output = ["| " + " | ".join(rows[0]) + " |"]
    output.append("| " + " | ".join(["---"] * width) + " |")
    output.extend("| " + " | ".join(row) + " |" for row in rows[1:])
    return output


def extract_patent_docx(
    source: Path, markdown_output: Path, formula_output: Path
) -> dict[str, Any]:
    with zipfile.ZipFile(source) as archive:
        document = ET.fromstring(archive.read("word/document.xml"))
        styles_root = ET.fromstring(archive.read("word/styles.xml"))
    styles = docx_style_map(styles_root)
    body = document.find("w:body", XML_NAMESPACES)
    if body is None:
        raise PackagingError(f"DOCX has no document body: {source}")

    paragraphs = list(body.iter(f"{{{W_NS}}}p"))
    paragraph_indices = {id(item): index for index, item in enumerate(paragraphs, 1)}
    texts = [paragraph_text(item) for item in paragraphs]
    sections: list[str] = []
    current_section = "Document preamble"
    for paragraph, text in zip(paragraphs, texts):
        style = paragraph_style(paragraph, styles)
        if style["outline"] is not None and style["outline"] <= 3 and text:
            current_section = text
        sections.append(current_section)

    title = ""
    for table in body.findall("w:tbl", XML_NAMESPACES):
        for row in table.findall("w:tr", XML_NAMESPACES):
            cells = row.findall("w:tc", XML_NAMESPACES)
            cell_text = [
                " ".join(filter(None, (paragraph_text(p) for p in cell.findall("w:p", XML_NAMESPACES))))
                for cell in cells
            ]
            if cell_text and cell_text[0].strip() == "专利名称" and len(cell_text) > 1:
                title = cell_text[1].strip()
                break
        if title:
            break
    if not title:
        title = next((text for text in texts if text), source.stem)

    formula_rows: list[dict[str, Any]] = []
    paragraph_formulas: dict[int, list[dict[str, Any]]] = {}
    formula_index = 0
    for zero_index, paragraph in enumerate(paragraphs):
        formulas = paragraph.findall(".//m:oMath", XML_NAMESPACES)
        for local_index, formula in enumerate(formulas, 1):
            formula_index += 1
            rendered = normalize_inline_text(omml_to_text(formula))
            status, unknown = formula_parse_status(formula, rendered)
            preceding = next(
                (texts[index] for index in range(zero_index - 1, -1, -1) if texts[index]),
                "",
            )
            following = next(
                (
                    texts[index]
                    for index in range(zero_index + 1, len(texts))
                    if texts[index]
                ),
                "",
            )
            row = {
                "formula_id": f"F{formula_index:03d}",
                "section": sections[zero_index],
                "paragraph_index": zero_index + 1,
                "formula_text_or_summary": rendered or "FORMULA_PARSE_PARTIAL",
                "parse_status": status,
                "omml_object_index": formula_index,
                "notes": (
                    f"omml_objects_in_paragraph={len(formulas)}; "
                    f"paragraph_object_index={local_index}; "
                    f"preceding={preceding[:180]}; following={following[:180]}; "
                    f"unknown_math_tags={','.join(unknown) or 'none'}"
                ),
            }
            formula_rows.append(row)
            paragraph_formulas.setdefault(zero_index + 1, []).append(row)

    markdown_lines = [
        "# Patent 1 current readable text export",
        "",
        f"- Patent title: {title}",
        f"- Source file: `{source}`",
        f"- Source SHA-256: `{sha256_file(source)}`",
        f"- Body paragraph count: {len(paragraphs)}",
        f"- Table count: {len(body.findall('w:tbl', XML_NAMESPACES))}",
        f"- OMML formula object count: {len(formula_rows)}",
        "- Conversion: read-only WordprocessingML/OMML to plain Markdown; the DOCX was not modified.",
        "",
        f"# {title}",
        "",
    ]
    for child in body:
        name = xml_local_name(child)
        if name == "p":
            text = paragraph_text(child)
            index = paragraph_indices[id(child)]
            style = paragraph_style(child, styles)
            if text:
                if style["outline"] is not None and style["outline"] <= 3:
                    markdown_lines.extend(
                        [f"{'#' * (style['outline'] + 1)} {text}", ""]
                    )
                elif style["name"] == "Title":
                    markdown_lines.extend([f"**{text}**", ""])
                elif style["name"] == "Subtitle":
                    markdown_lines.extend([f"*{text}*", ""])
                elif style["name"] == "Compact":
                    markdown_lines.extend([f"- {text}", ""])
                else:
                    markdown_lines.extend([text, ""])
            elif child.find(".//w:drawing", XML_NAMESPACES) is not None:
                markdown_lines.extend(
                    ["[Embedded figure omitted from plain-text export; caption retained below.]", ""]
                )
            for formula in paragraph_formulas.get(index, []):
                markdown_lines.extend(
                    [
                        f"> {formula['formula_id']} | section: {formula['section']} | "
                        f"OMML object: {formula['omml_object_index']} | "
                        f"status: {formula['parse_status']}",
                        f"> `{formula['formula_text_or_summary']}`",
                        "",
                    ]
                )
        elif name == "tbl":
            markdown_lines.extend(markdown_table(child))
            markdown_lines.append("")

    markdown_lines.extend(
        [
            "# Formula location inventory",
            "",
            "The adjacent text is retained in the CSV `notes` field. Any formula that cannot be rendered reliably is explicitly marked `FORMULA_PARSE_PARTIAL`.",
            "",
        ]
    )
    for formula in formula_rows:
        markdown_lines.extend(
            [
                f"- {formula['formula_id']} — section `{formula['section']}`, "
                f"paragraph {formula['paragraph_index']}, OMML object "
                f"{formula['omml_object_index']}, `{formula['parse_status']}`: "
                f"`{formula['formula_text_or_summary']}`"
            ]
        )
    markdown_output.write_text("\n".join(markdown_lines) + "\n", encoding="utf-8")

    fieldnames = (
        "formula_id",
        "section",
        "paragraph_index",
        "formula_text_or_summary",
        "parse_status",
        "omml_object_index",
        "notes",
    )
    with formula_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(formula_rows)
    return {
        "title": title,
        "sha256": sha256_file(source),
        "paragraph_count": len(paragraphs),
        "table_count": len(body.findall("w:tbl", XML_NAMESPACES)),
        "formula_count": len(formula_rows),
        "partial_formula_count": sum(
            row["parse_status"] == "FORMULA_PARSE_PARTIAL" for row in formula_rows
        ),
    }


def candidate_files(root: Path, filename: str) -> list[Path]:
    candidates = []
    for path in root.rglob(filename):
        relative = path.relative_to(root)
        if not path.is_file() or excluded_parts(relative):
            continue
        if relative.parts and relative.parts[0] == "review_exports":
            continue
        candidates.append(path)
    return sorted(candidates)


def select_identical_candidate(
    candidates: list[Path], *, prefer_ascii: bool = False
) -> tuple[Path | None, str, list[dict[str, str]]]:
    records = [
        {"path": str(path), "sha256": sha256_file(path)} for path in candidates
    ]
    if not candidates:
        return None, "MISSING", records
    if len({record["sha256"] for record in records}) > 1:
        return None, "CONFLICT", records
    ordered = candidates
    if prefer_ascii:
        ordered = sorted(
            candidates,
            key=lambda path: (
                not path.name.isascii(),
                len(path.name),
                path.as_posix(),
            ),
        )
    status = "BYTE_IDENTICAL" if len(candidates) > 1 else "COPIED"
    return ordered[0], status, records


def copy_review_source(root: Path, source: Path, export_name: str) -> dict[str, Any]:
    destination = root / "review_exports" / export_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    source_hash = sha256_file(source)
    if sha256_file(destination) != source_hash:
        raise PackagingError(f"review export copy verification failed: {source}")
    return {
        "export_name": export_name,
        "source_path": str(source),
        "source_sha256": source_hash,
        "export_path": destination.relative_to(root).as_posix(),
        "export_sha256": source_hash,
        "size_bytes": destination.stat().st_size,
        "exists": True,
        "status": "COPIED",
        "notes": "",
    }


def parse_report_fields(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    fields: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^([A-Z][A-Z0-9_]+):\s*(.*?)\s*$", line.strip())
        if match:
            fields[match.group(1)] = match.group(2)
    if "BASELINE_FREEZE_PASS_WITH_WARNINGS" in text:
        fields["DAY1_GATE"] = "BASELINE_FREEZE_PASS_WITH_WARNINGS"
    return fields


def write_review_manifest(root: Path, records: list[dict[str, Any]]) -> None:
    fields = (
        "export_name",
        "source_path",
        "source_sha256",
        "export_path",
        "export_sha256",
        "size_bytes",
        "exists",
        "status",
        "notes",
    )
    by_name = {record["export_name"]: record for record in records}
    with (root / "REVIEW_MANIFEST.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for name in REVIEW_EXPORT_NAMES:
            record = by_name.get(
                name,
                {
                    "export_name": name,
                    "source_path": "",
                    "source_sha256": "",
                    "export_path": f"review_exports/{name}",
                    "export_sha256": "",
                    "size_bytes": 0,
                    "exists": False,
                    "status": "MISSING",
                    "notes": "required export was not generated",
                },
            )
            writer.writerow(record)


def write_critical_hashes(root: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    destination = root / "review_exports/critical_file_hashes.csv"
    rows = []
    seen = set()
    for record in records:
        for role, path_key, hash_key in (
            ("SOURCE", "source_path", "source_sha256"),
            ("REVIEW_EXPORT", "export_path", "export_sha256"),
        ):
            value = record.get(path_key)
            digest = record.get(hash_key)
            if not value or not digest or (role, value) in seen:
                continue
            seen.add((role, value))
            path = Path(value) if role == "SOURCE" else root / value
            rows.append(
                {
                    "role": role,
                    "path": value,
                    "size_bytes": path.stat().st_size if path.is_file() else 0,
                    "sha256": digest,
                    "notes": record.get("status", ""),
                }
            )
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=("role", "path", "size_bytes", "sha256", "notes")
        )
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda item: (item["role"], item["path"])))
    return {
        "export_name": destination.name,
        "source_path": "generated from REVIEW_MANIFEST source/export mappings",
        "source_sha256": "",
        "export_path": destination.relative_to(root).as_posix(),
        "export_sha256": sha256_file(destination),
        "size_bytes": destination.stat().st_size,
        "exists": True,
        "status": "GENERATED",
        "notes": "self-entry intentionally omitted to avoid recursive hashing",
    }


def generated_export_record(
    root: Path,
    export_name: str,
    source_path: str,
    source_sha256: str,
    *,
    status: str = "GENERATED",
    notes: str = "",
) -> dict[str, Any]:
    destination = root / "review_exports" / export_name
    return {
        "export_name": export_name,
        "source_path": source_path,
        "source_sha256": source_sha256,
        "export_path": destination.relative_to(root).as_posix(),
        "export_sha256": sha256_file(destination) if destination.is_file() else "",
        "size_bytes": destination.stat().st_size if destination.is_file() else 0,
        "exists": destination.is_file(),
        "status": status if destination.is_file() else "MISSING",
        "notes": notes,
    }


def missing_export_record(
    export_name: str, source_description: str, status: str, notes: str
) -> dict[str, Any]:
    return {
        "export_name": export_name,
        "source_path": source_description,
        "source_sha256": "",
        "export_path": f"review_exports/{export_name}",
        "export_sha256": "",
        "size_bytes": 0,
        "exists": False,
        "status": status,
        "notes": notes,
    }


def write_review_index(
    root: Path,
    git: dict[str, Any],
    pytest: dict[str, Any],
    patent: dict[str, Any],
    day2: dict[str, str],
    day3: dict[str, str],
    records: list[dict[str, Any]],
    missing: list[str],
    conflicts: list[str],
    package_complete: bool,
    package_status: str,
    zip_sha256: str,
    packaging_time: str,
) -> None:
    purposes = {
        "day1_baseline_audit.md": "Day 1 baseline and frozen scientific-status audit",
        "day2_traceability_gate.md": "Day 2 patent/formula/code traceability gate",
        "day3_prior_art_gate.md": "Day 3 prior-art search gate and retained warnings",
        "closest_prior_art_matrix.md": "closest-reference element comparison",
        "combination_attack_matrix.md": "combined-reference inventive-step attacks",
        "novelty_inventiveness_risk.md": "novelty and inventiveness risk analysis",
        "recommended_claim_boundary.md": "recommended claim boundary",
        "patent1_current_text.md": "plain-text export of the current patent DOCX",
        "patent1_formula_inventory.csv": "OMML formula locations and readable renderings",
        "patent1_revision_report.md": "V1.2 revision report plus change summary",
        "project_state.md": "current repository and frozen project state",
        "packaging_report.md": "canonical package generation report",
        "critical_file_hashes.csv": "SHA-256 inventory for critical sources and exports",
    }
    direct_files = "\n".join(
        f"- `review_exports/{name}` — {purposes[name]}" for name in REVIEW_EXPORT_NAMES
    )
    missing_text = (
        "\n".join(f"- MISSING: `{item}`" for item in missing)
        or "- Missing files: none"
    )
    conflict_text = (
        "\n".join(f"- CONFLICT: `{item}`" for item in conflicts)
        or "- Conflicting files: none"
    )
    worktree = "clean" if git["worktree_clean"] else "not clean"
    text = f"""# Degen-LIO Review Index

## Current repository

- Branch: `{git['branch']}`
- HEAD: `{git['head']}`
- Worktree status: `{worktree}`
- Python version: `{platform.python_version()}`
- pytest result: `{pytest['passed_count']} passed, {pytest['failed_count']} failed, {pytest['skipped_count']} skipped` (exit `{pytest['exit_code']}`)

## Scientific status

- Stage 1C: `REJECTED`; confirmatory risk-prediction gate is NO-GO.
- Stage 2A: `CONFIRMED`; detector and weak-direction gate passed.
- Stage 2B: `REJECTED`; column-scaled update is a frozen NO-GO.
- Stage 2C: `REJECTED`; projected gain failed the reserved performance gate.
- FAST-LIO2: `NOT_IMPLEMENTED` and unauthorized.
- Real IMU: `NOT_IMPLEMENTED`; only the documented deterministic surrogate exists.
- Real association: `NOT_IMPLEMENTED`; controlled correspondence generation is not a deployed association system.
- Complete Degen-LIO: `NOT_IMPLEMENTED`; the repository contains prototype components, not a complete deployed system.

RISK_WARNING_AUTHORIZED=false
DETECTOR_PASS=true
SELECTIVE_UPDATE_PASS=false
PROJECTED_GAIN_UPDATE_PASS=false
FAST_LIO2_INTEGRATION_AUTHORIZED=false

## Patent status

- Current patent file: `{patent.get('source_path', '')}`
- Patent SHA-256: `{patent.get('sha256', '')}`
- Day 2 Gate: `{day2.get('DAY2_GATE', 'MISSING')}`
- Day 2 P0/P1/P2: `{day2.get('P0_ISSUE_COUNT', 'MISSING')}/{day2.get('P1_ISSUE_COUNT', 'MISSING')}/{day2.get('P2_ISSUE_COUNT', 'MISSING')}`
- Formula count: `{patent.get('formula_count', 'MISSING')}` OMML objects
- F13 formula status: `{'MATCH' if day2.get('F13_FORMULA_MATCH', '').lower() == 'true' else 'NOT_VERIFIED'}`

## Prior-art status

- Day 3 Gate: `{day3.get('DAY3_GATE', 'MISSING')}`
- Candidate patent family count: `{day3.get('PATENT_FAMILY_CANDIDATE_COUNT', 'MISSING')}`
- High-relevance patent count: `{day3.get('HIGH_RELEVANCE_PATENT_COUNT', 'MISSING')}`
- Deep-review patent count: `{day3.get('DEEP_REVIEW_PATENT_COUNT', 'MISSING')}`
- Candidate paper count: `{day3.get('NON_PATENT_CANDIDATE_COUNT', 'MISSING')}`
- High-relevance paper count: `{day3.get('HIGH_RELEVANCE_PAPER_COUNT', 'MISSING')}`
- Deep-review paper count: `{day3.get('DEEP_REVIEW_PAPER_COUNT', 'MISSING')}`
- Closest reference: `{day3.get('PRIMARY_CLOSEST_REFERENCE', 'MISSING')}`
- Combination risk: `{day3.get('COMBINATION_INVENTIVENESS_RISK', 'MISSING')}`

## Directly readable files

{direct_files}

## Missing or conflicting files

{missing_text}
{conflict_text}

## Package status

- Package complete: `{str(package_complete).lower()}`
- Final status: `{package_status}`
- ZIP SHA-256: `{zip_sha256}`
- Packaging time: `{packaging_time}`

The ZIP digest is detached in the archived copy because an archive cannot contain its own final digest without changing that digest. The live file and packaging report are refreshed with the final value after atomic replacement.
"""
    (root / "REVIEW_INDEX.md").write_text(text, encoding="utf-8")


def write_package_audit(
    root: Path,
    git: dict[str, Any],
    pytest: dict[str, Any],
    bundle: dict[str, Any],
    patent: dict[str, Any],
    day1: dict[str, str],
    day2: dict[str, str],
    day3: dict[str, str],
    records: list[dict[str, Any]],
    missing: list[str],
    conflicts: list[str],
    candidate_audit: dict[str, Any],
    package_complete: bool,
    package_status: str,
    zip_sha256: str,
) -> None:
    by_name = {record["export_name"]: record for record in records}

    def exists(name: str) -> bool:
        return bool(by_name.get(name, {}).get("exists"))

    private_count = len(private_tracked_files(root))
    patent_tracked = run(
        ["git", "ls-files", "_private/patent1/**"], cwd=root
    ).stdout.splitlines()
    worktree = str(git["worktree_clean"]).lower()
    lines = [
        "# Degen-LIO Package Audit",
        "",
        f"PROJECT_ROOT: {root}",
        f"GIT_BRANCH: {git['branch']}",
        f"GIT_HEAD: {git['head']}",
        f"WORKTREE_CLEAN: {worktree}",
        "",
        f"PYTHON_VERSION: {platform.python_version()}",
        f"PYTEST_COMMAND: {pytest['command']}",
        f"PYTEST_PASS: {str(pytest['pass']).lower()}",
        f"PYTEST_PASSED_COUNT: {pytest['passed_count']}",
        f"PYTEST_FAILED_COUNT: {pytest['failed_count']}",
        f"PYTEST_SKIPPED_COUNT: {pytest['skipped_count']}",
        "",
        f"DAY1_GATE: {day1.get('DAY1_GATE', 'MISSING')}",
        f"DAY2_GATE: {day2.get('DAY2_GATE', 'MISSING')}",
        f"DAY3_GATE: {day3.get('DAY3_GATE', 'MISSING')}",
        "",
        f"PATENT_CURRENT_PATH: {patent.get('source_path', 'MISSING')}",
        f"PATENT_CURRENT_SHA256: {patent.get('sha256', 'MISSING')}",
        f"PATENT_TEXT_EXPORT_EXISTS: {str(exists('patent1_current_text.md')).lower()}",
        f"PATENT_FORMULA_INVENTORY_EXISTS: {str(exists('patent1_formula_inventory.csv')).lower()}",
        "",
        f"CLOSEST_PRIOR_ART_EXISTS: {str(exists('closest_prior_art_matrix.md')).lower()}",
        f"COMBINATION_ATTACK_EXISTS: {str(exists('combination_attack_matrix.md')).lower()}",
        f"NOVELTY_RISK_EXISTS: {str(exists('novelty_inventiveness_risk.md')).lower()}",
        f"CLAIM_BOUNDARY_EXISTS: {str(exists('recommended_claim_boundary.md')).lower()}",
        "",
        f"PRIVATE_GIT_TRACKED_COUNT: {private_count}",
        f"PATENT_GIT_TRACKED_COUNT: {len(patent_tracked)}",
        f"BUNDLE_EXISTS: {str((root / bundle['path']).is_file()).lower()}",
        f"BUNDLE_SHA256: {bundle['sha256']}",
        f"BUNDLE_VERIFY_PASS: {str(bundle['verify_pass']).lower()}",
        "",
        f"REVIEW_EXPORT_FILE_COUNT: {sum(record.get('exists', False) for record in records)}",
        f"MISSING_CRITICAL_FILE_COUNT: {len(missing)}",
        f"CONFLICT_CRITICAL_FILE_COUNT: {len(conflicts)}",
        f"MISSING_CRITICAL_FILES: {json.dumps(missing, ensure_ascii=False)}",
        f"CONFLICT_CRITICAL_FILES: {json.dumps(conflicts, ensure_ascii=False)}",
        "",
        f"PACKAGE_COMPLETE: {str(package_complete).lower()}",
        f"FINAL_STATUS: {package_status}",
        f"CANONICAL_ZIP_SHA256: {zip_sha256}",
        f"PACKAGING_TIME: {now_iso()}",
        "",
        "## Candidate resolution audit",
        "",
        "```json",
        json.dumps(candidate_audit, ensure_ascii=False, indent=2),
        "```",
    ]
    (root / "PACKAGE_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_package_contents(root: Path) -> None:
    files = [
        path
        for path in included_files(root)
        if path.relative_to(root).as_posix() != "PACKAGE_CONTENTS.txt"
    ]
    lines = [
        "Degen-LIO canonical package contents",
        f"Generated: {now_iso()}",
        f"Project root: {root}",
        "Historical ZIPs under _archives/legacy_packages/ are intentionally excluded.",
        "The .git directory, caches, virtual environments, pyc, and pyo files are excluded.",
        "",
        "relative_path",
        "PACKAGE_CONTENTS.txt",
    ]
    lines.extend(
        path.relative_to(root).as_posix()
        for path in files
    )
    (root / "PACKAGE_CONTENTS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_review_exports(
    root: Path,
    git: dict[str, Any],
    pytest: dict[str, Any],
    bundle: dict[str, Any],
    *,
    archive_verified: bool,
    zip_sha256: str,
) -> dict[str, Any]:
    review_dir = root / "review_exports"
    review_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    missing: list[str] = []
    conflicts: list[str] = []
    candidate_audit: dict[str, Any] = {}

    fixed_sources = {
        "day1_baseline_audit.md": root / "reports/stage1/baseline_audit_20260720.md",
        "day2_traceability_gate.md": root
        / "reports/stage1/day2_traceability_gate_20260721_revision2.md",
        "day3_prior_art_gate.md": root
        / "reports/stage1/day3_prior_art_gate_20260722.md",
    }
    for export_name, source in fixed_sources.items():
        if source.is_file():
            records.append(copy_review_source(root, source, export_name))
        else:
            missing.append(export_name)
            records.append(
                missing_export_record(export_name, str(source), "MISSING", "source absent")
            )

    prior_art_mapping = {
        "06_closest_prior_art_matrix.md": "closest_prior_art_matrix.md",
        "07_combination_attack_matrix.md": "combination_attack_matrix.md",
        "08_novelty_inventiveness_risk.md": "novelty_inventiveness_risk.md",
        "09_recommended_claim_boundary.md": "recommended_claim_boundary.md",
    }
    for source_name, export_name in prior_art_mapping.items():
        candidates = candidate_files(root, source_name)
        chosen, status, audit = select_identical_candidate(candidates)
        candidate_audit[source_name] = {"status": status, "candidates": audit}
        if chosen is None:
            target = conflicts if status == "CONFLICT" else missing
            target.append(export_name)
            records.append(
                missing_export_record(
                    export_name,
                    source_name,
                    status,
                    json.dumps(audit, ensure_ascii=False),
                )
            )
            continue
        record = copy_review_source(root, chosen, export_name)
        record["status"] = status
        record["notes"] = json.dumps(audit, ensure_ascii=False)
        records.append(record)

    patent_candidates = sorted(
        {
            *candidate_files(root, "patent1_degen_lio_v1_2_agent_review.docx"),
            *[
                path
                for path in root.rglob("*V1.2*代理人送审版.docx")
                if path.is_file() and not excluded_parts(path.relative_to(root))
            ],
        }
    )
    patent_source, patent_status, patent_audit = select_identical_candidate(
        patent_candidates, prefer_ascii=True
    )
    candidate_audit["current_patent_docx"] = {
        "status": patent_status,
        "candidates": patent_audit,
    }
    patent_info: dict[str, Any] = {"source_path": "MISSING", "sha256": ""}
    if patent_source is None:
        target = conflicts if patent_status == "CONFLICT" else missing
        target.extend(["patent1_current_text.md", "patent1_formula_inventory.csv"])
        for export_name in ("patent1_current_text.md", "patent1_formula_inventory.csv"):
            records.append(
                missing_export_record(
                    export_name,
                    "current patent DOCX",
                    patent_status,
                    json.dumps(patent_audit, ensure_ascii=False),
                )
            )
    else:
        patent_info = extract_patent_docx(
            patent_source,
            review_dir / "patent1_current_text.md",
            review_dir / "patent1_formula_inventory.csv",
        )
        patent_info["source_path"] = str(patent_source)
        for export_name in ("patent1_current_text.md", "patent1_formula_inventory.csv"):
            records.append(
                generated_export_record(
                    root,
                    export_name,
                    str(patent_source),
                    patent_info["sha256"],
                    status=patent_status,
                    notes=(
                        f"formula_count={patent_info['formula_count']}; "
                        f"partial_formula_count={patent_info['partial_formula_count']}; "
                        f"candidates={json.dumps(patent_audit, ensure_ascii=False)}"
                    ),
                )
            )

    revision = root / "_private/patent1/current/patent1_v1_2_revision_report.md"
    summary = root / "_private/patent1/current/patent1_v1_2_change_summary.md"
    revision_output = review_dir / "patent1_revision_report.md"
    if revision.is_file():
        content = revision.read_text(encoding="utf-8")
        source_paths = [str(revision)]
        source_hashes = [sha256_file(revision)]
        if summary.is_file():
            content = (
                content.rstrip()
                + "\n\n# Change Summary\n\n"
                + summary.read_text(encoding="utf-8").lstrip()
            )
            source_paths.append(str(summary))
            source_hashes.append(sha256_file(summary))
        revision_output.write_text(content.rstrip() + "\n", encoding="utf-8")
        records.append(
            generated_export_record(
                root,
                revision_output.name,
                " | ".join(source_paths),
                " | ".join(source_hashes),
                notes="full revision report with complete change summary appended",
            )
        )
    else:
        missing.append(revision_output.name)
        records.append(
            missing_export_record(
                revision_output.name, str(revision), "MISSING", "revision report absent"
            )
        )

    for source_relative, export_name in (
        ("_package/project_state.md", "project_state.md"),
        ("_package/packaging_report.md", "packaging_report.md"),
    ):
        source = root / source_relative
        if source.is_file():
            records.append(copy_review_source(root, source, export_name))
        else:
            missing.append(export_name)
            records.append(
                missing_export_record(export_name, str(source), "MISSING", "source absent")
            )

    hash_record = write_critical_hashes(root, records)
    records.append(hash_record)
    write_review_manifest(root, records)

    day1 = parse_report_fields(fixed_sources["day1_baseline_audit.md"])
    day2 = parse_report_fields(fixed_sources["day2_traceability_gate.md"])
    day3 = parse_report_fields(fixed_sources["day3_prior_art_gate.md"])
    all_exports_exist = all(
        (review_dir / name).is_file() for name in REVIEW_EXPORT_NAMES
    )
    package_complete = bool(
        archive_verified
        and all_exports_exist
        and not missing
        and not conflicts
        and pytest["pass"]
        and bundle["verify_pass"]
        and not private_tracked_files(root)
    )
    package_status = (
        "SINGLE_ROOT_PACKAGE_PASS_WITH_WARNINGS"
        if package_complete
        else "SINGLE_ROOT_PACKAGE_INCOMPLETE"
    )
    generated = now_iso()
    write_review_index(
        root,
        git,
        pytest,
        patent_info,
        day2,
        day3,
        records,
        missing,
        conflicts,
        package_complete,
        package_status,
        zip_sha256,
        generated,
    )
    write_package_audit(
        root,
        git,
        pytest,
        bundle,
        patent_info,
        day1,
        day2,
        day3,
        records,
        missing,
        conflicts,
        candidate_audit,
        package_complete,
        package_status,
        zip_sha256,
    )
    write_package_contents(root)
    return {
        "records": records,
        "missing": sorted(set(missing)),
        "conflicts": sorted(set(conflicts)),
        "candidate_audit": candidate_audit,
        "patent": patent_info,
        "file_count": sum((review_dir / name).is_file() for name in REVIEW_EXPORT_NAMES),
        "complete": package_complete,
        "status": package_status,
    }


def scan_sensitive_files(root: Path) -> list[dict[str, str]]:
    filename_patterns = (
        ".env",
        ".env.*",
        "*.pem",
        "*.key",
        "id_rsa",
        "id_ed25519",
        "credentials.json",
        "service-account*.json",
        "access_token*",
        "secret*",
    )
    content_patterns = (
        ("PEM_PRIVATE_KEY", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
        ("AWS_ACCESS_KEY", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
        (
            "ASSIGNED_SECRET",
            re.compile(
                r"(?i)\b(?:password|passwd|api[_-]?key|access[_-]?token|"
                r"client[_-]?secret)\s*[:=]\s*[\"']?[A-Za-z0-9_+/=-]{12,}"
            ),
        ),
    )
    findings: list[dict[str, str]] = []
    for path in included_files(root):
        relative = path.relative_to(root)
        lower_name = path.name.lower()
        filename_match = next(
            (
                pattern
                for pattern in filename_patterns
                if fnmatch.fnmatch(lower_name, pattern.lower())
            ),
            None,
        )
        if filename_match:
            findings.append(
                {
                    "relative_path": relative.as_posix(),
                    "reason": f"SENSITIVE_FILENAME:{filename_match}",
                }
            )
            continue
        if path.suffix.lower() not in TEXT_SCAN_SUFFIXES or path.stat().st_size > 5_000_000:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for label, pattern in content_patterns:
            if pattern.search(content):
                findings.append(
                    {"relative_path": relative.as_posix(), "reason": label}
                )
                break
    return findings


def update_git_bundle(root: Path) -> dict[str, Any]:
    bundle = root / "_backups/git_bundles/Degen-LIO-full-history.bundle"
    temporary = bundle.with_name(f"{bundle.name}.tmp")
    temporary.unlink(missing_ok=True)
    run(["git", "bundle", "create", str(temporary), "--all"], cwd=root)
    verify = run(["git", "bundle", "verify", str(temporary)], cwd=root)
    os.replace(temporary, bundle)
    return {
        "path": bundle.relative_to(root).as_posix(),
        "size_bytes": bundle.stat().st_size,
        "sha256": sha256_file(bundle),
        "verify_pass": True,
        "verify_output": verify.stdout.strip(),
    }


def git_state(root: Path) -> dict[str, Any]:
    branch = run(["git", "branch", "--show-current"], cwd=root).stdout.strip()
    head = run(["git", "rev-parse", "HEAD"], cwd=root).stdout.strip()
    status_lines = [
        line
        for line in run(["git", "status", "--porcelain"], cwd=root).stdout.splitlines()
        if line
    ]
    log = run(
        ["git", "log", "-10", "--oneline", "--decorate"], cwd=root
    ).stdout.rstrip()
    tags = run(
        ["git", "tag", "--list", "--sort=refname"], cwd=root
    ).stdout.splitlines()
    return {
        "branch": branch,
        "head": head,
        "worktree_clean": not status_lines,
        "status_lines": status_lines,
        "recent_log": log,
        "tags": tags,
    }


def write_project_state(root: Path, state: dict[str, Any]) -> None:
    tags = "\n".join(f"- `{tag}`" for tag in state["tags"]) or "- None"
    status = "clean" if state["worktree_clean"] else "not clean"
    text = f"""# Degen-LIO project state

- Project root: `{root}`
- Recorded at: `{now_iso()}`
- Git branch: `{state['branch']}`
- Git HEAD: `{state['head']}`
- Worktree: **{status}**
- Canonical package: `{root.parent / CANONICAL_ZIP_NAME}`

## Frozen project conclusions

- Stage 1C: confirmatory risk-prediction gate is NO-GO; `RISK_WARNING_AUTHORIZED=false`.
- Stage 2A: detector and weak-direction gate passed; weak-update research was authorized, but risk warning remains unauthorized.
- Stage 2B: column-scaled selective update is a frozen NO-GO; `SELECTIVE_UPDATE_PASS=false`.
- Stage 2C: projected-gain formulation passed mathematical checks but failed the reserved performance gate; `PROJECTED_GAIN_UPDATE_PASS=false`.
- FAST-LIO2: integration is not implemented or authorized; `FAST_LIO2_INTEGRATION_AUTHORIZED=false`.
- Patent 1: V1.2 agent-review draft and prior-art review package are privately retained; no formal filing is asserted.
- Day 1 Gate: `BASELINE_FREEZE_PASS_WITH_WARNINGS`.
- Day 2 Gate: `TRACEABILITY_PASS_WITH_WARNINGS` (Revision 2).
- Day 3 Gate: `PRIOR_ART_REVIEW_PASS_WITH_WARNINGS`.

RISK_WARNING_AUTHORIZED=false
SELECTIVE_UPDATE_PASS=false
PROJECTED_GAIN_UPDATE_PASS=false
FAST_LIO2_INTEGRATION_AUTHORIZED=false

## Private-material tracking proof

`git ls-files '_private/**' '_backups/**' '_archives/**' '_package/**'`
returned no paths when this state was generated. These directories are excluded
locally in `.git/info/exclude` and are included only in the private canonical ZIP.

## Archive tags

{tags}

## Recent commits

```text
{state['recent_log']}
```
"""
    (root / "_package/project_state.md").write_text(text, encoding="utf-8")


def write_package_readme(root: Path) -> None:
    text = f"""# Canonical package metadata

Run `python3 scripts/package_full_project.py` from `{root}` to rebuild the only
supported delivery archive: `{root.parent / CANONICAL_ZIP_NAME}`.

The workflow performs a filename/content-pattern secret scan, runs the complete
pytest suite, refreshes a `git bundle --all`, writes stable file inventories,
creates the ZIP through a temporary path, atomically replaces the prior ZIP,
then extracts and verifies the archive. Historical ZIPs stay under
`_archives/legacy_packages/` and are deliberately excluded from the canonical
ZIP to prevent recursive growth.

`full_manifest.json` contains explicit self-referential entries for itself and
`full_sha256.txt`; their `sha256` values are null and the notes explain the
exception. `full_sha256.txt` records the actual manifest digest and excludes
only itself. The canonical ZIP digest is necessarily detached because embedding
an archive's own digest would change that digest; the live packaging report and
script output record the final SHA-256 after atomic replacement.
"""
    (root / "_package/README_PACKAGE.md").write_text(text, encoding="utf-8")


def run_pytest(root: Path) -> dict[str, Any]:
    result = run([sys.executable, "-m", "pytest", "-q"], cwd=root, check=False)
    output = result.stdout.rstrip()
    print(output)

    def count(label: str) -> int:
        match = re.search(rf"(\d+)\s+{label}\b", output)
        return int(match.group(1)) if match else 0

    return {
        "command": "python3 -m pytest -q",
        "pass": result.returncode == 0,
        "passed_count": count("passed"),
        "failed_count": count("failed"),
        "skipped_count": count("skipped"),
        "exit_code": result.returncode,
        "summary_tail": "\n".join(output.splitlines()[-3:]),
    }


def tracked_paths(root: Path) -> set[str]:
    output = run(["git", "ls-files", "-z"], cwd=root).stdout
    return {item for item in output.split("\0") if item}


def category_for(relative: Path) -> str:
    parts = relative.parts
    if not parts:
        return "root"
    if parts[:3] == ("_private", "patent1", "prior_art"):
        return "patent_prior_art"
    if parts[:2] == ("_private", "patent1"):
        return "patent"
    if parts[0] == "_private":
        return "private_stage1"
    if parts[0] == "_backups":
        return "backup"
    if parts[0] == "_package":
        return "package_metadata"
    if parts[0] == "review_exports" or relative.name in REVIEW_ROOT_FILES:
        return "readable_review_export"
    mapping = {
        "src": "scientific_code",
        "configs": "configuration",
        "tests": "test",
        "scripts": "script",
        "docs": "documentation",
        "artifacts": "artifact",
        "reports": "report",
        "data": "data",
        "results": "result",
    }
    return mapping.get(parts[0], "root")


def source_origin_map(migration: dict[str, Any]) -> dict[str, str]:
    return {
        item["destination"]: item["source_origin"]
        for item in migration.get("source_mappings", [])
    }


def manifest_entry(
    root: Path,
    path: Path,
    tracked: set[str],
    origins: dict[str, str],
    *,
    included: bool,
) -> dict[str, Any]:
    relative = path.relative_to(root)
    relative_string = relative.as_posix()
    notes = ""
    alias_names = {
        "patent1_degen_lio_v1_2_agent_review.docx",
        "一种隧道退化环境下激光惯性里程计退化检测与弱方向识别方法_专利技术交底书_V1.2_代理人送审版.docx",
    }
    if relative.name in alias_names and relative.parts[:3] == (
        "_private",
        "patent1",
        "current",
    ):
        notes = "BYTE_IDENTICAL_ALIAS"
    return {
        "relative_path": relative_string,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "category": category_for(relative),
        "sensitive": relative.parts[0] in {"_private", "_backups"},
        "git_tracked": relative_string in tracked,
        "included_in_canonical_zip": included,
        "source_origin": origins.get(
            relative_string,
            "generated_packaging_workflow"
            if relative.parts[0] in {"_package", "_backups", "review_exports"}
            or relative.name in REVIEW_ROOT_FILES
            else "git_worktree"
            if relative_string in tracked
            else "existing_untracked_worktree",
        ),
        "notes": notes,
    }


def build_manifest_entries(
    root: Path, migration: dict[str, Any]
) -> list[dict[str, Any]]:
    tracked = tracked_paths(root)
    origins = source_origin_map(migration)
    entries = []
    self_paths = {
        "_package/full_manifest.json",
        "_package/full_sha256.txt",
    }
    for path in included_files(root):
        relative = path.relative_to(root).as_posix()
        if relative in self_paths:
            continue
        entries.append(
            manifest_entry(root, path, tracked, origins, included=True)
        )
    legacy_dir = root / "_archives/legacy_packages"
    for path in sorted(item for item in legacy_dir.glob("*") if item.is_file()):
        entries.append(
            manifest_entry(root, path, tracked, origins, included=False)
        )
    entries.extend(
        [
            {
                "relative_path": ".git/",
                "size_bytes": None,
                "sha256": None,
                "category": "git_metadata",
                "sensitive": True,
                "git_tracked": False,
                "included_in_canonical_zip": False,
                "source_origin": "git_repository_metadata",
                "notes": "DIRECTORY_EXCLUDED; history preserved in full Git bundle",
            },
            {
                "relative_path": "_package/full_manifest.json",
                "size_bytes": None,
                "sha256": None,
                "category": "package_metadata",
                "sensitive": False,
                "git_tracked": False,
                "included_in_canonical_zip": True,
                "source_origin": "generated_packaging_workflow",
                "notes": "SELF_REFERENTIAL; actual digest recorded in full_sha256.txt",
            },
            {
                "relative_path": "_package/full_sha256.txt",
                "size_bytes": None,
                "sha256": None,
                "category": "package_metadata",
                "sensitive": False,
                "git_tracked": False,
                "included_in_canonical_zip": True,
                "source_origin": "generated_packaging_workflow",
                "notes": "SELF_REFERENTIAL; checksum list intentionally excludes itself",
            },
        ]
    )
    return sorted(entries, key=lambda item: item["relative_path"])


def write_manifest(
    root: Path, migration: dict[str, Any], generated_at: str
) -> list[dict[str, Any]]:
    entries = build_manifest_entries(root, migration)
    manifest = {
        "schema_version": 1,
        "generated_at": generated_at,
        "project_root": str(root),
        "canonical_zip": str(root.parent / CANONICAL_ZIP_NAME),
        "entry_count": len(entries),
        "entries": entries,
    }
    manifest_path = root / "_package/full_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = []
    for entry in entries:
        if not entry["included_in_canonical_zip"]:
            continue
        relative = entry["relative_path"]
        if relative == "_package/full_sha256.txt":
            continue
        if relative == "_package/full_manifest.json":
            digest = sha256_file(manifest_path)
        else:
            digest = entry["sha256"]
        if digest:
            lines.append(f"{digest}  {relative}")
    (root / "_package/full_sha256.txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return entries


def count_files(path: Path) -> int:
    return sum(1 for item in path.rglob("*") if item.is_file()) if path.exists() else 0


def build_base_report(
    root: Path,
    git: dict[str, Any],
    migration: dict[str, Any],
    bundle: dict[str, Any],
    pytest: dict[str, Any],
    security_findings: list[dict[str, str]],
) -> dict[str, Any]:
    legacy_files = [
        path
        for path in (root / "_archives/legacy_packages").glob("*")
        if path.is_file()
    ]
    day3_missing = [path for path in DAY3_CORE_PATHS if not (root / path).is_file()]
    private_tracked = private_tracked_files(root)
    patent_tracked = run(
        ["git", "ls-files", "_private/patent1/**"], cwd=root
    ).stdout.splitlines()
    conflicts = migration.get("conflicts", [])
    report: dict[str, Any] = {
        "PROJECT_ROOT": str(root),
        "GIT_BRANCH": git["branch"],
        "GIT_HEAD": git["head"],
        "ORIGINAL_GIT_HEAD": migration.get("original_git_head", git["head"]),
        "WORKTREE_CLEAN": git["worktree_clean"],
        "EXTERNAL_PRIVATE_IP_FOUND": migration.get(
            "external_private_ip_found", False
        ),
        "EXTERNAL_PRIVATE_IP_MIGRATED": migration.get(
            "external_private_ip_migrated", False
        ),
        "EXTERNAL_PRIVATE_IP_REMAINS": (root.parent / "Degen-LIO-private-IP").exists(),
        "EXTERNAL_BACKUPS_FOUND": migration.get("external_backups_found", False),
        "EXTERNAL_BACKUPS_MIGRATED": migration.get(
            "external_backups_migrated", False
        ),
        "EXTERNAL_BACKUPS_REMAINS": (root.parent / "Degen-LIO-backups").exists(),
        "OLD_PRIVATE_STAGE1_FOUND": migration.get(
            "old_private_stage1_found", False
        ),
        "OLD_PRIVATE_STAGE1_MIGRATED": migration.get(
            "old_private_stage1_migrated", False
        ),
        "OLD_PRIVATE_STAGE1_REMAINS": (root / "_private_stage1").exists(),
        "LEGACY_ZIP_COUNT": len(legacy_files),
        "LEGACY_ZIP_TOTAL_SIZE": sum(path.stat().st_size for path in legacy_files),
        "PRIVATE_FILE_COUNT": count_files(root / "_private"),
        "BACKUP_FILE_COUNT": count_files(root / "_backups"),
        "PATENT_FILE_COUNT": count_files(root / "_private/patent1"),
        "PRIOR_ART_FILE_COUNT": count_files(root / "_private/patent1/prior_art"),
        "STAGE1_REPORT_COUNT": count_files(root / "reports/stage1"),
        "DAY3_REQUIRED_FILE_COUNT": len(DAY3_CORE_PATHS),
        "DAY3_MISSING_FILES": day3_missing,
        "DEDUPLICATED_FILE_COUNT": len(migration.get("deduplicated", [])),
        "CONFLICT_FILE_COUNT": len(conflicts),
        "CONFLICT_FILES": [item.get("preserved_as", "") for item in conflicts],
        "GIT_BUNDLE_PATH": str(root / bundle["path"]),
        "GIT_BUNDLE_SIZE": bundle["size_bytes"],
        "GIT_BUNDLE_SHA256": bundle["sha256"],
        "GIT_BUNDLE_VERIFY_PASS": bundle["verify_pass"],
        "PRIVATE_GIT_TRACKED_COUNT": len(private_tracked),
        "PATENT_GIT_TRACKED_COUNT": len(patent_tracked),
        "SECURITY_SCAN_PASS": not security_findings,
        "SECURITY_SCAN_FINDINGS": security_findings,
        "PYTEST_COMMAND": pytest["command"],
        "PYTEST_PASS": pytest["pass"],
        "PYTEST_PASSED_COUNT": pytest["passed_count"],
        "PYTEST_FAILED_COUNT": pytest["failed_count"],
        "PYTEST_SKIPPED_COUNT": pytest["skipped_count"],
        "PYTEST_EXIT_CODE": pytest["exit_code"],
        "CANONICAL_ZIP_PATH": str(root.parent / CANONICAL_ZIP_NAME),
        "CANONICAL_ZIP_SIZE": None,
        "CANONICAL_ZIP_SHA256": "PENDING_DETACHED_AFTER_FINALIZATION",
        "CANONICAL_ZIP_VERIFIED": False,
        "MANIFEST_ENTRY_COUNT": None,
        "PACKAGE_COMPLETE": False,
        "FINAL_STATUS": "SINGLE_ROOT_PACKAGE_INCOMPLETE",
        "SCIENTIFIC_CODE_MODIFIED": False,
        "HISTORICAL_ARTIFACTS_MODIFIED": False,
        "FORMAL_SCIENTIFIC_EXPERIMENTS_RUN": False,
        "GIT_PUSH_PERFORMED": False,
        "GENERATED_AT": now_iso(),
    }
    return report


def write_report(root: Path, report: dict[str, Any]) -> None:
    json_path = root / "_package/packaging_report.json"
    md_path = root / "_package/packaging_report.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = ["# Degen-LIO canonical packaging report", ""]
    for key, value in report.items():
        if isinstance(value, (list, dict)):
            rendered = json.dumps(value, ensure_ascii=False)
        elif isinstance(value, bool):
            rendered = str(value).lower()
        elif value is None:
            rendered = "null"
        else:
            rendered = str(value)
        lines.append(f"{key}: {rendered}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def data_size_warnings(root: Path) -> list[str]:
    warnings = []
    for name in ("data", "results"):
        directory = root / name
        if not directory.exists():
            continue
        size = sum(
            path.stat().st_size for path in directory.rglob("*") if path.is_file()
        )
        if size > 5 * 1024**3:
            warnings.append(f"{name}/ exceeds 5 GiB ({size} bytes); retained")
    return warnings


def create_zip(root: Path, temporary: Path) -> None:
    temporary.unlink(missing_ok=True)
    prefix = root.name
    with zipfile.ZipFile(
        temporary, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True
    ) as archive:
        for path in included_files(root):
            relative = path.relative_to(root).as_posix()
            archive.write(path, arcname=f"{prefix}/{relative}")
        names = set(archive.namelist())
        for relative in EMPTY_DIRS_TO_ARCHIVE:
            name = f"{prefix}/{relative.rstrip('/')}/"
            if name not in names:
                archive.writestr(name, b"")


def verify_zip(root: Path, archive_path: Path) -> dict[str, Any]:
    prefix = f"{root.name}/"
    with zipfile.ZipFile(archive_path) as archive:
        corrupt = archive.testzip()
        if corrupt:
            raise PackagingError(f"ZIP CRC verification failed: {corrupt}")
        names = set(archive.namelist())
        if any(name.startswith(f"{prefix}.git/") for name in names):
            raise PackagingError("canonical ZIP unexpectedly contains .git")
        if any(
            name.startswith(f"{prefix}_archives/legacy_packages/")
            for name in names
        ):
            raise PackagingError("canonical ZIP unexpectedly contains legacy ZIPs")

        missing = [
            path for path in REQUIRED_FILE_PATHS if f"{prefix}{path}" not in names
        ]
        missing.extend(
            path for path in REVIEW_ROOT_FILES if f"{prefix}{path}" not in names
        )
        missing.extend(
            f"review_exports/{name}"
            for name in REVIEW_EXPORT_NAMES
            if f"{prefix}review_exports/{name}" not in names
        )
        missing.extend(
            path
            for path in REQUIRED_PREFIXES
            if not any(name.startswith(f"{prefix}{path}") for name in names)
        )
        missing.extend(
            path for path in DAY3_CORE_PATHS if f"{prefix}{path}" not in names
        )

        with tempfile.TemporaryDirectory(prefix="degen-lio-package-verify-") as temp:
            destination = Path(temp)
            archive.extractall(destination)
            extracted_root = destination / root.name
            manifest_path = extracted_root / "_package/full_manifest.json"
            with manifest_path.open(encoding="utf-8") as handle:
                manifest = json.load(handle)
            hash_failures = []
            for entry in manifest["entries"]:
                if not entry["included_in_canonical_zip"] or not entry["sha256"]:
                    continue
                extracted = extracted_root / entry["relative_path"]
                if not extracted.is_file() or sha256_file(extracted) != entry["sha256"]:
                    hash_failures.append(entry["relative_path"])
            if hash_failures:
                raise PackagingError(
                    "extracted manifest verification failed:\n"
                    + "\n".join(hash_failures)
                )
            bundle_verify = run(
                [
                    "git",
                    "bundle",
                    "verify",
                    str(
                        extracted_root
                        / "_backups/git_bundles/Degen-LIO-full-history.bundle"
                    ),
                ],
                # Bundle prerequisite verification requires an existing Git
                # repository; the extracted package intentionally has no .git.
                cwd=root,
            )
    return {
        "verified": True,
        "missing_required": sorted(set(missing)),
        "bundle_verify_output": bundle_verify.stdout.strip(),
    }


def package(root: Path) -> dict[str, Any]:
    ensure_layout(root)
    assert_private_untracked(root)
    assert_review_untracked(root)
    migration = load_migration(root)
    security_findings = scan_sensitive_files(root)
    if security_findings:
        failure_report = {
            "PROJECT_ROOT": str(root),
            "SECURITY_SCAN_PASS": False,
            "SECURITY_SCAN_FINDINGS": security_findings,
            "PACKAGE_COMPLETE": False,
            "FINAL_STATUS": "SINGLE_ROOT_PACKAGE_FAIL",
            "GENERATED_AT": now_iso(),
        }
        write_report(root, failure_report)
        raise PackagingError("SECURITY_SCAN_FAIL; canonical ZIP was not created")

    bundle = update_git_bundle(root)
    current_git = git_state(root)
    write_project_state(root, current_git)
    write_package_readme(root)
    pytest_result = run_pytest(root)
    report = build_base_report(
        root,
        current_git,
        migration,
        bundle,
        pytest_result,
        security_findings,
    )
    size_warnings = data_size_warnings(root)
    report["DATA_SIZE_WARNINGS"] = size_warnings
    write_report(root, report)

    # Generate a pre-verification readable set, then scan the generated plain
    # text as part of the exact payload that will enter the ZIP.
    review = generate_review_exports(
        root,
        current_git,
        pytest_result,
        bundle,
        archive_verified=False,
        zip_sha256="PENDING_ARCHIVE_VERIFICATION",
    )
    security_findings = scan_sensitive_files(root)
    if security_findings:
        failure_report = {
            **report,
            "SECURITY_SCAN_PASS": False,
            "SECURITY_SCAN_FINDINGS": security_findings,
            "PACKAGE_COMPLETE": False,
            "FINAL_STATUS": "SINGLE_ROOT_PACKAGE_FAIL",
            "GENERATED_AT": now_iso(),
        }
        write_report(root, failure_report)
        raise PackagingError(
            "SECURITY_SCAN_FAIL after readable export; canonical ZIP was not created"
        )
    report.update(
        {
            "REVIEW_EXPORT_FILE_COUNT": review["file_count"],
            "REVIEW_MISSING_CRITICAL_FILES": review["missing"],
            "REVIEW_CONFLICT_CRITICAL_FILES": review["conflicts"],
            "PATENT_TEXT_FORMULA_COUNT": review["patent"].get("formula_count"),
            "PATENT_TEXT_PARTIAL_FORMULA_COUNT": review["patent"].get(
                "partial_formula_count"
            ),
        }
    )
    write_report(root, report)
    review = generate_review_exports(
        root,
        current_git,
        pytest_result,
        bundle,
        archive_verified=False,
        zip_sha256="PENDING_ARCHIVE_VERIFICATION",
    )

    generated_at = now_iso()
    entries = write_manifest(root, migration, generated_at)
    report["MANIFEST_ENTRY_COUNT"] = len(entries)
    write_report(root, report)
    review = generate_review_exports(
        root,
        current_git,
        pytest_result,
        bundle,
        archive_verified=False,
        zip_sha256="PENDING_ARCHIVE_VERIFICATION",
    )
    entries = write_manifest(root, migration, generated_at)

    final_zip = root.parent / CANONICAL_ZIP_NAME
    temporary_zip = final_zip.with_name(f"{final_zip.name}.tmp")
    create_zip(root, temporary_zip)
    draft_verification = verify_zip(root, temporary_zip)

    package_complete = (
        draft_verification["verified"]
        and not draft_verification["missing_required"]
        and pytest_result["pass"]
        and not security_findings
        and not private_tracked_files(root)
        and bundle["verify_pass"]
        and not review["missing"]
        and not review["conflicts"]
        and not report["EXTERNAL_PRIVATE_IP_REMAINS"]
        and not report["EXTERNAL_BACKUPS_REMAINS"]
        and not report["OLD_PRIVATE_STAGE1_REMAINS"]
    )
    warnings = bool(
        migration.get("deduplicated")
        or migration.get("conflicts")
        or size_warnings
        or "WITH_WARNINGS"
        in (root / "reports/stage1/day3_prior_art_gate_20260722.md").read_text(
            encoding="utf-8", errors="ignore"
        )
    )
    if package_complete:
        final_status = (
            "SINGLE_ROOT_PACKAGE_PASS_WITH_WARNINGS"
            if warnings
            else "SINGLE_ROOT_PACKAGE_PASS"
        )
    elif draft_verification["verified"]:
        final_status = "SINGLE_ROOT_PACKAGE_INCOMPLETE"
    else:
        final_status = "SINGLE_ROOT_PACKAGE_FAIL"

    # The verified draft proves that this exact file set is packageable. Write
    # final readable status with a detached digest marker, then build and verify
    # the final archive from that status-bearing payload.
    report.update(
        {
            "CANONICAL_ZIP_SIZE": temporary_zip.stat().st_size,
            "CANONICAL_ZIP_SHA256": "DETACHED_AFTER_FINALIZATION",
            "CANONICAL_ZIP_VERIFIED": draft_verification["verified"],
            "ZIP_MISSING_REQUIRED_FILES": draft_verification["missing_required"],
            "PACKAGE_COMPLETE": package_complete,
            "FINAL_STATUS": final_status,
            "GENERATED_AT": now_iso(),
        }
    )
    write_report(root, report)
    review = generate_review_exports(
        root,
        current_git,
        pytest_result,
        bundle,
        archive_verified=draft_verification["verified"],
        zip_sha256="DETACHED_AFTER_FINALIZATION",
    )
    write_manifest(root, migration, generated_at)
    create_zip(root, temporary_zip)
    verification = verify_zip(root, temporary_zip)
    os.replace(temporary_zip, final_zip)

    package_complete = bool(
        package_complete
        and verification["verified"]
        and not verification["missing_required"]
        and review["complete"]
    )
    final_status = (
        "SINGLE_ROOT_PACKAGE_PASS_WITH_WARNINGS"
        if package_complete and warnings
        else "SINGLE_ROOT_PACKAGE_PASS"
        if package_complete
        else "SINGLE_ROOT_PACKAGE_INCOMPLETE"
        if verification["verified"]
        else "SINGLE_ROOT_PACKAGE_FAIL"
    )
    final_digest = sha256_file(final_zip)
    report.update(
        {
            "CANONICAL_ZIP_SIZE": final_zip.stat().st_size,
            "CANONICAL_ZIP_SHA256": final_digest,
            "CANONICAL_ZIP_VERIFIED": verification["verified"],
            "ZIP_MISSING_REQUIRED_FILES": verification["missing_required"],
            "REVIEW_EXPORT_FILE_COUNT": review["file_count"],
            "REVIEW_MISSING_CRITICAL_FILES": review["missing"],
            "REVIEW_CONFLICT_CRITICAL_FILES": review["conflicts"],
            "PACKAGE_COMPLETE": package_complete,
            "FINAL_STATUS": final_status,
            "GENERATED_AT": now_iso(),
        }
    )
    # Live files receive the detached final digest after atomic replacement.
    # The archive necessarily retains DETACHED_AFTER_FINALIZATION internally.
    write_report(root, report)
    generate_review_exports(
        root,
        current_git,
        pytest_result,
        bundle,
        archive_verified=verification["verified"],
        zip_sha256=final_digest,
    )
    write_manifest(root, migration, generated_at)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--consolidate-sources",
        action="store_true",
        help="perform the one-time verified source migration before packaging",
    )
    parser.add_argument(
        "--consolidate-only",
        action="store_true",
        help="perform migration but do not build the canonical ZIP",
    )
    args = parser.parse_args()
    if args.consolidate_only and not args.consolidate_sources:
        parser.error("--consolidate-only requires --consolidate-sources")

    try:
        root = project_root_from_script()
        if args.consolidate_sources:
            migration = consolidate_sources(root)
            print(json.dumps(migration.to_dict(), ensure_ascii=False, indent=2))
        if not args.consolidate_only:
            report = package(root)
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except PackagingError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
