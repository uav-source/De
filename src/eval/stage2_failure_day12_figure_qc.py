"""Image, static-code, and reproducibility audits for Day 12 figures."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from PIL import Image, ImageStat

from eval.stage2_failure_day12_figures import FIGURE_NAMES


def pixel_sha256(path: Path) -> str:
    with Image.open(path) as image:
        digest = hashlib.sha256()
        digest.update(image.mode.encode("ascii"))
        digest.update(str(image.size).encode("ascii"))
        digest.update(image.tobytes())
        return digest.hexdigest()


def audit_figures(output_dir: Path, png_dpi: int = 300) -> Mapping[str, Any]:
    output_dir = Path(output_dir)
    figures = output_dir / "figures"
    expected_png = {f"{name}.png" for name in FIGURE_NAMES}
    expected_pdf = {f"{name}.pdf" for name in FIGURE_NAMES}
    actual_png = {path.name for path in figures.glob("*.png")}
    actual_pdf = {path.name for path in figures.glob("*.pdf")}
    other = [
        path.name for path in figures.iterdir()
        if path.is_file() and path.suffix.lower() not in {".png", ".pdf"}
    ] if figures.is_dir() else []
    records = []
    failures = 0
    for name in FIGURE_NAMES:
        png = figures / f"{name}.png"
        pdf = figures / f"{name}.pdf"
        png_pass = png.is_file() and png.stat().st_size > 20 * 1024
        width = height = 0
        dpi = (0.0, 0.0)
        variance = 0.0
        pixel_hash = ""
        if png_pass:
            try:
                with Image.open(png) as image:
                    image.load()
                    width, height = image.size
                    dpi = tuple(float(value) for value in image.info.get("dpi", (0.0, 0.0)))
                    variance = float(sum(ImageStat.Stat(image.convert("L")).var))
                pixel_hash = pixel_sha256(png)
                png_pass = width > 0 and height > 0 and variance > 0.0 and all(abs(value - png_dpi) <= 2.0 for value in dpi)
            except (OSError, ValueError):
                png_pass = False
        pdf_pass = pdf.is_file() and pdf.stat().st_size > 10 * 1024 and pdf.read_bytes()[:4] == b"%PDF"
        passed = bool(png_pass and pdf_pass)
        failures += int(not passed)
        records.append({
            "figure_id": name, "png_path": str(png), "pdf_path": str(pdf),
            "png_size_bytes": png.stat().st_size if png.is_file() else 0,
            "pdf_size_bytes": pdf.stat().st_size if pdf.is_file() else 0,
            "width": width, "height": height, "dpi": list(dpi),
            "pixel_variance": variance, "pixel_sha256": pixel_hash,
            "png_pass": bool(png_pass), "pdf_pass": bool(pdf_pass), "pass": passed,
        })
    unexpected = len((actual_png - expected_png) | (actual_pdf - expected_pdf)) + len(other)
    failures += int(actual_png != expected_png) + int(actual_pdf != expected_pdf) + int(bool(other))
    forbidden_paths = [
        output_dir / name
        for name in (
            "thresholds", "roc", "alerts", "stage3", "extra_figures",
            "selected_statistic.json",
        )
        if (output_dir / name).exists()
    ]
    failures += len(forbidden_paths)
    return {
        "schema_version": "stage2_failure_day12_figure_qc_v2", "figures": records,
        "png_figure_count": len(actual_png), "pdf_figure_count": len(actual_pdf),
        "unexpected_figure_count": unexpected, "figure_qc_failure_count": failures,
        "forbidden_output_count": len(forbidden_paths),
        "forbidden_outputs": [str(path) for path in forbidden_paths],
        "audit_pass": failures == 0,
    }


def audit_plot_code(source_path: Path) -> Mapping[str, Any]:
    source = Path(source_path).read_text(encoding="utf-8")
    tree = ast.parse(source)
    failures = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Name, ast.arg)):
            name = node.id if isinstance(node, ast.Name) else node.arg
            if "thresh" in name.lower():
                failures.append(f"forbidden variable: {name}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "axhline":
                if not node.args or not isinstance(node.args[0], (ast.Constant, ast.Num)) or float(getattr(node.args[0], "value", getattr(node.args[0], "n", 1.0))) != 0.0:
                    failures.append("nonzero axhline")
            if node.func.attr == "axvline":
                failures.append("axvline is forbidden")
    for token in ("sklearn", "roc_curve", "np.random", "random."):
        if token in source:
            failures.append(f"forbidden source token: {token}")
    return {
        "schema_version": "stage2_failure_day12_plot_code_static_audit_v2",
        "source_path": str(source_path), "failure_count": len(failures),
        "failures": failures, "audit_pass": not failures,
    }


def compare_reproduction(main_dir: Path, second_dir: Path) -> Mapping[str, Any]:
    main_dir, second_dir = Path(main_dir), Path(second_dir)
    csv_equal = all(
        (main_dir / "figure_data" / f"{name}.csv").read_bytes()
        == (second_dir / "figure_data" / f"{name}.csv").read_bytes()
        for name in FIGURE_NAMES
    )
    pixel_equal = all(
        pixel_sha256(main_dir / "figures" / f"{name}.png")
        == pixel_sha256(second_dir / "figures" / f"{name}.png")
        for name in FIGURE_NAMES
    )
    size_equal = all(
        Image.open(main_dir / "figures" / f"{name}.png").size
        == Image.open(second_dir / "figures" / f"{name}.png").size
        for name in FIGURE_NAMES
    )
    summary_equal = (main_dir / "day12_descriptive_summary.csv").read_bytes() == (second_dir / "day12_descriptive_summary.csv").read_bytes()
    captions_equal = (main_dir / "figure_captions.md").read_bytes() == (second_dir / "figure_captions.md").read_bytes()
    pdf_ok = all(
        (second_dir / "figures" / f"{name}.pdf").is_file()
        and (second_dir / "figures" / f"{name}.pdf").stat().st_size > 10 * 1024
        for name in FIGURE_NAMES
    )
    return {
        "schema_version": "stage2_failure_day12_reproducibility_v2",
        "repro_plot_data_byte_identical": csv_equal,
        "repro_png_pixel_hash_identical": pixel_equal and size_equal,
        "repro_summary_byte_identical": summary_equal,
        "repro_captions_byte_identical": captions_equal,
        "repro_pdf_valid": pdf_ok,
        "audit_pass": bool(csv_equal and pixel_equal and size_equal and summary_equal and captions_equal and pdf_ok),
    }
