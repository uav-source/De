#!/usr/bin/env python3
"""Day 31 final cleanup audit for README/release synchronization."""

from __future__ import annotations

import csv
import json
import subprocess
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


ROOT = Path(__file__).resolve().parents[1]

README_SYNC_FIELDNAMES = ["check_id", "check_item", "expected", "observed", "status", "reason"]
DRYRUN_FIELDNAMES = ["check_id", "check_item", "path", "status", "blocking", "reason"]

FORBIDDEN_PHRASES = [
    "ODI robustly predicts drift",
    "validated Degen-LIO estimator",
    "Degen-LIO estimator method is validated",
    "weak-subspace update is authorized",
    "toy_lio is real LIO",
]


def main() -> int:
    start = time.time()
    readme = ROOT / "README.md"
    release_notes = ROOT / "docs/release/day30_final_release_notes.md"
    checklist = ROOT / "docs/release/day31_release_dryrun_checklist.md"
    dryrun_script = ROOT / "scripts/release_dryrun.sh"
    day30_manifest = ROOT / "results/day30/manifests/day30_final_package_manifest.json"
    report_path = ROOT / "reports/day31_final_cleanup_report.md"
    table_dir = ROOT / "results/day30/tables"
    manifest_path = ROOT / "results/day30/manifests/day31_final_cleanup_manifest.json"

    readme_text = readme.read_text(encoding="utf-8") if readme.exists() else ""
    release_text = release_notes.read_text(encoding="utf-8") if release_notes.exists() else ""
    checklist_text = checklist.read_text(encoding="utf-8") if checklist.exists() else ""
    dryrun_text = dryrun_script.read_text(encoding="utf-8") if dryrun_script.exists() else ""
    day30 = json.loads(day30_manifest.read_text(encoding="utf-8")) if day30_manifest.exists() else {}

    readme_rows = build_readme_release_sync_audit(readme_text, release_text, checklist, dryrun_script)
    dryrun_rows = build_release_dryrun_audit(checklist, checklist_text, dryrun_script, dryrun_text, day30)

    readme_path = table_dir / "day31_readme_release_sync_audit.csv"
    dryrun_path = table_dir / "day31_release_dryrun_audit.csv"
    write_csv(readme_path, README_SYNC_FIELDNAMES, readme_rows)
    write_csv(dryrun_path, DRYRUN_FIELDNAMES, dryrun_rows)

    method_update_authorized = bool(day30.get("method_update_authorized", False))
    weak_update_authorized = bool(day30.get("weak_update_authorized", False))
    missing = [
        relative(path)
        for path in [readme, release_notes, checklist, dryrun_script, day30_manifest, readme_path, dryrun_path, report_path]
        if path != report_path and not path.exists()
    ]
    readme_sync_passed = all(row["status"] == "pass" for row in readme_rows)
    dryrun_passed = all(row["status"] in {"pass", "manual_required"} for row in dryrun_rows)
    forbidden_passed = not any(row["status"] == "fail" for row in readme_rows + dryrun_rows)
    status = "OK" if not missing and readme_sync_passed and dryrun_passed and forbidden_passed else "FAILED"
    if status == "OK" and any(row["status"] == "manual_required" for row in dryrun_rows):
        status = "CONDITIONAL_OK"

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(build_report(status, readme_sync_passed, dryrun_passed, method_update_authorized, weak_update_authorized), encoding="utf-8")

    outputs = [readme_path, dryrun_path, manifest_path, report_path]
    missing = [relative(path) for path in outputs if path != manifest_path and not path.exists()]
    manifest = {
        "status": "FAILED" if missing else status,
        "git_commit": git_commit(),
        "inputs": [relative(path) for path in [readme, release_notes, checklist, dryrun_script, day30_manifest]],
        "outputs": [relative(path) for path in outputs],
        "readme_release_sync_passed": bool(readme_sync_passed),
        "release_dryrun_audit_passed": bool(dryrun_passed),
        "forbidden_claims_passed": bool(forbidden_passed),
        "method_update_authorized": bool(method_update_authorized),
        "weak_update_authorized": bool(weak_update_authorized),
        "full_pytest_manual_required": True,
        "clean_archive_dryrun_manual_required": True,
        "missing_artifacts": missing,
        "runtime_seconds": round(time.time() - start, 6),
        "interpretation": "Day31 README/release synchronization and dry-run planning; no method update authorized",
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"day31 readme/release sync audit: {relative(readme_path)}")
    print(f"day31 release dry-run audit: {relative(dryrun_path)}")
    print(f"day31 manifest: {relative(manifest_path)}")
    print(f"day31 report: {relative(report_path)}")
    print(f"status: {manifest['status']}")
    return 0 if manifest["status"] in {"OK", "CONDITIONAL_OK"} else 1


