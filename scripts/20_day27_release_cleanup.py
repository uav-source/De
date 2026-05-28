#!/usr/bin/env python3
"""Run Day 27 README/release cleanup audit."""

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

from eval.day27_release_cleanup import (  # noqa: E402
    ARCHIVE_FIELDNAMES,
    FIGURE_READINESS_FIELDNAMES,
    FILE_POLICY_FIELDNAMES,
    FORBIDDEN_CLAIM_FIELDNAMES,
    FORBIDDEN_PATH_FIELDNAMES,
    README_FIELDNAMES,
    RECOMMENDATION_FIELDNAMES,
    audit_forbidden_claims,
    audit_readme_scope,
    audit_release_forbidden_paths,
    build_figure_table_generation_readiness,
    build_release_file_policy,
    build_safe_archive_plan,
    derive_day28_recommendation,
    load_day27_inputs,
    write_csv,
    write_day27_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/validation/day27_release_cleanup.yaml")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--out-root", type=Path, default=ROOT / "results/day30")
    parser.add_argument("--reports-root", type=Path, default=ROOT / "reports")
    parser.add_argument("--readme", type=Path, default=ROOT / "README.md")
    parser.add_argument("--report", type=Path, default=ROOT / "reports/day27_release_cleanup_report.md")
    return parser.parse_args()


def main() -> int:
    start = time.time()
    args = parse_args()
    config = load_config(args.config)
    try:
        artifacts = load_day27_inputs(args.repo_root, args.out_root, args.reports_root, args.readme)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    readme_audit = audit_readme_scope(artifacts["readme"], config["required_readme_phrases"])
    forbidden_audit = audit_forbidden_claims(artifacts["readme"], config["forbidden_readme_phrases"])
    path_audit = audit_release_forbidden_paths(args.repo_root, config["forbidden_paths"])
    file_policy = build_release_file_policy()
    archive_plan = build_safe_archive_plan()
    figure_readiness = build_figure_table_generation_readiness(artifacts["day26_figure_plan"])
    recommendation = derive_day28_recommendation()

    table_dir = args.out_root / "tables"
    manifest_dir = args.out_root / "manifests"
    readme_path = table_dir / "day27_readme_scope_audit.csv"
    forbidden_path = table_dir / "day27_forbidden_claims_audit.csv"
    paths_path = table_dir / "day27_release_forbidden_paths_audit.csv"
    policy_path = table_dir / "day27_release_file_policy.csv"
    archive_path = table_dir / "day27_safe_archive_plan.csv"
    figure_path = table_dir / "day27_figure_table_readiness.csv"
    recommendation_path = table_dir / "day27_day28_recommendation.csv"
    manifest_path = manifest_dir / "day27_release_cleanup_manifest.json"

    write_csv(readme_path, README_FIELDNAMES, readme_audit)
    write_csv(forbidden_path, FORBIDDEN_CLAIM_FIELDNAMES, forbidden_audit)
    write_csv(paths_path, FORBIDDEN_PATH_FIELDNAMES, path_audit)
    write_csv(policy_path, FILE_POLICY_FIELDNAMES, file_policy)
    write_csv(archive_path, ARCHIVE_FIELDNAMES, archive_plan)
    write_csv(figure_path, FIGURE_READINESS_FIELDNAMES, figure_readiness)
    write_csv(recommendation_path, RECOMMENDATION_FIELDNAMES, recommendation)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(build_report(readme_audit, forbidden_audit, path_audit, figure_readiness, recommendation), encoding="utf-8")

    outputs = [
        readme_path,
        forbidden_path,
        paths_path,
        policy_path,
        archive_path,
        figure_path,
        recommendation_path,
        manifest_path,
        args.report,
    ]
    manifest = write_day27_manifest(
        manifest_path,
        inputs=artifacts["input_paths"] + [args.config],
        outputs=outputs,
        readme_audit=readme_audit,
        forbidden_audit=forbidden_audit,
        path_audit=path_audit,
        archive_plan=archive_plan,
        figure_readiness=figure_readiness,
        artifacts=artifacts,
        runtime_seconds=time.time() - start,
    )

    print(f"day27 README audit: {display_path(readme_path)}")
    print(f"day27 forbidden claims audit: {display_path(forbidden_path)}")
    print(f"day27 forbidden paths audit: {display_path(paths_path)}")
    print(f"day27 release file policy: {display_path(policy_path)}")
    print(f"day27 safe archive plan: {display_path(archive_path)}")
    print(f"day27 figure/table readiness: {display_path(figure_path)}")
    print(f"day27 recommendation: {display_path(recommendation_path)}")
    print(f"day27 manifest: {display_path(manifest_path)}")
    print(f"day27 report: {display_path(args.report)}")
    print(f"status: {manifest['status']}")
    return 0 if manifest["status"] == "OK" else 1


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"Day27 config must be a mapping: {path}")
    config.setdefault("forbidden_paths", [".git", ".pytest_cache", "__pycache__"])
    config.setdefault("required_readme_phrases", [])
    config.setdefault("forbidden_readme_phrases", [])
    return config


def build_report(
    readme_audit: Sequence[Dict[str, str]],
    forbidden_audit: Sequence[Dict[str, str]],
    path_audit: Sequence[Dict[str, str]],
    figure_readiness: Sequence[Dict[str, str]],
    recommendation: Sequence[Dict[str, str]],
) -> str:
    readme_ok = all(row["status"] == "pass" for row in readme_audit)
    forbidden_ok = all(row["status"] == "pass" for row in forbidden_audit)
    excluded = ", ".join(row["path_pattern"] for row in path_audit)
    ready = [row["item_id"] for row in figure_readiness if row["readiness_status"] == "ready_for_conversion"]
    pending = [row["item_id"] for row in figure_readiness if row["readiness_status"] == "pending"]
    selected = [row for row in recommendation if row["allowed"] == "true"]
    selected_text = "; ".join(f"{row['recommended_route']}: {row['task']}" for row in selected[:2])
    return f"""# Day 27 README / Release Cleanup Report

## Direct Answers

- README 是否已经更新为 diagnostic benchmark / failure-analysis 定位？{'Yes' if readme_ok else 'No'}.
- README 是否仍存在 forbidden claims？{'No' if forbidden_ok else 'Yes'}.
- release archive 需要排除哪些路径？{excluded}.
- 是否已经生成安全 release plan？Yes. `day27_safe_archive_plan.csv` records non-destructive archive options.
- 图表生成哪些 ready，哪些 pending？Ready for conversion: `{', '.join(ready)}`. Pending: `{', '.join(pending)}`.
- 是否允许进入 weak-subspace update？No.
- Day 28 应该做什么？Selected options: {selected_text}.

## Conclusion

Day 27 updates README scope and creates a release hygiene audit for the diagnostic benchmark route.
The repository remains a diagnostic benchmark / failure-analysis package, not a validated Degen-LIO estimator method.
Weak-subspace update remains unauthorized.
Day 28 should proceed with figure/table generation scripts or paper section drafting, not method implementation.
"""


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


if __name__ == "__main__":
    raise SystemExit(main())
