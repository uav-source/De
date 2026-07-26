import hashlib
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

from capture_range.day2_development_protocol import (
    canonical_array_payload,
    canonical_array_sha256,
    canonical_bytes,
    canonical_seed,
    canonical_sha256,
    canonical_unit_interval,
)


ROOT = Path(__file__).resolve().parents[1]


def test_recursive_canonical_encoding_is_sorted_utf8_and_float_hex():
    value = {"中文": [1.5, -0.0], "a": {"z": np.float64(0.25)}}
    expected = (
        '{"a":{"z":"0x1.0000000000000p-2"},'
        '"中文":["0x1.8000000000000p+0","0x0.0p+0"]}'
    ).encode("utf-8")

    assert canonical_bytes(value) == expected
    assert canonical_sha256(value) == hashlib.sha256(expected).hexdigest()
    assert canonical_sha256(value) == canonical_sha256(dict(reversed(value.items())))
    digest = hashlib.sha256(expected).digest()
    assert canonical_seed(value) == int.from_bytes(digest[:16], "big")
    assert canonical_unit_interval(value) == int.from_bytes(digest[:8], "big") / 2**64


def test_canonical_array_payload_uses_dtype_shape_and_c_order_values():
    array = np.array([[-0.0, 1.5]], dtype="<f8")
    expected = {
        "dtype": "<f8",
        "shape": [1, 2],
        "values": [-0.0, 1.5],
    }

    assert canonical_array_payload(array) == expected
    assert canonical_array_sha256(array) == canonical_sha256(expected)
    assert b'"values":["0x0.0p+0","0x1.8000000000000p+0"]' in canonical_bytes(
        array
    )


def test_canonical_hash_is_identical_in_a_fresh_process():
    payload = {"label": "跨进程", "nested": [3, -0.0, {"x": 0.1}]}
    local = canonical_sha256(payload)
    code = (
        "from capture_range.day2_development_protocol import canonical_sha256;"
        "print(canonical_sha256({'nested':[3,-0.0,{'x':0.1}],'label':'跨进程'}))"
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")
    remote = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    assert remote == local