def build_readme_release_sync_audit(readme_text: str, release_text: str, checklist: Path, dryrun_script: Path) -> List[Dict[str, str]]:
    checks = [
        ("READ31-01", "README evidence chain", "Evidence Chain Day14-Day30", "Evidence Chain Day14-Day30" in readme_text, "README must summarize through Day30"),
        ("READ31-02", "README Day28 bullet", "Day 28: paper-draft table conversion and pending figure planning.", "Day 28: paper-draft table conversion and pending figure planning." in readme_text, "Day28 result must be visible"),
        ("READ31-03", "README Day29 bullet", "Day 29: real F01/F03 figure generation and table interpretation safeguards.", "Day 29: real F01/F03 figure generation and table interpretation safeguards." in readme_text, "Day29 result must be visible"),
        ("READ31-04", "README Day30 bullet", "Day 30: final package review, artifact audit, claim-boundary audit, and release readiness check.", "Day 30: final package review, artifact audit, claim-boundary audit, and release readiness check." in readme_text, "Day30 result must be visible"),
        ("READ31-05", "README Day28 command", "python3 scripts/21_day28_figure_table_generation.py --config configs/validation/day28_figure_table_generation.yaml", "python3 scripts/21_day28_figure_table_generation.py --config configs/validation/day28_figure_table_generation.yaml" in readme_text, "Day28 command required"),
        ("READ31-06", "README Day29 command", "python3 scripts/22_day29_safe_figures.py --config configs/validation/day29_safe_figures.yaml", "python3 scripts/22_day29_safe_figures.py --config configs/validation/day29_safe_figures.yaml" in readme_text, "Day29 command required"),
        ("READ31-07", "README Day30 command", "python3 scripts/23_day30_final_package_review.py --config configs/validation/day30_final_package_review.yaml", "python3 scripts/23_day30_final_package_review.py --config configs/validation/day30_final_package_review.yaml" in readme_text, "Day30 command required"),
        ("REL31-01", "release notes staged reproduction", "For full staged reproduction, run the Day15-Day30 scripts listed in README.", "For full staged reproduction, run the Day15-Day30 scripts listed in README." in release_text, "release notes must distinguish shortcut from full chain"),
        ("REL31-02", "release notes shortcut caveat", "The short command block below is only a final audit shortcut, not the full chain.", "The short command block below is only a final audit shortcut, not the full chain." in release_text, "release notes must prevent shortcut overclaiming"),
        ("REL31-03", "dry-run checklist exists", str(checklist), checklist.exists() and checklist.stat().st_size > 0, "Day31 checklist required"),
        ("REL31-04", "release dry-run helper exists", str(dryrun_script), dryrun_script.exists() and dryrun_script.stat().st_size > 0, "Day31 helper required"),
    ]
    rows = []
    for check_id, item, expected, found, reason in checks:
        rows.append(
            {
                "check_id": check_id,
                "check_item": item,
                "expected": expected,
                "observed": str(bool(found)).lower(),
                "status": "pass" if found else "fail",
                "reason": reason if found else f"missing: {reason}",
            }
        )
    rows.extend(forbidden_claim_rows(readme_text + "\n" + release_text, source="README/release notes"))
    return rows


