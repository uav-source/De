from pathlib import Path
from PIL import Image
from eval.stage2_failure_day12_figure_qc import audit_figures


def test_blank_and_missing_figures_fail_qc(tmp_path):
    figures = tmp_path / "figures"
    figures.mkdir()
    Image.new("RGB", (100, 100), "white").save(figures / "day12_fig01_innovation_timeline.png", dpi=(300, 300))
    result = audit_figures(tmp_path)
    assert result["figure_qc_failure_count"] > 0


def test_extra_scientific_image_is_counted(tmp_path):
    figures = tmp_path / "figures"
    figures.mkdir()
    Image.new("RGB", (10, 10), "black").save(figures / "extra.png")
    assert audit_figures(tmp_path)["unexpected_figure_count"] == 1


def test_forbidden_scientific_output_directory_fails_qc(tmp_path):
    figures = tmp_path / "figures"
    figures.mkdir()
    (tmp_path / "thresholds").mkdir()
    audit = audit_figures(tmp_path)
    assert audit["forbidden_output_count"] == 1
    assert audit["audit_pass"] is False
