#!/usr/bin/env python3
"""Run Day 30 final package review and release-readiness audit."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict, Sequence

import yaml


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eval.day30_final_package_review import (  # noqa: E402
    ARCHIVE_FIELDNAMES,
    CLAIM_AUDIT_FIELDNAMES,
    FIGURE_TABLE_FIELDNAMES,
    FINAL_DECISION_FIELDNAMES,
    RELEASE_CHECK_FIELDNAMES,
    REQUIRED_ARTIFACT_FIELDNAMES,
    audit_figures_and_tables,
    audit_global_claim_boundaries,
    audit_release_readiness,
    audit_required_artifacts,
    build_clean_archive_plan,
    derive_final_decision,
    load_day14_to_day29_artifacts,
    write_csv,
    write_day30_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/validation/day30_final_package_review.yaml")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--day14-root", type=Path, default=ROOT / "results/day14")
    parser.add_argument("--out-root", type=Path, default=ROOT / "results/day30")
    parser.add_argument("--reports-root", type=Path, default=ROOT / "reports")
    parser.add_argument("--docs-root", type=Path, default=ROOT / "docs")
    parser.add_argument("--report", type=Path, default=ROOT / "reports/day30_final_package_review.md")
    parser.add_argument("--release-notes", type=Path, default=ROOT / "docs/release/day30_final_release_notes.md")
    return parser.parse_args()


def main() -> int:
    start = time.time()
    args = parse_args()
    try:
        config = load_config(args.config)
        artifacts = load_day14_to_day29_artifacts(args.day14_root, args.out_root, args.reports_root, args.docs_root, args.repo_root)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    required_rows = audit_required_artifacts(args.repo_root, args.day14_root, args.out_root, args.reports_root)
    figure_rows = audit_figures_and_tables(args.repo_root)
    archive_rows = build_clean_archive_plan()
    final_rows_pre = derive_final_decision(required_rows, figure_rows, [])
    args.release_notes.parent.mkdir(parents=True, exist_ok=True)
    args.release_notes.write_text(build_release_notes(final_rows_pre), encoding="utf-8")

    claim_rows = audit_global_claim_boundaries(args.repo_root)
    release_rows = audit_release_readiness(str(artifacts.get("readme") or ""), required_rows, figure_rows, claim_rows)
    final_rows = derive_final_decision(required_rows, figure_rows, claim_rows)

    table_dir = args.out_root / "tables"
    manifest_dir = args.out_root / "manifests"
    required_path = table_dir / "day30_required_artifact_audit.csv"
    figure_path = table_dir / "day30_figure_table_final_audit.csv"
    claim_path = table_dir / "day30_global_claim_boundary_audit.csv"
    release_path = table_dir / "day30_release_readiness_checklist.csv"
    archive_path = table_dir / "day30_clean_archive_plan.csv"
    decision_path = table_dir / "day30_final_decision.csv"
    manifest_path = manifest_dir / "day30_final_package_manifest.json"

    write_csv(required_path, REQUIRED_ARTIFACT_FIELDNAMES, required_rows)
    write_csv(figure_path, FIGURE_TABLE_FIELDNAMES, figure_rows)
    write_csv(claim_path, CLAIM_AUDIT_FIELDNAMES, claim_rows)
    write_csv(release_path, RELEASE_CHECK_FIELDNAMES, release_rows)
    write_csv(archive_path, ARCHIVE_FIELDNAMES, archive_rows)
    write_csv(decision_path, FINAL_DECISION_FIELDNAMES, final_rows)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(build_report(required_rows, figure_rows, claim_rows, release_rows, final_rows), encoding="utf-8")

    outputs = [
        required_path,
        figure_path,
        claim_path,
        release_path,
        archive_path,
        decision_path,
        manifest_path,
        args.report,
        args.release_notes,
    ]
    manifest = write_day30_manifest(
        manifest_path,
        inputs=artifacts["input_paths"] + [args.config],
        outputs=outputs,
        required_rows=required_rows,
        figure_rows=figure_rows,
        claim_rows=claim_rows,
        release_rows=release_rows,
        final_rows=final_rows,
        runtime_seconds=time.time() - start,
    )

    print(f"day30 required artifact audit: {display_path(required_path)}")
    print(f"day30 figure/table final audit: {display_path(figure_path)}")
    print(f"day30 global claim boundary audit: {display_path(claim_path)}")
    print(f"day30 release readiness checklist: {display_path(release_path)}")
    print(f"day30 clean archive plan: {display_path(archive_path)}")
    print(f"day30 final decision: {display_path(decision_path)}")
    print(f"day30 manifest: {display_path(manifest_path)}")
    print(f"day30 report: {display_path(args.report)}")
    print(f"day30 release notes: {display_path(args.release_notes)}")
    print(f"status: {manifest['status']}")
    return 0 if manifest["status"] in {"OK", "CONDITIONAL_OK"} else 1


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"Day30 config must be a mapping: {path}")
    return config


def build_report(
    required_rows: Sequence[Dict[str, str]],
    figure_rows: Sequence[Dict[str, str]],
    claim_rows: Sequence[Dict[str, str]],
    release_rows: Sequence[Dict[str, str]],
    final_rows: Sequence[Dict[str, str]],
) -> str:
    required_failed = [row for row in required_rows if row["status"] != "pass"]
    figures_ok = all(row["status"] == "pass" for row in figure_rows)
    claim_ok = all(row["status"] != "fail" for row in claim_rows)
    manual = [row["check_item"] for row in release_rows if row["status"] == "manual_required"]
    diagnostic_status = next(row["status"] for row in final_rows if row["decision_item"] == "diagnostic benchmark package ready")
    return f"""# Day 30 Final Package Review

