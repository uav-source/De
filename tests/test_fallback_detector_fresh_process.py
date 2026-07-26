import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_three_fresh_python_processes_emit_identical_canonical_bytes():
    code = """
from fastlio2_adapter.canonical_detector_output import canonical_json_line
from fastlio2_adapter.offline_detector_determinism import evaluate_frozen_observation
from test_runtime_observation_v3 import v3_record
import sys
sys.stdout.buffer.write(canonical_json_line(evaluate_frozen_observation(v3_record(), record_index=0)))
"""
    environment = dict(os.environ)
    environment.update(
        {
            "PYTHONHASHSEED": "0",
            "OMP_NUM_THREADS": "1",
            "OMP_DYNAMIC": "FALSE",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "VECLIB_MAXIMUM_THREADS": "1",
            "LC_ALL": "C",
            "LANG": "C",
            "TZ": "UTC",
            "PYTHONPATH": os.pathsep.join(
                [str(ROOT / "src"), str(ROOT / "tests")]
            ),
        }
    )
    outputs = [
        subprocess.check_output([sys.executable, "-c", code], env=environment)
        for _ in range(3)
    ]
    assert outputs[0] == outputs[1] == outputs[2]


def test_canonical_process_output_does_not_contain_process_identity():
    source = (
        ROOT / "scripts/69_run_fallback_offline_detector_determinism.py"
    ).read_text(encoding="utf-8")
    assert '"process_id"' not in source
    assert '"hostname"' not in source
