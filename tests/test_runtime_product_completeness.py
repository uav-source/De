from __future__ import annotations

import importlib.util
import json
import struct
import sys
import threading
import time
from pathlib import Path

import pytest

from test_runtime_binary_conversion import framed, runtime_payload


ROOT = Path(__file__).resolve().parents[1]


def load_validator():
    spec = importlib.util.spec_from_file_location(
        "runtime_product_validator",
        ROOT / "scripts/53_validate_runtime_audit_products.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def fixture(run_dir: Path):
    run_dir.mkdir()
    runtime = run_dir / "runtime_audit_v2.bin"
    runtime.write_bytes(framed(b"HBRTAUD2", 2, runtime_payload()))
    (run_dir / "run_summary.json").write_text(
        json.dumps({"runtime_audit_record_count": 1}) + "\n"
    )
    (run_dir / "final_map_summary.json").write_text(
        json.dumps({"final_map_point_count": 0, "final_map_checksum": 1}) + "\n"
    )
    (run_dir / "tap_export_summary.json").write_text(
        json.dumps(
            {
                "runtime_mode": "AUDIT_ONLY",
                "tap_enabled": False,
                "binary_observation_record_count": 0,
            }
        )
        + "\n"
    )
    return runtime


def test_complete_runtime_products_and_trailer_pass(tmp_path):
    validator = load_validator()
    run_dir = tmp_path / "run"
    fixture(run_dir)
    result = validator.validate_runtime_products(run_dir, run_dir / "converted")
    assert result["runtime_product_pass"] is True
    assert result["runtime_binary_trailer_pass"] is True
    tap = json.loads((run_dir / "tap_export_summary.json").read_text())
    assert tap["mode"] == "AUDIT_ONLY"
    assert tap["observation_record_count"] == 0


@pytest.mark.parametrize(
    ("mutation", "classification"),
    [
        ("missing_trailer", "RUNTIME_BINARY_TRAILER_MISSING"),
        ("record_checksum", "RUNTIME_BINARY_CHECKSUM_FAILURE"),
        ("file_checksum", "RUNTIME_BINARY_CHECKSUM_FAILURE"),
        ("record_count", "RUNTIME_BINARY_RECORD_COUNT_MISMATCH"),
        ("extra_bytes", "RUNTIME_BINARY_EXTRA_BYTES"),
    ],
)
def test_binary_corruption_fails_closed(tmp_path, mutation, classification):
    validator = load_validator()
    run_dir = tmp_path / mutation
    runtime = fixture(run_dir)
    data = bytearray(runtime.read_bytes())
    if mutation == "missing_trailer":
        del data[-24:]
    elif mutation == "record_checksum":
        data[24] ^= 1
    elif mutation == "file_checksum":
        data[-1] ^= 1
    elif mutation == "record_count":
        data[-16] = 2
    else:
        converter = validator._load_converter()
        prefix = bytes(data[:-24]) + b"x"
        data = bytearray(
            prefix
            + b"HBRENDV1"
            + bytes(data[-16:-8])
            + struct.pack("<Q", converter.fnv1a64(prefix))
        )
    runtime.write_bytes(data)
    with pytest.raises(validator.RuntimeProductError) as caught:
        validator.validate_runtime_products(run_dir, run_dir / "converted")
    assert caught.value.classification == classification


def test_missing_summary_and_nonzero_audit_observation_fail(tmp_path):
    validator = load_validator()
    run_dir = tmp_path / "missing"
    fixture(run_dir)
    (run_dir / "final_map_summary.json").unlink()
    with pytest.raises(validator.RuntimeProductError) as caught:
        validator.validate_runtime_products(run_dir, run_dir / "converted")
    assert caught.value.classification == "RUNTIME_PRODUCT_MISSING"

    run_dir = tmp_path / "observation"
    fixture(run_dir)
    tap = json.loads((run_dir / "tap_export_summary.json").read_text())
    tap["binary_observation_record_count"] = 1
    (run_dir / "tap_export_summary.json").write_text(json.dumps(tap))
    with pytest.raises(validator.RuntimeProductError):
        validator.validate_runtime_products(run_dir, run_dir / "converted")


def test_stability_wait_does_not_parse_while_file_is_growing(tmp_path):
    validator = load_validator()
    path = tmp_path / "growing"
    path.write_bytes(b"a")

    def grow():
        time.sleep(0.02)
        with path.open("ab") as stream:
            stream.write(b"b")

    thread = threading.Thread(target=grow)
    thread.start()
    result = validator.wait_for_stable_products(
        [path], poll_interval=0.01, stable_polls=4, timeout=1.0
    )
    thread.join()
    assert result["stable"] is True
    assert result["files"][0]["size_bytes"] == 2
