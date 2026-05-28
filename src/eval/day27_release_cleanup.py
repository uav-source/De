"""Day 27 README/release cleanup audit and figure/table readiness."""

from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]

README_FIELDNAMES = ["check_id", "required_phrase", "found", "status", "reason"]
FORBIDDEN_CLAIM_FIELDNAMES = ["claim_id", "forbidden_phrase", "found", "status", "location", "reason"]
FORBIDDEN_PATH_FIELDNAMES = ["path_pattern", "found_paths", "found_count", "release_action", "blocking_for_release", "reason"]
FILE_POLICY_FIELDNAMES = ["path_or_pattern", "policy", "include_in_release", "reason"]
ARCHIVE_FIELDNAMES = ["archive_step", "command_or_action", "safe", "requires_manual_confirmation", "reason"]
FIGURE_READINESS_FIELDNAMES = ["item_id", "source_artifact", "output_target", "readiness_status", "next_action", "must_not_claim"]
RECOMMENDATION_FIELDNAMES = ["recommended_day", "recommended_route", "task", "allowed", "reason", "blocking_condition"]


def load_day27_inputs(repo_root: Path, day30_root: Path, reports_root: Path, readme_path: Path) -> Dict[str, Any]:
    """Load Day 24-26 inputs and README for release cleanup auditing."""

    paths = {
        "readme": readme_path,
        "day24_manifest": day30_root / "manifests/day24_diagnostic_consolidation_manifest.json",
        "day24_report": reports_root / "day24_diagnostic_consolidation_report.md",
        "day25_manifest": day30_root / "manifests/day25_paper_outline_manifest.json",
        "day25_report": reports_root / "day25_paper_outline_report.md",
        "day26_manifest": day30_root / "manifests/day26_paper_skeleton_manifest.json",
        "day26_report": reports_root / "day26_paper_skeleton_report.md",
        "day26_figure_plan": day30_root / "tables/day26_figure_table_execution_plan.csv",
        "day26_readme_plan": day30_root / "tables/day26_readme_scope_update_plan.csv",
        "day26_release_plan": day30_root / "tables/day26_release_cleanup_plan.csv",
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing required Day27 input file(s): "
            + "; ".join(missing)
            + ". Run Day 24-26 scripts before Day 27 release cleanup."
        )
    artifacts: Dict[str, Any] = {"paths": paths, "input_paths": list(paths.values()), "repo_root": repo_root}
    for key, path in paths.items():
        if path.suffix == ".json":
            artifacts[key] = json.loads(path.read_text(encoding="utf-8"))
        elif path.suffix == ".csv":
            artifacts[key] = read_csv_rows(path)
        else:
            artifacts[key] = path.read_text(encoding="utf-8")
    return artifacts


def audit_readme_scope(readme_text: str, required_phrases: Sequence[str]) -> List[Dict[str, str]]:
    rows = []
    lower = readme_text.lower()
    for index, phrase in enumerate(required_phrases, start=1):
        found = phrase.lower() in lower
        rows.append(
            {
                "check_id": f"READ{index:02d}",
                "required_phrase": phrase,
                "found": str(found).lower(),
                "status": "pass" if found else "fail",
                "reason": "required README scope phrase found" if found else "required README scope phrase missing",
            }
        )
    return rows


def audit_forbidden_claims(readme_text: str, forbidden_phrases: Sequence[str]) -> List[Dict[str, str]]:
    rows = []
    for index, phrase in enumerate(forbidden_phrases, start=1):
        locations = find_forbidden_locations(readme_text, phrase)
        rows.append(
            {
                "claim_id": f"FC{index:02d}",
                "forbidden_phrase": phrase,
                "found": str(bool(locations)).lower(),
                "status": "fail" if locations else "pass",
                "location": ";".join(locations) if locations else "none",
                "reason": "forbidden claim phrase appears without negating context" if locations else "not present as an affirmative forbidden claim",
            }
        )
    return rows


