#!/usr/bin/env python3
"""Consolidate private material and build the canonical Degen-LIO package.

The default mode is repeatable: it refreshes the full-history Git bundle,
project state, integrity inventories, pytest result, and the canonical ZIP.
The optional ``--consolidate-sources`` mode performs the one-time, verified
migration from the legacy external/private locations before packaging.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
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
            if relative.parts[0] in {"_package", "_backups"}
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

    generated_at = now_iso()
    entries = write_manifest(root, migration, generated_at)
    report["MANIFEST_ENTRY_COUNT"] = len(entries)
    write_report(root, report)
    entries = write_manifest(root, migration, generated_at)

    final_zip = root.parent / CANONICAL_ZIP_NAME
    temporary_zip = final_zip.with_name(f"{final_zip.name}.tmp")
    create_zip(root, temporary_zip)
    verification = verify_zip(root, temporary_zip)
    os.replace(temporary_zip, final_zip)

    package_complete = (
        verification["verified"]
        and not verification["missing_required"]
        and pytest_result["pass"]
        and not security_findings
        and not private_tracked_files(root)
        and bundle["verify_pass"]
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
    elif verification["verified"]:
        final_status = "SINGLE_ROOT_PACKAGE_INCOMPLETE"
    else:
        final_status = "SINGLE_ROOT_PACKAGE_FAIL"

    report.update(
        {
            "CANONICAL_ZIP_SIZE": final_zip.stat().st_size,
            "CANONICAL_ZIP_SHA256": sha256_file(final_zip),
            "CANONICAL_ZIP_VERIFIED": verification["verified"],
            "ZIP_MISSING_REQUIRED_FILES": verification["missing_required"],
            "PACKAGE_COMPLETE": package_complete,
            "FINAL_STATUS": final_status,
            "GENERATED_AT": now_iso(),
        }
    )
    # The live report records the detached final archive digest. The archived
    # report necessarily contains the pre-finalization marker; see README_PACKAGE.
    write_report(root, report)
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
