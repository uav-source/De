#!/usr/bin/env python3
"""Generate F03 legacy vs unbiased toy_lio bias audit figure."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--day30-root", type=Path, default=ROOT / "results/day30")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "docs/paper/figures")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bias_path = args.day30_root / "tables/day15_bias_audit.csv"
    unbiased_path = args.day30_root / "tables/day16_unbiased_toy_lio_summary.csv"
    try:
        legacy_rows = read_rows(bias_path)
        unbiased_rows = read_rows(unbiased_path)
        data = join_rows(legacy_rows, unbiased_rows)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    args.out_dir.mkdir(parents=True, exist_ok=True)
    labels = [row["sequence_id"] for row in data]
    legacy = [row["legacy_axis_bias"] for row in data]
    applied = [row["applied_axis_bias"] for row in data]
    x = list(range(len(data)))
    width = 0.36
    fig, ax = plt.subplots(figsize=(10, 5.4), constrained_layout=True)
    ax.bar([v - width / 2 for v in x], legacy, width=width, label="legacy scene-family axis bias", color="#9467bd")
    ax.bar([v + width / 2 for v in x], applied, width=width, label="unbiased protocol applied bias", color="#17becf")
    for idx, row in enumerate(data):
        ax.text(idx, max(row["legacy_axis_bias"], row["applied_axis_bias"]) + 0.001, row["confound_risk_level"], ha="center", va="bottom", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylabel("axis bias magnitude [synthetic units]")
    ax.set_title("F03 Legacy Scene-Family Bias vs Unbiased Protocol Applied Bias")
    ax.legend()
    ax.grid(axis="y", linewidth=0.4, alpha=0.4)
    ax.text(
        0.01,
        -0.28,
        "Claim boundary: toy_lio is a synthetic diagnostic probe; this figure audits bias and does not validate a real LIO estimator.",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9,
    )
    png = args.out_dir / "F03_bias_audit_legacy_vs_unbiased.png"
    pdf = args.out_dir / "F03_bias_audit_legacy_vs_unbiased.pdf"
    fig.savefig(png, dpi=180)
    fig.savefig(pdf)
    plt.close(fig)
    print(f"generated {png}")
    print(f"generated {pdf}")
    return 0


def read_rows(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Missing required F03 source artifact: {path}")
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"F03 source artifact is empty: {path}")
    return rows


def join_rows(legacy_rows, unbiased_rows):
    unbiased = {row["sequence_id"]: row for row in unbiased_rows}
    data = []
    for row in legacy_rows:
        seq = row["sequence_id"]
        if seq not in unbiased:
            raise ValueError(f"Missing Day16 unbiased row for sequence {seq}")
        data.append(
            {
                "sequence_id": seq,
                "legacy_axis_bias": float(row["legacy_axis_bias"]),
                "applied_axis_bias": float(unbiased[seq]["applied_axis_bias"]),
                "confound_risk_level": row.get("confound_risk_level", "unknown"),
            }
        )
    return data


if __name__ == "__main__":
    raise SystemExit(main())
