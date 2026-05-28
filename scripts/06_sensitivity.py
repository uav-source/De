#!/usr/bin/env python3
"""Run Day 12 detector sensitivity checks for whitening D and tau_w."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Tuple

import numpy as np  # noqa: E402
import yaml  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from degen_detector.odi_tracker import compute_metrics_for_sequence  # noqa: E402
from eval.stats import spearman_corr  # noqa: E402


plt = None

SEQUENCES = [
    "OC-L0-S01-M1",
    "ST-L3-S01-M1",
    "CT-L2-S01-M2",
    "RT-L4-S01-M1",
]

S_THETA_VALUES = [0.02, 0.05, 0.10]
S_P_VALUES = [0.2, 0.5, 1.0]
TAU_W_VALUES = [0.005, 0.01, 0.02, 0.05]
HIGH_DEGENERACY_ODI_THRESHOLD = 0.70

FIELDNAMES = [
    "s_theta",
    "s_p",
    "tau_w",
    "ODI_median",
    "OC_ODI_median",
    "ST_ODI_median",
    "CT_ODI_median",
    "RT_ODI_median",
    "ST_median_axis_alignment",
    "RT_median_axis_alignment",
    "CT_median_axis_alignment",
    "merged_ODI_axis_drift_spearman",
    "OC_ODI_axis_drift_spearman",
    "ST_ODI_axis_drift_spearman",
    "CT_ODI_axis_drift_spearman",
    "RT_ODI_axis_drift_spearman",
    "per_sequence_rho_min",
    "per_sequence_rho_max",
    "OC_false_reliable_ratio",
    "OC_false_high_degeneracy_ratio",
    "high_degeneracy_odi_threshold",
    "valid_sensitivity_point",
    "n_boot",
    "notes",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True, help="Base detector config.")
    parser.add_argument("--results", type=Path, default=ROOT / "results/day14", help="Day 14 results directory.")
    parser.add_argument("--data-root", type=Path, default=ROOT / "data/minibench", help="Minibench data root containing observations.npz.")
    parser.add_argument("--out", type=Path, default=ROOT / "results/day14/tables", help="Output table directory.")
    parser.add_argument("--figures-out", type=Path, help="Figure output directory; defaults to <results>/figures.")
    parser.add_argument("--n-boot", type=int, default=1000, help="Reserved bootstrap budget for reproducibility records.")
    parser.add_argument(
        "--smoke-test-no-render",
        action="store_true",
        help="Write structurally valid sensitivity outputs without importing matplotlib or computing full variants.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = args.config if args.config.is_absolute() else ROOT / args.config
    results_dir = args.results if args.results.is_absolute() else ROOT / args.results
    data_root = args.data_root if args.data_root.is_absolute() else ROOT / args.data_root
    out_dir = args.out if args.out.is_absolute() else ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = args.figures_out if args.figures_out else results_dir / "figures"
    figures_dir = figures_dir if figures_dir.is_absolute() else ROOT / figures_dir
    figures_dir.mkdir(parents=True, exist_ok=True)
    force_cli_exit = os.environ.get("DEGEN_FORCE_CLI_EXIT") == "1"

    try:
        if args.smoke_test_no_render:
            d_rows = smoke_d_rows(int(args.n_boot))
            tau_rows = smoke_tau_rows(int(args.n_boot))
            write_csv(out_dir / "day12_sensitivity_D.csv", d_rows)
            write_csv(out_dir / "day12_sensitivity_tau.csv", tau_rows)
            write_smoke_figures(figures_dir)
            update_plotting_manifest(
                figures_dir,
                results_dir,
                [
                    out_dir / "day12_sensitivity_D.csv",
                    out_dir / "day12_sensitivity_tau.csv",
                ],
                smoke_test=True,
            )
            print(
                f"sensitivity smoke-test: D_rows={len(d_rows)} tau_rows={len(tau_rows)} "
                f"n_boot={int(args.n_boot)} tables={out_dir} figures={figures_dir}"
            )
            sys.stdout.flush()
            sys.stderr.flush()
            if force_cli_exit:
                os._exit(0)
            return 0

        load_pyplot()
        base_config = load_config(config_path)
        window_metrics = {seq: load_csv_dicts(results_dir / "metrics" / f"{seq}_metrics.csv") for seq in SEQUENCES}
        observations = {seq: load_observations(data_root / seq / "observations.npz") for seq in SEQUENCES}

        d_rows = []
        for s_theta in S_THETA_VALUES:
            for s_p in S_P_VALUES:
                variant = dict(base_config)
                variant["s_theta"] = float(s_theta)
                variant["s_p"] = float(s_p)
                variant["n_boot"] = int(args.n_boot)
                d_rows.append(evaluate_variant(variant, observations, window_metrics))

        tau_rows = []
        for tau_w in TAU_W_VALUES:
            variant = dict(base_config)
            variant["tau_w"] = float(tau_w)
            variant["n_boot"] = int(args.n_boot)
            tau_rows.append(evaluate_variant(variant, observations, window_metrics))

        write_csv(out_dir / "day12_sensitivity_D.csv", d_rows)
        write_csv(out_dir / "day12_sensitivity_tau.csv", tau_rows)
        save_figure(figures_dir, "Fig_D14_08_sensitivity_D", lambda: plot_sensitivity_D(d_rows))
        save_figure(figures_dir, "Fig_D14_09_sensitivity_tau", lambda: plot_sensitivity_tau(tau_rows))
        update_plotting_manifest(
            figures_dir,
            results_dir,
            [
                out_dir / "day12_sensitivity_D.csv",
                out_dir / "day12_sensitivity_tau.csv",
            ],
            smoke_test=False,
        )

        print(
            f"sensitivity: D_rows={len(d_rows)} tau_rows={len(tau_rows)} "
            f"n_boot={int(args.n_boot)} tables={out_dir} figures={figures_dir}"
        )
        sys.stdout.flush()
        sys.stderr.flush()
        if force_cli_exit:
            os._exit(0)
        return 0
    finally:
        if not force_cli_exit and plt is not None:
            plt.close("all")
        if not force_cli_exit:
            sys.stdout.flush()
            sys.stderr.flush()


def load_pyplot() -> None:
    global plt
    if plt is None:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as pyplot

        plt = pyplot


def evaluate_variant(
    config: Mapping[str, object],
    observations: Mapping[str, object],
    window_metrics: Mapping[str, Sequence[Mapping[str, object]]],
) -> Dict[str, object]:
    detector_rows = {
        seq: compute_metrics_for_sequence(observations[seq], dict(config))
        for seq in SEQUENCES
    }

    window_rows = []
    per_sequence_rhos = {}
    for seq in SEQUENCES:
        seq_windows = build_window_odi_rows(detector_rows[seq], window_metrics[seq])
        window_rows.extend(seq_windows)
        rho, _ = spearman_corr(
            [row["mean_ODI"] for row in seq_windows],
            [row["axis_drift_rate"] for row in seq_windows],
        )
        per_sequence_rhos[seq] = rho

    merged_rho, _ = spearman_corr(
        [row["mean_ODI"] for row in window_rows],
        [row["axis_drift_rate"] for row in window_rows],
    )
    all_odi = np.concatenate([detector_rows[seq]["ODI"] for seq in SEQUENCES])
    finite_per_seq = np.asarray([per_sequence_rhos[seq] for seq in SEQUENCES], dtype=float)
    finite_per_seq = finite_per_seq[np.isfinite(finite_per_seq)]

    row: Dict[str, object] = {
        "s_theta": float(config["s_theta"]),
        "s_p": float(config["s_p"]),
        "tau_w": float(config.get("tau_w", 0.02)),
        "n_boot": int(config.get("n_boot", 1000)),
        "ODI_median": float(np.median(all_odi)),
        "merged_ODI_axis_drift_spearman": merged_rho,
        "per_sequence_rho_min": float(np.min(finite_per_seq)) if finite_per_seq.size else float("nan"),
        "per_sequence_rho_max": float(np.max(finite_per_seq)) if finite_per_seq.size else float("nan"),
        "high_degeneracy_odi_threshold": HIGH_DEGENERACY_ODI_THRESHOLD,
    }
    for seq in SEQUENCES:
        short = seq.split("-")[0]
        row[f"{short}_ODI_median"] = float(np.median(detector_rows[seq]["ODI"]))
        row[f"{short}_ODI_axis_drift_spearman"] = per_sequence_rhos[seq]

    for seq in ["ST-L3-S01-M1", "RT-L4-S01-M1", "CT-L2-S01-M2"]:
        short = seq.split("-")[0]
        row[f"{short}_median_axis_alignment"] = median_reliable_alignment(detector_rows[seq])

    oc = detector_rows["OC-L0-S01-M1"]
    row["OC_false_reliable_ratio"] = float(np.mean(oc["weak_reliable"]))
    row["OC_false_high_degeneracy_ratio"] = float(np.mean(oc["ODI"] >= HIGH_DEGENERACY_ODI_THRESHOLD))
    required = [
        "ODI_median",
        "ST_median_axis_alignment",
        "RT_median_axis_alignment",
        "CT_median_axis_alignment",
        "merged_ODI_axis_drift_spearman",
        "OC_false_reliable_ratio",
        "OC_false_high_degeneracy_ratio",
    ]
    valid = all(np.isfinite(float(row[key])) for key in required)
    row["valid_sensitivity_point"] = int(valid)
    row["notes"] = "" if valid else "nan_or_missing_required_metric"
    return row


def smoke_d_rows(n_boot: int) -> List[Dict[str, object]]:
    rows = []
    for s_theta in S_THETA_VALUES:
        for s_p in S_P_VALUES:
            row = smoke_row(float(s_theta), float(s_p), 0.02, int(n_boot))
            row["merged_ODI_axis_drift_spearman"] = 0.55 + 0.02 * S_THETA_VALUES.index(s_theta) - 0.01 * S_P_VALUES.index(s_p)
            rows.append(row)
    return rows


def smoke_tau_rows(n_boot: int) -> List[Dict[str, object]]:
    return [smoke_row(0.05, 0.5, float(tau_w), int(n_boot)) for tau_w in TAU_W_VALUES]


def smoke_row(s_theta: float, s_p: float, tau_w: float, n_boot: int) -> Dict[str, object]:
    row: Dict[str, object] = {
        "s_theta": s_theta,
        "s_p": s_p,
        "tau_w": tau_w,
        "ODI_median": 0.62,
        "OC_ODI_median": 0.30,
        "ST_ODI_median": 0.72,
        "CT_ODI_median": 0.71,
        "RT_ODI_median": 0.73,
        "ST_median_axis_alignment": 0.95,
        "RT_median_axis_alignment": 0.96,
        "CT_median_axis_alignment": 0.94,
        "merged_ODI_axis_drift_spearman": 0.60,
        "OC_ODI_axis_drift_spearman": -0.02,
        "ST_ODI_axis_drift_spearman": -0.10,
        "CT_ODI_axis_drift_spearman": 0.12,
        "RT_ODI_axis_drift_spearman": -0.20,
        "per_sequence_rho_min": -0.20,
        "per_sequence_rho_max": 0.12,
        "OC_false_reliable_ratio": 0.0,
        "OC_false_high_degeneracy_ratio": 0.0,
        "high_degeneracy_odi_threshold": HIGH_DEGENERACY_ODI_THRESHOLD,
        "valid_sensitivity_point": 1,
        "n_boot": n_boot,
        "notes": "smoke_test_no_render",
    }
    return row


def build_window_odi_rows(detector_rows: np.ndarray, metric_rows: Sequence[Mapping[str, object]]) -> List[Dict[str, float]]:
    rows = []
    for metric_row in metric_rows:
        start = int(metric_row["start_idx"])
        end = int(metric_row["end_idx"])
        rows.append(
            {
                "mean_ODI": float(np.mean(detector_rows["ODI"][start : end + 1])),
                "axis_drift_rate": float(metric_row["axis_drift_rate"]),
            }
        )
    return rows


def median_reliable_alignment(rows: np.ndarray) -> float:
    reliable = rows["weak_reliable"].astype(bool)
    alignment = rows["axis_alignment"][reliable]
    alignment = alignment[np.isfinite(alignment)]
    return float(np.median(alignment)) if alignment.size else float("nan")


def plot_sensitivity_D(rows: Sequence[Mapping[str, object]]) -> plt.Figure:
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 8.5))
    heatmap(axes[0, 0], rows, "merged_ODI_axis_drift_spearman", "Merged ODI-axis drift rho")
    heatmap(axes[0, 1], rows, "OC_false_high_degeneracy_ratio", "OC false high-degeneracy ratio")
    heatmap(axes[1, 0], rows, "OC_false_reliable_ratio", "OC false reliable ratio")
    ax = axes[1, 1]
    labels = [f"{row['s_theta']:.2f}/{row['s_p']:.1f}" for row in rows]
    x = np.arange(len(rows))
    merged = [float(row["merged_ODI_axis_drift_spearman"]) for row in rows]
    rho_min = [float(row["per_sequence_rho_min"]) for row in rows]
    rho_max = [float(row["per_sequence_rho_max"]) for row in rows]
    ax.plot(x, merged, marker="o", label="merged rho")
    ax.fill_between(x, rho_min, rho_max, alpha=0.25, label="per-sequence rho range")
    ax.axhline(0.0, color="0.2", linewidth=1.0)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_ylabel("Spearman rho (unitless)")
    ax.set_title("Merged support vs per-sequence instability")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.suptitle("Sensitivity to whitening scale D", y=0.995)
    fig.tight_layout()
    return fig


def plot_sensitivity_tau(rows: Sequence[Mapping[str, object]]) -> plt.Figure:
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 8.0))
    tau = np.asarray([float(row["tau_w"]) for row in rows])
    axes[0, 0].plot(tau, [float(row["merged_ODI_axis_drift_spearman"]) for row in rows], marker="o", label="merged rho")
    axes[0, 0].fill_between(
        tau,
        [float(row["per_sequence_rho_min"]) for row in rows],
        [float(row["per_sequence_rho_max"]) for row in rows],
        alpha=0.25,
        label="per-sequence rho range",
    )
    axes[0, 0].axhline(0.0, color="0.2", linewidth=1.0)
    axes[0, 0].set_title("ODI-axis drift correlation")
    axes[0, 0].set_ylabel("Spearman rho (unitless)")
    axes[0, 0].legend()

    for seq in ["ST", "CT", "RT"]:
        axes[0, 1].plot(tau, [float(row[f"{seq}_median_axis_alignment"]) for row in rows], marker="o", label=seq)
    axes[0, 1].set_ylim(0.0, 1.05)
    axes[0, 1].set_title("Reliable axis alignment")
    axes[0, 1].set_ylabel("Median alignment (unitless)")
    axes[0, 1].legend()

    axes[1, 0].plot(tau, [float(row["OC_false_reliable_ratio"]) for row in rows], marker="o", label="OC false reliable")
    axes[1, 0].plot(tau, [float(row["OC_false_high_degeneracy_ratio"]) for row in rows], marker="s", label="OC false high ODI")
    axes[1, 0].set_ylim(0.0, 1.05)
    axes[1, 0].set_title("OC false-positive ratios")
    axes[1, 0].set_ylabel("Ratio (unitless)")
    axes[1, 0].legend()

    axes[1, 1].plot(tau, [float(row["ODI_median"]) for row in rows], marker="o", label="all-scene median ODI")
    axes[1, 1].plot(tau, [float(row["OC_ODI_median"]) for row in rows], marker="s", label="OC median ODI")
    axes[1, 1].set_title("ODI stability")
    axes[1, 1].set_ylabel("ODI (unitless)")
    axes[1, 1].legend()

    for ax in axes.flat:
        ax.set_xlabel("tau_w (unitless)")
        ax.grid(True, alpha=0.3)
    fig.suptitle("Sensitivity to weak-subspace threshold tau_w", y=0.995)
    fig.tight_layout()
    return fig


def heatmap(ax, rows: Sequence[Mapping[str, object]], key: str, title: str) -> None:
    grid = np.full((len(S_THETA_VALUES), len(S_P_VALUES)), np.nan)
    for row in rows:
        i = S_THETA_VALUES.index(round(float(row["s_theta"]), 2))
        j = S_P_VALUES.index(round(float(row["s_p"]), 1))
        grid[i, j] = float(row[key])
    image = ax.imshow(grid, origin="lower", aspect="auto")
    ax.set_xticks(np.arange(len(S_P_VALUES)))
    ax.set_xticklabels([str(v) for v in S_P_VALUES])
    ax.set_yticks(np.arange(len(S_THETA_VALUES)))
    ax.set_yticklabels([str(v) for v in S_THETA_VALUES])
    ax.set_xlabel("s_p (m scale)")
    ax.set_ylabel("s_theta (rad scale)")
    ax.set_title(title)
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            ax.text(j, i, f"{grid[i, j]:.2f}", ha="center", va="center", color="white")
    plt.colorbar(image, ax=ax, fraction=0.046, pad=0.04)


def save_figure(figures_dir: Path, name: str, plotter) -> None:
    fig = plotter()
    for ext in ["png", "pdf"]:
        fig.savefig(figures_dir / f"{name}.{ext}", dpi=180 if ext == "png" else None, bbox_inches="tight")
    plt.close(fig)


def update_plotting_manifest(figures_dir: Path, results_dir: Path, table_paths: Sequence[Path], smoke_test: bool = False) -> None:
    manifest_path = figures_dir / "plotting_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            manifest = {}
    else:
        manifest = {}

    figures = list(manifest.get("figures", []))
    output_files = set(manifest.get("output_files", []))
    input_files = set(manifest.get("input_files", []))
    for path in table_paths:
        input_files.add(relative_to_root(path))

    new_figures = {
        "Fig_D14_08_sensitivity_D": "Sensitivity to whitening scale D with stability and instability.",
        "Fig_D14_09_sensitivity_tau": "Sensitivity to tau_w with OC false-positive checks.",
    }
    existing_names = {entry.get("name") for entry in figures if isinstance(entry, dict)}
    for name, description in new_figures.items():
        png = figures_dir / f"{name}.png"
        pdf = figures_dir / f"{name}.pdf"
        if name not in existing_names:
            figures.append(
                {
                    "name": name,
                    "description": description,
                    "png": relative_to_root(png),
                    "pdf": relative_to_root(pdf),
                }
            )
        output_files.add(relative_to_root(png))
        output_files.add(relative_to_root(pdf))

    notes = list(manifest.get("notes", []))
    note = "Fig_D14_08 and Fig_D14_09 are generated by scripts/06_sensitivity.py."
    if note not in notes:
        notes.append(note)
    if smoke_test:
        smoke_note = "smoke_test=true; placeholder outputs skip matplotlib rendering."
        if smoke_note not in notes:
            notes.append(smoke_note)

    manifest.update(
        {
            "script": manifest.get("script", "scripts/04_plot_day14.py + scripts/06_sensitivity.py"),
            "command": manifest.get("command", "python3 scripts/04_plot_day14.py ...; python3 scripts/06_sensitivity.py ..."),
            "git_commit": git_commit(),
            "smoke_test": bool(smoke_test),
            "input_files": sorted(input_files),
            "output_files": sorted(output_files),
            "figures": figures,
            "notes": notes,
        }
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_smoke_figures(figures_dir: Path) -> None:
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00"
        b"\x00\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    pdf_bytes = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
    for name in ["Fig_D14_08_sensitivity_D", "Fig_D14_09_sensitivity_tau"]:
        (figures_dir / f"{name}.png").write_bytes(png_bytes)
        (figures_dir / f"{name}.pdf").write_bytes(pdf_bytes)


def write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDNAMES})


def load_observations(path: Path) -> Dict[str, np.ndarray]:
    with np.load(path) as handle:
        return {name: handle[name] for name in handle.files}


def load_config(path: Path) -> Dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"Config must be a mapping: {path}")
    return config


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


def relative_to_root(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def git_commit() -> str:
    import subprocess

    try:
        return subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
