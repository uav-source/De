import shutil
from pathlib import Path

from PIL import Image

from eval.stage2_failure_day12_figure_qc import audit_v2_v3_figure_changes
from eval.stage2_failure_day12_figures import FIGURE_NAMES


ROOT = Path(__file__).resolve().parents[1]
V2 = ROOT / "results/stage2_failure_analysis/day12_figures/stage2_failure_day12_figures_v2"


def _copy_pngs(target: Path) -> None:
    (target / "figures").mkdir(parents=True)
    for name in FIGURE_NAMES:
        shutil.copy2(V2 / "figures" / f"{name}.png", target / "figures" / f"{name}.png")


def _change_pixel(path: Path) -> None:
    with Image.open(path) as source:
        image = source.convert("RGBA")
    pixel = image.getpixel((0, 0))
    image.putpixel((0, 0), ((pixel[0] + 1) % 256, pixel[1], pixel[2], pixel[3]))
    image.save(path)


def test_expected_figure3_and_figure4_pixel_changes_pass(tmp_path):
    v3 = tmp_path / "v3"
    _copy_pngs(v3)
    _change_pixel(v3 / "figures" / f"{FIGURE_NAMES[2]}.png")
    _change_pixel(v3 / "figures" / f"{FIGURE_NAMES[3]}.png")
    assert audit_v2_v3_figure_changes(V2, v3)["audit_pass"] is True


def test_figure1_or_figure2_pixel_change_is_rejected(tmp_path):
    for index in (0, 1):
        v3 = tmp_path / f"v3_{index}"
        _copy_pngs(v3)
        for changed in (2, 3, index):
            _change_pixel(v3 / "figures" / f"{FIGURE_NAMES[changed]}.png")
        audit = audit_v2_v3_figure_changes(V2, v3)
        assert audit["figures"][index]["change_scope_pass"] is False
        assert audit["audit_pass"] is False


def test_figure3_or_figure4_without_pixel_change_is_rejected(tmp_path):
    for unchanged in (2, 3):
        v3 = tmp_path / f"v3_{unchanged}"
        _copy_pngs(v3)
        changed = 3 if unchanged == 2 else 2
        _change_pixel(v3 / "figures" / f"{FIGURE_NAMES[changed]}.png")
        audit = audit_v2_v3_figure_changes(V2, v3)
        assert audit["figures"][unchanged]["change_scope_pass"] is False
        assert audit["audit_pass"] is False