## Direct Answers

- Day 30 是否完成 final package review？Yes. Required artifact, figure/table, claim-boundary, release-readiness, archive-plan, and final-decision audits were generated.
- 当前是否是 diagnostic benchmark / failure-analysis package？Yes. Final package status is `{diagnostic_status}` for the diagnostic benchmark / failure-analysis route.
- 当前是否是 validated Degen-LIO estimator method？No. The project is not a validated Degen-LIO estimator method.
- F01 / F03 是否为真实图？{'Yes' if figures_ok else 'No'}.
- generated tables 是否齐全？{'Yes' if figures_ok else 'No'}.
- forbidden claims 是否被控制住？{'Yes' if claim_ok else 'No'}.
- release archive 是否已经准备好？Conditional/manual only. Manual checks still required: {', '.join(manual) if manual else 'none'}.
- full pytest 是否已确认？The external command must be checked manually before release; this script records it as manual_required.
- 是否允许进入 weak-subspace update？No.
- Day 30 最终结论是什么？Proceed only as a diagnostic benchmark paper/release draft with manual release checks.

## Audit Summary

- Required artifact failures: {len(required_failed)}.
- Figure/table audit passed: {figures_ok}.
- Global claim-boundary audit passed: {claim_ok}.
- Release readiness contains manual checks: {bool(manual)}.

## Conclusion

Day 30 completes the final package review for the diagnostic benchmark / failure-analysis route.
The project is not a validated Degen-LIO estimator method.
Weak-subspace update remains unauthorized.
ODI robust drift prediction remains unvalidated.
The package may proceed as a diagnostic benchmark paper/release draft only if manual release checks, including full local pytest and clean archive dry-run, are completed.
"""


def build_release_notes(final_rows: Sequence[Dict[str, str]]) -> str:
    diagnostic = next((row for row in final_rows if row["decision_item"] == "diagnostic benchmark package ready"), None)
    diagnostic_status = diagnostic["status"] if diagnostic else "conditional"
    return f"""# Day 30 Final Release Notes

## Scope

This release candidate is scoped as a diagnostic benchmark / failure-analysis package for LiDAR-Inertial degeneracy analysis.
It is not a validated Degen-LIO estimator method.

## Allowed Claims

- The repository provides a reproducible synthetic diagnostic benchmark package.
- The package documents legacy bias, unbiased toy-probe protocols, metric-validity stress tests, and No-Go gate evidence.
- F01 and F03 are generated from source artifacts, not placeholders.

## Forbidden Claims

- Do not claim a validated Degen-LIO estimator method.
- Do not claim weak-subspace update authorization.
- Do not claim robust ODI drift prediction.
- Do not claim toy_lio is a real LIO estimator.

## Reproduction Commands

For full staged reproduction, run the Day15-Day30 scripts listed in README.
The short command block below is only a final audit shortcut, not the full chain.

```bash
python3 scripts/check_env.py
python3 -m pytest -q
bash scripts/reproduce_day14.sh --run
python3 scripts/22_day29_safe_figures.py --config configs/validation/day29_safe_figures.yaml
python3 scripts/23_day30_final_package_review.py --config configs/validation/day30_final_package_review.yaml
```

## Included Artifacts

- Source code, configs, scripts, tests, README, docs, reports, selected results/day30 tables and manifests.
- Paper skeleton, generated tables, real F01/F03 figures, caption banks, and release docs.

## Excluded Paths

- `.git`
- `.pytest_cache`
- `__pycache__`
- other local caches or temporary build products.

## Manual Checks Before Release

- Run full local pytest and confirm success.
- Perform a clean archive dry-run with `git archive` or an `rsync --exclude` staging directory.
- Inspect the archive contents before sharing.

## Known Limitations

- Diagnostic package status: {diagnostic_status}.
- Synthetic-only evidence remains a limitation.
- The method update gate remains closed.
- ODI robust drift prediction remains unvalidated.
"""


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


if __name__ == "__main__":
    raise SystemExit(main())
