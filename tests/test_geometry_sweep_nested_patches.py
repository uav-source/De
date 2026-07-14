from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from minibench.scene_generator import generate_master_axial_patch_pool  # noqa: E402


def test_geometry_levels_are_strictly_nested_master_pool_prefixes():
    pool = generate_master_axial_patch_pool(202, 30.0, 4.0, 3.0, 16)
    ids = {count: {patch.patch_id for patch in pool[:count]} for count in [12, 7, 3, 1]}
    assert ids[1] < ids[3] < ids[7] < ids[12]
    assert [patch.support_strength for patch in pool] == sorted(
        [patch.support_strength for patch in pool], reverse=True
    )