def audit_release_forbidden_paths(repo_root: Path, forbidden_paths: Sequence[str]) -> List[Dict[str, str]]:
    rows = []
    for pattern in forbidden_paths:
        found = find_paths(repo_root, pattern)
        rows.append(
            {
                "path_pattern": pattern,
                "found_paths": ";".join(relative_to_root(path) for path in found[:20]) if found else "none",
                "found_count": str(len(found)),
                "release_action": "exclude from release archive",
                "blocking_for_release": "true",
                "reason": "may exist in checkout but must not enter release archive",
            }
        )
    return rows


def build_release_file_policy() -> List[Dict[str, str]]:
    return [
        policy_row("src/", "include source code", True, "core executable modules"),
        policy_row("configs/", "include configs", True, "reproducible protocols and validation settings"),
        policy_row("scripts/", "include scripts", True, "reproduction and analysis entry points"),
        policy_row("tests/", "include tests", True, "artifact quality and scope guardrails"),
        policy_row("docs/paper/", "include paper planning docs", True, "paper skeleton and figure/table plans"),
        policy_row("docs/release/", "include release docs", True, "release scope, cleanup policy, and commands"),
        policy_row("reports/", "include curated reports", True, "human-readable evidence summaries"),
        policy_row("results/day30/tables/", "include selected key CSV tables", True, "Day15-Day27 evidence tables"),
        policy_row("results/day30/manifests/", "include selected manifests", True, "provenance and status tracking"),
        policy_row("results/day14/manifests/", "include required Day14 manifests", True, "reproduction provenance"),
        policy_row("results/day14/figures/", "document smoke vs real figures", True, "figures are useful but must record smoke/real mode"),
        policy_row("results/day14/raw/*.tum", "rebuild or explicitly document if packaged", False, "raw trajectories are generated artifacts"),
        policy_row(".git", "exclude", False, "repository internals do not belong in release archive"),
        policy_row(".pytest_cache", "exclude", False, "test cache is not evidence"),
        policy_row("__pycache__", "exclude", False, "bytecode cache is not evidence"),
    ]


def build_safe_archive_plan() -> List[Dict[str, str]]:
    return [
        archive_row("ARCH01", "run python3 scripts/check_env.py", True, False, "confirm environment and commit provenance"),
        archive_row("ARCH02", "run python3 -m pytest -q", True, False, "full pytest must pass before packaging"),
        archive_row("ARCH03", "run python3 scripts/20_day27_release_cleanup.py --config configs/validation/day27_release_cleanup.yaml", True, False, "refresh release audit tables"),
        archive_row("ARCH04", "git archive --format=tar.gz --output degen_lio_diagnostic_release.tar.gz HEAD", True, True, "safe archive excludes .git by construction but requires manual review"),
        archive_row("ARCH05", "rsync -a --exclude .git --exclude .pytest_cache --exclude __pycache__ ./ release_dir/", True, True, "alternative archive staging with explicit excludes"),
        archive_row("ARCH06", "do not delete local .git/.pytest_cache/__pycache__ during planning", True, False, "Day27 is an audit and plan, not destructive cleanup"),
    ]


def build_figure_table_generation_readiness(figure_plan: Sequence[Mapping[str, str]]) -> List[Dict[str, str]]:
    rows = []
    for row in figure_plan:
        status = row.get("generation_status", "")
        if status == "source_available":
            readiness = "ready_for_conversion"
            action = "convert source CSV/table into paper table; keep claim boundary wording"
        else:
            readiness = "pending"
            action = "write explicit generation script or keep as planned placeholder; do not fake a rendered figure"
        rows.append(
            {
                "item_id": row["item_id"],
                "source_artifact": row["source_artifact"],
                "output_target": row["output_target"],
                "readiness_status": readiness,
                "next_action": action,
                "must_not_claim": row["must_not_claim"],
            }
        )
    return rows


