from pathlib import Path
from eval.stage2_failure_day12_figure_qc import audit_plot_code

ROOT = Path(__file__).resolve().parents[1]


def test_plot_source_static_audit_passes():
    assert audit_plot_code(ROOT / "src/eval/stage2_failure_day12_figures.py")["audit_pass"] is True


def test_nonzero_reference_line_is_rejected(tmp_path):
    source = tmp_path / "plot.py"
    source.write_text("def f(ax):\n    ax.axhline(1.0)\n", encoding="utf-8")
    assert audit_plot_code(source)["audit_pass"] is False


def test_random_plot_displacement_is_rejected(tmp_path):
    source = tmp_path / "plot.py"
    source.write_text("def f():\n    return np.random.uniform()\n", encoding="utf-8")
    assert audit_plot_code(source)["audit_pass"] is False


def test_day12_pipeline_has_no_estimator_entry_point():
    for filename in (
        "stage2_failure_day12.py", "stage2_failure_day12_input_audit.py",
        "stage2_failure_day12_plot_data.py", "stage2_failure_day12_figures.py",
    ):
        source = (ROOT / "src/eval" / filename).read_text(encoding="utf-8")
        assert "run_map_lio" not in source
