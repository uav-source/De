from pathlib import Path
from PIL import Image

from eval.stage2_failure_day12_figure_qc import compare_reproduction
from eval.stage2_failure_day12_figures import FIGURE_NAMES
from eval.stage2_failure_day12_plot_data import build_all_plot_data, read_merged_rows
from eval.stage2_failure_day12_schema import FIGURE_DATA_FIELDS, write_csv

ROOT = Path(__file__).resolve().parents[1]
MERGED = ROOT / "results/stage2_failure_analysis/day11b_replay/stage2_failure_day11b_replay_v2/replay_frame_diagnostics_merged.csv"


def test_two_plot_data_writes_are_byte_identical(tmp_path):
    fields, rows = read_merged_rows(MERGED)
    data = build_all_plot_data(fields, rows)
    for name, columns in FIGURE_DATA_FIELDS.items():
        first, second = tmp_path / "a" / f"{name}.csv", tmp_path / "b" / f"{name}.csv"
        write_csv(first, data[name], columns)
        write_csv(second, data[name], columns)
        assert first.read_bytes() == second.read_bytes()


def _fake_render(root: Path) -> None:
    (root / "figure_data").mkdir(parents=True)
    (root / "figures").mkdir()
    for name in FIGURE_NAMES:
        (root / "figure_data" / f"{name}.csv").write_text("x\n1\n", encoding="utf-8")
        Image.new("RGB", (12, 12), (20, 40, 60)).save(root / "figures" / f"{name}.png")
        (root / "figures" / f"{name}.pdf").write_bytes(b"%PDF" + b"x" * (11 * 1024))
    (root / "day12_descriptive_summary.csv").write_text("x\n1\n", encoding="utf-8")
    (root / "figure_captions.md").write_text("caption\n", encoding="utf-8")


def test_reproduction_rejects_plot_data_byte_change(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    _fake_render(first); _fake_render(second)
    target = second / "figure_data" / f"{FIGURE_NAMES[0]}.csv"
    target.write_text("x\n2\n", encoding="utf-8")
    audit = compare_reproduction(first, second)
    assert audit["repro_plot_data_byte_identical"] is False
    assert audit["audit_pass"] is False


def test_reproduction_rejects_png_pixel_change(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    _fake_render(first); _fake_render(second)
    Image.new("RGB", (12, 12), (20, 40, 61)).save(second / "figures" / f"{FIGURE_NAMES[0]}.png")
    audit = compare_reproduction(first, second)
    assert audit["repro_png_pixel_hash_identical"] is False
    assert audit["audit_pass"] is False