def derive_day28_recommendation() -> List[Dict[str, str]]:
    return [
        {
            "recommended_day": "Day 28",
            "recommended_route": "figure/table generation scripts",
            "task": "implement safe conversion scripts for source_available tables and explicit pending placeholders for figures",
            "allowed": "true",
            "reason": "Day27 identifies table-ready and pending figure items",
            "blocking_condition": "must not fake generated figures",
        },
        {
            "recommended_day": "Day 28",
            "recommended_route": "paper section drafting",
            "task": "expand paper skeleton sections using claim boundary language",
            "allowed": "true",
            "reason": "README/release scope is now explicit",
            "blocking_condition": "must preserve forbidden claim boundaries",
        },
        {
            "recommended_day": "Day 28",
            "recommended_route": "weak-subspace update implementation",
            "task": "implement estimator update",
            "allowed": "false",
            "reason": "method update remains unauthorized",
            "blocking_condition": "requires future method_update_authorized=true",
        },
    ]


def write_day27_manifest(
    path: Path,
    *,
    inputs: Sequence[Path],
    outputs: Sequence[Path],
    readme_audit: Sequence[Mapping[str, str]],
    forbidden_audit: Sequence[Mapping[str, str]],
    path_audit: Sequence[Mapping[str, str]],
    archive_plan: Sequence[Mapping[str, str]],
    figure_readiness: Sequence[Mapping[str, str]],
    artifacts: Mapping[str, Any],
    runtime_seconds: float,
) -> Dict[str, Any]:
    missing = [relative_to_root(output) for output in outputs if output != path and not output.exists()]
    readme_scope_passed = all(row["status"] == "pass" for row in readme_audit)
    forbidden_claims_passed = all(row["status"] == "pass" for row in forbidden_audit)
    method_update_authorized = bool(artifacts["day26_manifest"].get("method_update_authorized", False))
    weak_update_authorized = bool(artifacts["day26_manifest"].get("weak_update_authorized", False))
    manifest = {
        "status": "OK" if not missing and readme_scope_passed and forbidden_claims_passed else "FAILED",
        "git_commit": git_commit(),
        "inputs": [relative_to_root(path) for path in inputs],
        "outputs": [relative_to_root(path) for path in outputs],
        "readme_scope_passed": bool(readme_scope_passed),
        "forbidden_claims_passed": bool(forbidden_claims_passed),
        "release_forbidden_paths_audited": bool(path_audit),
        "safe_archive_plan_created": bool(archive_plan),
        "figure_table_readiness_created": bool(figure_readiness),
        "method_update_authorized": method_update_authorized,
        "weak_update_authorized": weak_update_authorized,
        "missing_artifacts": missing,
        "runtime_seconds": round(float(runtime_seconds), 6),
        "interpretation": "README/release cleanup audit for diagnostic benchmark route; no destructive cleanup or method update",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def find_forbidden_locations(text: str, phrase: str) -> List[str]:
    needle = phrase.lower()
    locations = []
    offset = 0
    for line_no, line in enumerate(text.splitlines(), start=1):
        lower = line.lower()
        start = 0
        while True:
            index = lower.find(needle, start)
            if index < 0:
                break
            prefix = lower[max(0, index - 40): index]
            if not is_negated_context(prefix):
                locations.append(f"line:{line_no}:char:{offset + index}")
            start = index + len(needle)
        offset += len(line) + 1
    return locations


def is_negated_context(context: str) -> bool:
    negations = ["not a ", "not ", "does not ", "do not ", "no ", "is not ", "remains unauthorized", "not validated"]
    return any(token in context for token in negations)


def find_paths(repo_root: Path, pattern: str) -> List[Path]:
    if pattern == ".git":
        path = repo_root / ".git"
        return [path] if path.exists() else []
    matches = [path for path in repo_root.rglob(pattern) if path.exists()]
    return sorted(matches)


def policy_row(path, policy, include, reason):
    return {
        "path_or_pattern": path,
        "policy": policy,
        "include_in_release": str(bool(include)).lower(),
        "reason": reason,
    }


def archive_row(step, action, safe, manual, reason):
    return {
        "archive_step": step,
        "command_or_action": action,
        "safe": str(bool(safe)).lower(),
        "requires_manual_confirmation": str(bool(manual)).lower(),
        "reason": reason,
    }


def write_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def relative_to_root(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)
