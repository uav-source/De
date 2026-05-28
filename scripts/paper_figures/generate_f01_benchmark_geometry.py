#!/usr/bin/env python3
"""Generate F01 benchmark geometry overview from real minibench artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data/minibench")
    parser.add_argument("--config-root", type=Path, default=ROOT / "configs/minibench")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "docs/paper/figures")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        sequences = load_sequences(args.data_root, args.config_root)
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    args.out_dir.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(10, 8), constrained_layout=True)
    axes = list(axes.ravel())
    for ax, seq in zip(axes, sequences):
        points = seq["feature_points"]
        axis_rows = seq["axis"]
        planes = seq["planes"]
        metadata = seq["metadata"]
        xs = [row["x"] for row in points]
        ys = [row["y"] for row in points]
        ax.scatter(xs, ys, s=8, alpha=0.55, label="feature points")
        if axis_rows:
            origin_x = xs[len(xs) // 2] if xs else 0.0
            origin_y = ys[len(ys) // 2] if ys else 0.0
            mean_axis_x = sum(row["axis_x"] for row in axis_rows) / len(axis_rows)
            mean_axis_y = sum(row["axis_y"] for row in axis_rows) / len(axis_rows)
            ax.arrow(origin_x, origin_y, mean_axis_x * 4.0, mean_axis_y * 4.0, width=0.03, color="#d62728", label="mean local axis")
        for plane in planes[:6]:
            qx, qy = plane["qx"], plane["qy"]
            nx, ny = plane["nx"], plane["ny"]
            ax.arrow(qx, qy, nx * 0.8, ny * 0.8, color="#2ca02c", alpha=0.55, head_width=0.12)
        ax.set_title(f"{metadata['sequence_id']} ({metadata.get('scene_family', 'unknown')})")
        ax.set_xlabel("x [m]")
        ax.set_ylabel("y [m]")
        ax.axis("equal")
        ax.grid(True, linewidth=0.4, alpha=0.4)
    for ax in axes[len(sequences):]:
        ax.axis("off")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2)
    fig.suptitle("F01 Benchmark Geometry Overview (real minibench feature/axis/plane artifacts)", y=1.03)
    png = args.out_dir / "F01_benchmark_geometry_overview.png"
    pdf = args.out_dir / "F01_benchmark_geometry_overview.pdf"
    fig.savefig(png, dpi=180)
    fig.savefig(pdf)
    plt.close(fig)
    print(f"generated {png}")
    print(f"generated {pdf}")
    return 0


def load_sequences(data_root: Path, config_root: Path):
    if not data_root.exists():
        raise FileNotFoundError(f"Missing minibench data root: {data_root}")
    if not config_root.exists():
        raise FileNotFoundError(f"Missing minibench config root: {config_root}")
    sequence_dirs = sorted(path for path in data_root.iterdir() if path.is_dir())
    if not sequence_dirs:
        raise FileNotFoundError(f"No sequence directories found under {data_root}")
    sequences = []
    for seq_dir in sequence_dirs:
        metadata_path = seq_dir / "scene_metadata.json"
        feature_path = seq_dir / "feature_points.csv"
        axis_path = seq_dir / "axis.csv"
        planes_path = seq_dir / "planes.csv"
        for path in [metadata_path, feature_path, axis_path, planes_path]:
            if not path.exists():
                raise FileNotFoundError(f"Missing required F01 source artifact: {path}")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        sequence_id = metadata.get("sequence_id", seq_dir.name)
        config_path = config_root / f"{sequence_id}.yaml"
        if not config_path.exists():
            raise FileNotFoundError(f"Missing required F01 minibench config: {config_path}")
        feature_points = read_float_csv(feature_path)
        axis = read_float_csv(axis_path)
        planes = read_float_csv(planes_path)
        if not feature_points or not axis or not planes:
            raise ValueError(f"F01 source artifact is empty for {sequence_id}")
        sequences.append({"metadata": metadata, "feature_points": feature_points, "axis": axis, "planes": planes})
    return sequences


def read_float_csv(path: Path):
    rows = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append({key: coerce_float(value) for key, value in row.items()})
    return rows


def coerce_float(value: str):
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


if __name__ == "__main__":
    raise SystemExit(main())