def build_release_dryrun_audit(checklist: Path, checklist_text: str, dryrun_script: Path, dryrun_text: str, day30: Dict[str, object]) -> List[Dict[str, str]]:
    rows = [
        dry_row("DRY31-01", "release dry-run checklist exists", checklist, "pass" if checklist.exists() and checklist.stat().st_size > 0 else "fail", True, "checklist must exist"),
        dry_row("DRY31-02", "full pytest command documented", checklist, "pass" if "python3 -m pytest -q" in checklist_text else "fail", True, "full local pytest remains a manual gate"),
        dry_row("DRY31-03", "clean archive dry-run command documented", checklist, "pass" if "scripts/release_dryrun.sh" in checklist_text else "fail", True, "dry-run command must be documented"),
        dry_row("DRY31-04", "excluded paths documented", checklist, "pass" if all(token in checklist_text for token in [".git", ".pytest_cache", "__pycache__"]) else "fail", True, "cache/repository internals must be excluded"),
        dry_row("DRY31-05", "release helper exists", dryrun_script, "pass" if dryrun_script.exists() and dryrun_script.stat().st_size > 0 else "fail", True, "release helper must exist"),
        dry_row("DRY31-06", "release helper excludes forbidden paths", dryrun_script, "pass" if all(token in dryrun_text for token in [".git", ".pytest_cache", "__pycache__"]) else "fail", True, "script must use explicit excludes"),
        dry_row("DRY31-07", "release helper requires pytest confirmation", dryrun_script, "pass" if "CONFIRM_PYTEST_PASSED" in dryrun_text else "fail", True, "script must require pytest confirmation before execute mode"),
        dry_row("DRY31-08", "release helper does not run destructive deletion", dryrun_script, "pass" if not has_destructive_delete_command(dryrun_text) else "fail", True, "script must not delete user files"),
        dry_row("DRY31-09", "method update authorization remains false", Path("results/day30/manifests/day30_final_package_manifest.json"), "pass" if day30.get("method_update_authorized") is False else "fail", True, "Day30 gate must remain closed"),
        dry_row("DRY31-10", "weak update authorization remains false", Path("results/day30/manifests/day30_final_package_manifest.json"), "pass" if day30.get("weak_update_authorized") is False else "fail", True, "weak-subspace update remains unauthorized"),
        dry_row("DRY31-11", "full pytest release pass remains manual", checklist, "manual_required", True, "script cannot prove the user's latest local pytest run"),
        dry_row("DRY31-12", "clean archive inspection remains manual", checklist, "manual_required", True, "archive contents require human inspection"),
    ]
    rows.extend(forbidden_claim_rows(checklist_text + "\n" + dryrun_text, source="dry-run docs/script", fieldnames=DRYRUN_FIELDNAMES))
    return rows


def forbidden_claim_rows(text: str, *, source: str, fieldnames: Sequence[str] = README_SYNC_FIELDNAMES) -> List[Dict[str, str]]:
    rows = []
    for index, phrase in enumerate(FORBIDDEN_PHRASES, start=1):
        positive = appears_as_positive_assertion(text, phrase)
        if list(fieldnames) == README_SYNC_FIELDNAMES:
            rows.append(
                {
                    "check_id": f"CLAIM31-{index:02d}",
                    "check_item": f"forbidden claim audit: {phrase}",
                    "expected": "not present as positive assertion",
                    "observed": "positive assertion found" if positive else "boundary/negated/absent",
                    "status": "fail" if positive else "pass",
                    "reason": f"{source}: forbidden claim boundary check",
                }
            )
        else:
            rows.append(
                {
                    "check_id": f"CLAIM31-{index:02d}",
                    "check_item": f"forbidden claim audit: {phrase}",
                    "path": source,
                    "status": "fail" if positive else "pass",
                    "blocking": "true",
                    "reason": "positive forbidden claim found" if positive else "forbidden wording absent or bounded",
                }
            )
    return rows


def appears_as_positive_assertion(text: str, phrase: str) -> bool:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if phrase.lower() not in line.lower():
            continue
        context = "\n".join(lines[max(0, index - 3): index + 1]).lower()
        if any(token in context for token in ["forbidden", "do not", "not ", "not a ", "not an ", "unvalidated", "unauthorized", "must not"]):
            continue
        return True
    return False


def has_destructive_delete_command(script_text: str) -> bool:
    for raw_line in script_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("rm ") or line.startswith("rm\t") or line.startswith("find ") and " -delete" in line:
            return True
    return False


def dry_row(check_id: str, item: str, path: Path, status: str, blocking: bool, reason: str) -> Dict[str, str]:
    return {
        "check_id": check_id,
        "check_item": item,
        "path": relative(path),
        "status": status,
        "blocking": str(bool(blocking)).lower(),
        "reason": reason,
    }


def build_report(status: str, readme_sync_passed: bool, dryrun_passed: bool, method_update: bool, weak_update: bool) -> str:
    return f"""# Day 31 Final Cleanup / Release Dry-Run Audit

## Direct Answers

- README Day14-Day30 sync passed: {readme_sync_passed}.
- Release dry-run audit passed: {dryrun_passed}.
- Method update authorized: {method_update}.
- Weak update authorized: {weak_update}.
- Final cleanup status: {status}.

## Release Gate

Full local pytest and clean archive dry-run are still manual release gates. Day31 records the commands and safe dry-run policy; it does not mark a public release as complete.

## Conclusion

The repository remains a diagnostic benchmark / failure-analysis package, not a validated Degen-LIO estimator method.
Weak-subspace update remains unauthorized.
Full local pytest and clean archive dry-run are required before public release.
"""


def write_csv(path: Path, fieldnames: Sequence[str], rows: Sequence[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except (OSError, ValueError):
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
