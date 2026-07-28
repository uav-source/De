import numpy as np

from backend_phase_a_v1_1_test_support import ROOT, fake_result, fixture_points
from zero_perturbation.backend_phase_a_metrics import OPEN3D_BACKEND, PCL_BACKEND
from zero_perturbation.backend_phase_a_v1_1 import execute_fixture_chain


def test_runner_passes_identical_canonical_input_to_both_backends(tmp_path):
    seen = {}

    def hook(backend):
        base = fake_result(backend)

        def run(**arguments):
            seen[backend] = {
                "source": np.array(arguments["source"], copy=True),
                "target": np.array(arguments["target"], copy=True),
                "reference": np.array(arguments["reference"], copy=True),
                "checksums": dict(arguments["checksums"]),
            }
            return base(**arguments)

        return run

    manifest = execute_fixture_chain(
        root=ROOT,
        points=fixture_points(),
        output_dir=tmp_path,
        backend_hooks={OPEN3D_BACKEND: hook(OPEN3D_BACKEND), PCL_BACKEND: hook(PCL_BACKEND)},
    )
    assert np.array_equal(seen[OPEN3D_BACKEND]["source"], seen[PCL_BACKEND]["source"])
    assert np.array_equal(seen[OPEN3D_BACKEND]["target"], seen[PCL_BACKEND]["target"])
    assert np.array_equal(seen[OPEN3D_BACKEND]["reference"], seen[PCL_BACKEND]["reference"])
    assert seen[OPEN3D_BACKEND]["checksums"] == seen[PCL_BACKEND]["checksums"]
    assert manifest["backend_input_checksum_mismatch_count"] == 0

