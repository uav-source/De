from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from minibench.nested_geometry_observations import audit_nested_geometry_levels  # noqa: E402


def test_shared_geometry_measurements_have_identical_points_normals_and_noise(nested_geometry_outputs):
    audit = audit_nested_geometry_levels(nested_geometry_outputs)
    assert audit["measurement_sets_strictly_nested"] is True
    assert audit["shared_measurements_identical"] is True
