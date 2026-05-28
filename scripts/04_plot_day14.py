#!/usr/bin/env python3
"""Generate Day 11 diagnostic figures for the Day 14 package."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence

import numpy as np  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
plt = None

SEQUENCES = [
    "OC-L0-S01-M1",
    "ST-L3-S01-M1",
    "CT-L2-S01-M2",
    "RT-L4-S01-M1",
]

METRIC_NAMES = ["ODI", "condition_number", "lambda_min_clamped", "AIS"]

FIGURES = {
    "Fig_D14_01_spectrum_across_scenes": "Median normalized eigenvalue spectrum across scenes.",
    "Fig_D14_02_odi_timeline": "Framewise ODI, AIS, and lambda_min_clamped timelines.",
    "Fig_D14_03_alignment_hist": "Weak direction axis-alignment distributions.",
    "Fig_D14_04_odi_vs_axis_drift_merged_and_per_sequence": "Merged and per-sequence ODI-axis drift scatter.",
    "Fig_D14_05_metric_validity_comparison": "Metric validity comparison with merged, per-sequence, and LOSO evidence.",
    "Fig_D14_06_axis_cross_error": "Axis and cross error comparison.",
    "Fig_D14_07_bias_audit_summary": "Bias audit summary from Day 10 diagnostics.",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=ROOT / "results/day14", help="Day 14 results directory.")
    parser.add_argument("--out", type=Path, default=ROOT / "results/day14/figures", help="Figure output directory.")
    parser.add_argument(
        "--smoke-test-no-render",
        action="store_true",
        help="Validate inputs and write placeholder outputs/manifest without importing matplotlib.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results_dir = args.results if args.results.is_absolute() else ROOT / args.results
    out_dir = args.out if args.out.is_absolute() else ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    input_files = required_inputs(results_dir)
    for path in input_files:
        if not path.exists():
            raise FileNotFoundError(f"Missing required plotting input: {path}")

    try:
        if args.smoke_test_no_render:
            outputs = write_smoke_outputs(out_dir)
            write_plotting_manifest(out_dir, input_files, outputs, smoke_test=True)
            print(f"generated diagnostic smoke-test files: count={len(FIGURES)} out={out_dir}")
            print(f"manifest: {out_dir / 'plotting_manifest.json'}")
            return 0

        load_pyplot()

        raw_odi = {seq: load_csv_dicts(results_dir / "raw" / f"{seq}_odi.csv") for seq in SEQUENCES}
        window_metrics = {seq: load_csv_dicts(results_dir / "metrics" / f"{seq}_metrics.csv") for seq in SEQUENCES}
        metric_summary = load_csv_dicts(results_dir / "tables/day08_metric_summary.csv")
        validity = load_csv_dicts(results_dir / "tables/day10_metric_validity.csv")
        per_sequence = load_csv_dicts(results_dir / "tables/day10_metric_validity_per_sequence.csv")
        loso = load_csv_dicts(results_dir / "tables/day10_metric_validity_loso.csv")

        outputs: List[Path] = []
        outputs += save_figure(out_dir, "Fig_D14_01_spectrum_across_scenes", lambda: plot_spectrum(raw_odi))
        outputs += save_figure(out_dir, "Fig_D14_02_odi_timeline", lambda: plot_timeline(raw_odi))
        outputs += save_figure(out_dir, "Fig_D14_03_alignment_hist", lambda: plot_alignment_hist(raw_odi))
        outputs += save_figure(
            out_dir,
            "Fig_D14_04_odi_vs_axis_drift_merged_and_per_sequence",
            lambda: plot_odi_vs_axis_drift(window_metrics, validity, per_sequence),
        )
        outputs += save_figure(
            out_dir,
            "Fig_D14_05_metric_validity_comparison",
            lambda: plot_metric_validity(validity, per_sequence, loso),
        )
        outputs += save_figure(out_dir, "Fig_D14_06_axis_cross_error", lambda: plot_axis_cross_error(metric_summary))
        outputs += save_figure(
            out_dir,
            "Fig_D14_07_bias_audit_summary",
            lambda: plot_bias_audit_summary(validity, per_sequence, loso, metric_summary),
        )

        write_plotting_manifest(out_dir, input_files, outputs, smoke_test=False)
        print(f"generated diagnostic figures: count={len(FIGURES)} out={out_dir}")
        print(f"manifest: {out_dir / 'plotting_manifest.json'}")
        return 0
    finally:
        if plt is not None:
            plt.close("all")
        sys.stdout.flush()
        sys.stderr.flush()


def load_pyplot() -> None:
    global plt
    if plt is None:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as pyplot

        plt = pyplot


def write_plotting_manifest(out_dir: Path, input_files: Sequence[Path], outputs: Sequence[Path], smoke_test: bool) -> None:
    manifest = {
        "script": "scripts/04_plot_day14.py",
        "command": "python3 scripts/04_plot_day14.py --results results/day14 --out results/day14/figures",
        "git_commit": git_commit(),
        "input_files": [relative_to_root(path) for path in input_files],
        "output_files": [relative_to_root(path) for path in outputs],
        "figures": [
            {
                "name": name,
                "description": description,
                "png": relative_to_root(out_dir / f"{name}.png"),
                "pdf": relative_to_root(out_dir / f"{name}.pdf"),
            }
            for name, description in FIGURES.items()
        ],
        "notes": [
            "Fig_D14_04 explicitly includes merged_and_per_sequence evidence.",
            "Fig_D14_05 explicitly includes metric_validity_comparison evidence.",
            "Rho values are read from Day 10 CSV tables, not hard-coded.",
            "Smoke-test outputs skip matplotlib rendering." if smoke_test else "Rendered with matplotlib Agg backend.",
        ],
    }
    manifest_path = out_dir / "plotting_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_smoke_outputs(out_dir: Path) -> List[Path]:
    outputs: List[Path] = []
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00"
        b"\x00\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    pdf_bytes = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
    for name in FIGURES:
        png_path = out_dir / f"{name}.png"
        pdf_path = out_dir / f"{name}.pdf"
        png_path.write_bytes(png_bytes)
        pdf_path.write_bytes(pdf_bytes)
        outputs.extend([png_path, pdf_path])
    manifest_path = out_dir / "plotting_manifest.json"
    outputs.append(manifest_path)
    return outputs


def plot_spectrum(raw_odi: Mapping[str, List[Dict[str, object]]]) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    x = np.arange(1, 7)
    for seq, rows in raw_odi.items():
        eig = np.column_stack([values(rows, f"eig_{idx}") for idx in range(1, 7)])
        eig = np.maximum(eig, 0.0)
        denom = np.maximum(np.sum(eig, axis=1, keepdims=True), 1.0e-12)
        normalized = eig / denom
        median_spectrum = np.maximum(np.median(normalized, axis=0), 1.0e-12)
        ax.plot(x, median_spectrum, marker="o", linewidth=2.0, label=short_name(seq))
    ax.set_xlabel("Eigenvalue index (largest to smallest)")
    ax.set_ylabel("Median normalized eigenvalue (unitless)")
    ax.set_title("Median normalized spectrum across scenes")
    ax.set_yscale("log")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(title="Sequence")
    fig.tight_layout()
    return fig


def plot_timeline(raw_odi: Mapping[str, List[Dict[str, object]]]) -> plt.Figure:
    fig, axes = plt.subplots(len(SEQUENCES), 3, figsize=(13.5, 9.5), sharex=False)
    columns = [
        ("ODI", "ODI (unitless)"),
        ("AIS", "AIS (log whitened information)"),
        ("lambda_min_clamped", "lambda_min_clamped (whitened information)"),
    ]
    for row_idx, seq in enumerate(SEQUENCES):
        rows = raw_odi[seq]
        time_s = values(rows, "timestamp")
        for col_idx, (key, ylabel) in enumerate(columns):
            ax = axes[row_idx, col_idx]
            ax.plot(time_s, values(rows, key), linewidth=1.5, label=key)
            ax.set_title(f"{short_name(seq)} {key}")
            ax.set_xlabel("Time (s)")
            ax.set_ylabel(ylabel)
            ax.grid(True, alpha=0.3)
            ax.legend(loc="best")
    fig.suptitle("Online detector timelines per sequence", y=0.995)
    fig.tight_layout()
    return fig


def plot_alignment_hist(raw_odi: Mapping[str, List[Dict[str, object]]]) -> plt.Figure:
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.5), gridspec_kw={"width_ratios": [2.4, 1.0]})
    ax_hist, ax_ratio = axes
    bins = np.linspace(0.0, 1.0, 21)
    ratios = []
    for seq, rows in raw_odi.items():
        reliable = values(rows, "weak_reliable").astype(bool)
        alignment = values(rows, "axis_alignment")
        finite = reliable & np.isfinite(alignment)
        ratios.append(float(np.mean(reliable)))
        if np.any(finite):
            ax_hist.hist(alignment[finite], bins=bins, alpha=0.45, label=short_name(seq), density=True)
        else:
            ax_hist.plot([], [], label=f"{short_name(seq)} no reliable frames")
    ax_hist.set_xlabel("axis_alignment |v_p^T a| (unitless)")
    ax_hist.set_ylabel("Density (1/unitless)")
    ax_hist.set_title("Reliable weak-direction alignment")
    ax_hist.set_xlim(0.0, 1.0)
    ax_hist.grid(True, alpha=0.3)
    ax_hist.legend()

    ax_ratio.bar([short_name(seq) for seq in SEQUENCES], ratios)
    ax_ratio.set_ylim(0.0, 1.05)
    ax_ratio.set_ylabel("Reliable frame ratio (unitless)")
    ax_ratio.set_title("Reliability")
    ax_ratio.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    return fig


def plot_odi_vs_axis_drift(
    window_metrics: Mapping[str, List[Dict[str, object]]],
    validity: Sequence[Mapping[str, object]],
    per_sequence: Sequence[Mapping[str, object]],
) -> plt.Figure:
    fig, axes = plt.subplots(2, 3, figsize=(13.5, 8.5))
    all_rows = [row for seq in SEQUENCES for row in window_metrics[seq]]
    ax = axes[0, 0]
    for seq in SEQUENCES:
        rows = window_metrics[seq]
        ax.scatter(values(rows, "mean_ODI"), values(rows, "axis_drift_rate"), s=24, alpha=0.75, label=short_name(seq))
    merged_rho = lookup(validity, "metric_name", "ODI", "target_name", "axis_drift_rate", "spearman_rho")
    ax.text(0.02, 0.96, f"merged Spearman rho={merged_rho:.3f}", transform=ax.transAxes, va="top")
    ax.set_title("Merged all sequences")
    ax.set_xlabel("Mean ODI in window (unitless)")
    ax.set_ylabel("Axis drift rate (m/m)")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)

    subplot_positions = [(0, 1), (0, 2), (1, 0), (1, 1)]
    for seq, pos in zip(SEQUENCES, subplot_positions):
        seq_rows = window_metrics[seq]
        seq_ax = axes[pos]
        seq_ax.scatter(values(seq_rows, "mean_ODI"), values(seq_rows, "axis_drift_rate"), s=24, alpha=0.8)
        rho = lookup(per_sequence, "sequence_id", seq, "metric_name", "ODI", "target_name", "axis_drift_rate", "spearman_rho")
        seq_ax.text(0.04, 0.94, f"rho={format_float(rho)}", transform=seq_ax.transAxes, va="top")
        seq_ax.set_title(short_name(seq))
        seq_ax.set_xlabel("Mean ODI (unitless)")
        seq_ax.set_ylabel("Axis drift rate (m/m)")
        seq_ax.grid(True, alpha=0.3)
    axes[1, 2].axis("off")
    axes[1, 2].text(
        0.0,
        0.8,
        "Diagnostic point:\nmerged signal is shown with\nper-sequence instability.",
        fontsize=11,
        va="top",
    )
    fig.suptitle("ODI vs axis drift: merged and per-sequence views", y=0.995)
    fig.tight_layout()
    return fig


def plot_metric_validity(
    validity: Sequence[Mapping[str, object]],
    per_sequence: Sequence[Mapping[str, object]],
    loso: Sequence[Mapping[str, object]],
) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(10.5, 5.5))
    x = np.arange(len(METRIC_NAMES))
    merged = np.asarray(
        [lookup(validity, "metric_name", metric, "target_name", "axis_drift_rate", "spearman_rho") for metric in METRIC_NAMES],
        dtype=float,
    )
    ax.bar(x, merged, width=0.55, alpha=0.55, label="merged rho")

    for idx, metric in enumerate(METRIC_NAMES):
        per_vals = [
            lookup(per_sequence, "sequence_id", seq, "metric_name", metric, "target_name", "axis_drift_rate", "spearman_rho")
            for seq in SEQUENCES
        ]
        loso_vals = [
            lookup(loso, "held_out_sequence", seq, "metric_name", metric, "target_name", "axis_drift_rate", "test_spearman_rho_or_auc")
            for seq in SEQUENCES
        ]
        ax.scatter(np.full(len(per_vals), idx) - 0.18, per_vals, marker="o", color="black", s=32, label="per-sequence rho" if idx == 0 else None)
        ax.scatter(np.full(len(loso_vals), idx) + 0.18, loso_vals, marker="x", color="tab:red", s=45, label="LOSO held-out rho" if idx == 0 else None)
    ax.axhline(0.0, color="0.25", linewidth=1.0)
    ax.set_xticks(x)
    ax.set_xticklabels(METRIC_NAMES, rotation=20, ha="right")
    ax.set_ylabel("Spearman rho vs axis_drift_rate (unitless)")
    ax.set_title("Metric validity comparison with counter-evidence")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    return fig


def plot_axis_cross_error(metric_summary: Sequence[Mapping[str, object]]) -> plt.Figure:
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8), sharey=True)
    labels = [short_name(str(row["sequence_id"])) for row in metric_summary]
    x = np.arange(len(labels))
    width = 0.35
    for ax, axis_key, cross_key, title in [
        (axes[0], "final_axis_error", "final_cross_error", "Final error"),
        (axes[1], "mean_axis_error", "mean_cross_error", "Mean error"),
    ]:
        ax.bar(x - width / 2.0, [float(row[axis_key]) for row in metric_summary], width, label="axis error")
        ax.bar(x + width / 2.0, [float(row[cross_key]) for row in metric_summary], width, label="cross error")
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=20, ha="right")
        ax.set_ylabel("Translation error (m)")
        ax.set_title(title)
        ax.grid(True, axis="y", alpha=0.3)
        ax.legend()
    fig.suptitle("Axis and cross error diagnose directionality", y=0.995)
    fig.tight_layout()
    return fig


def plot_bias_audit_summary(
    validity: Sequence[Mapping[str, object]],
    per_sequence: Sequence[Mapping[str, object]],
    loso: Sequence[Mapping[str, object]],
    metric_summary: Sequence[Mapping[str, object]],
) -> plt.Figure:
    merged_rho = lookup(validity, "metric_name", "ODI", "target_name", "axis_drift_rate", "spearman_rho")
    per_vals = np.asarray(
        [
            lookup(per_sequence, "sequence_id", seq, "metric_name", "ODI", "target_name", "axis_drift_rate", "spearman_rho")
            for seq in SEQUENCES
        ],
        dtype=float,
    )
    loso_vals = np.asarray(
        [
            lookup(loso, "held_out_sequence", seq, "metric_name", "ODI", "target_name", "axis_drift_rate", "test_spearman_rho_or_auc")
            for seq in SEQUENCES
        ],
        dtype=float,
    )
    oc_axis = float(next(row for row in metric_summary if row["sequence_id"] == "OC-L0-S01-M1")["mean_axis_error"])
    tunnel_axis = np.mean([float(row["mean_axis_error"]) for row in metric_summary if row["sequence_id"] != "OC-L0-S01-M1"])
    axis_bias_risk_score = float(tunnel_axis / max(oc_axis, 1.0e-12))

    labels = ["merged ODI\nsignal", "per-seq\nunstable", "LOSO\nunstable", "axis-bias\nrisk"]
    scores = [
        1.0 if merged_rho >= 0.5 else 0.0,
        1.0 if np.any(per_vals < 0.0) else 0.0,
        1.0 if np.any(loso_vals < 0.0) else 0.0,
        min(axis_bias_risk_score / 1000.0, 1.0),
    ]
    colors = ["tab:green", "tab:orange", "tab:orange", "tab:red"]

    fig, ax = plt.subplots(figsize=(9.0, 4.8))
    ax.bar(labels, scores, color=colors, alpha=0.75, label="audit status")
    ax.set_ylim(0.0, 1.05)
    ax.set_ylabel("Audit status score (unitless)")
    ax.set_title("Bias audit: support and counter-evidence")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(loc="upper left")
    text = (
        f"merged ODI rho={merged_rho:.3f}\n"
        f"per-seq ODI range=[{np.nanmin(per_vals):.3f}, {np.nanmax(per_vals):.3f}]\n"
        f"LOSO ODI range=[{np.nanmin(loso_vals):.3f}, {np.nanmax(loso_vals):.3f}]\n"
        f"mean axis error tunnel/OC ratio={axis_bias_risk_score:.1f}"
    )
    ax.text(0.98, 0.95, text, transform=ax.transAxes, ha="right", va="top", bbox={"facecolor": "white", "alpha": 0.8})
    fig.tight_layout()
    return fig


def save_figure(out_dir: Path, name: str, plotter) -> List[Path]:
    fig = plotter()
    outputs = []
    for ext in ["png", "pdf"]:
        path = out_dir / f"{name}.{ext}"
        fig.savefig(path, dpi=180 if ext == "png" else None, bbox_inches="tight")
        outputs.append(path)
    plt.close(fig)
    return outputs


def required_inputs(results_dir: Path) -> List[Path]:
    inputs: List[Path] = []
    for seq in SEQUENCES:
        inputs.append(results_dir / "raw" / f"{seq}_odi.csv")
        inputs.append(results_dir / "metrics" / f"{seq}_metrics.csv")
    inputs.extend(
        [
            results_dir / "tables/day08_metric_summary.csv",
            results_dir / "tables/day10_metric_validity.csv",
            results_dir / "tables/day10_metric_validity_per_sequence.csv",
            results_dir / "tables/day10_metric_validity_loso.csv",
        ]
    )
    return inputs


def load_csv_dicts(path: Path) -> List[Dict[str, object]]:
    with path.open("r", encoding="utf-8") as handle:
        rows = []
        for row in csv.DictReader(handle):
            parsed: Dict[str, object] = {}
            for key, value in row.items():
                parsed[key] = parse_value(value)
            rows.append(parsed)
    if not rows:
        raise ValueError(f"CSV has no rows: {path}")
    return rows


def parse_value(value: str) -> object:
    try:
        return float(value)
    except ValueError:
        return value


def values(rows: Sequence[Mapping[str, object]], key: str) -> np.ndarray:
    return np.asarray([float(row.get(key, float("nan"))) for row in rows], dtype=float)


def lookup(rows: Sequence[Mapping[str, object]], *criteria) -> float:
    if len(criteria) < 3 or len(criteria) % 2 != 1:
        raise ValueError("lookup criteria must be key/value pairs followed by output field")
    output_field = str(criteria[-1])
    pairs = list(zip(criteria[:-1:2], criteria[1:-1:2]))
    for row in rows:
        if all(str(row.get(str(key))) == str(value) for key, value in pairs):
            try:
                return float(row[output_field])
            except (KeyError, TypeError, ValueError):
                return float("nan")
    return float("nan")


def short_name(sequence_id: str) -> str:
    return sequence_id.split("-")[0]


def format_float(value: float) -> str:
    return "NaN" if not np.isfinite(value) else f"{value:.3f}"


def relative_to_root(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


if __name__ == "__main__":
    rc = main()
    if os.environ.get("DEGEN_FORCE_CLI_EXIT") == "1":
        os._exit(rc)
    raise SystemExit(rc)
