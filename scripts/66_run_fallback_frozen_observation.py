#!/usr/bin/env python3
"""Run the one authorized Quick Shack compact observation export replay."""

from __future__ import annotations

import argparse
import importlib.util
import json
import signal
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastlio2_adapter.in_call_immutability import validate_status  # noqa: E402


RUN_ID = "multihyp_fallback_frozen_observation_v1"
SEQUENCE_ID = "avia_quick_shack"
REPEAT_ID = 1
ENGINEERING_MODE = "FALLBACK_FROZEN_OBSERVATION_EXPORT"
FAST_RUNTIME_MODE = "COMPACT_EXPORT"
PAYLOAD_PROFILE = "DETECTOR_MINIMAL_V1"
IN_CALL_STATUS_SERVICE = "/harmful_bias/in_call_immutability_status"
TAP_BUFFER_CAPACITY = 1024


def load_v5_runner() -> Any:
    path = ROOT / "scripts/60_run_single_startup_sync_v5.py"
    spec = importlib.util.spec_from_file_location(
        "fallback_frozen_observation_v5_transport", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load frozen V5 transport runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def configure_transport(module: Any) -> None:
    module.RUN_ID = RUN_ID
    module.SEQUENCES = (SEQUENCE_ID,)
    module.REPEATS = (REPEAT_ID,)
    module.MODE = FAST_RUNTIME_MODE

    original_run_command = module.run_command

    def run_command(
        command: Sequence[str],
        *,
        environment: Mapping[str, str],
        output: Path | None = None,
        check: bool = True,
    ) -> Any:
        values = list(command)
        if len(values) >= 2 and Path(values[1]).name == (
            "53_validate_runtime_audit_products.py"
        ):
            values[1] = str(
                ROOT / "scripts/67_validate_frozen_observation.py"
            )
            values.insert(2, "--runtime-products-only")
        result = original_run_command(
            values,
            environment=environment,
            output=output,
            check=check,
        )
        if values[:3] == [
            "rosparam",
            "set",
            "/harmful_bias/end_of_stream_audit_enabled",
        ]:
            for key, value in (
                (
                    "/harmful_bias/in_call_immutability_audit_enabled",
                    "true",
                ),
                (
                    "/harmful_bias/readonly_tap_buffer_capacity",
                    str(TAP_BUFFER_CAPACITY),
                ),
            ):
                original_run_command(
                    ["rosparam", "set", key, value],
                    environment=environment,
                )
        return result

    module.run_command = run_command
    original_shutdown = module.graceful_shutdown

    def graceful_shutdown(
        roslaunch: Any,
        *,
        environment: Mapping[str, str],
        run_dir: Path,
    ) -> dict[str, Any]:
        poll = module.bounded_trigger_call(
            IN_CALL_STATUS_SERVICE,
            environment=environment,
            timeout_sec=5.0,
        )
        module.atomic_json(
            run_dir / "in_call_immutability_service_evidence.json",
            dict(poll.evidence),
        )
        if (
            poll.snapshot is None
            or poll.evidence.get("service_success") is not True
        ):
            raise module.RunFailure(
                "RUNTIME_PRODUCT_MISSING",
                "in-call immutability status service failed",
            )
        status = validate_status(poll.snapshot)
        module.atomic_json(run_dir / "in_call_immutability_status.json", status)
        if status["audited_call_count"] <= 0:
            raise module.RunFailure(
                "RUNTIME_PRODUCT_MISSING",
                "in-call audit observed no valid tap calls",
            )
        return original_shutdown(
            roslaunch,
            environment=environment,
            run_dir=run_dir,
        )

    module.graceful_shutdown = graceful_shutdown


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--endpoint-contract", required=True, type=Path)
    parser.add_argument("--run-lock", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.run_id != RUN_ID:
        raise SystemExit(f"ERROR: only {RUN_ID} is allowed")
    module = load_v5_runner()
    configure_transport(module)
    transport_args = argparse.Namespace(
        run_id=RUN_ID,
        sequence_id=SEQUENCE_ID,
        repeat_id=REPEAT_ID,
        run_root=args.run_root,
        endpoint_contract=args.endpoint_contract,
        run_lock=args.run_lock,
    )

    def interrupt_runner(_signum: int, _frame: object) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, interrupt_runner)
    signal.signal(signal.SIGTERM, interrupt_runner)
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    try:
        metadata = module.execute(transport_args)
        print(
            json.dumps(
                {
                    "engineering_mode": ENGINEERING_MODE,
                    "fast_runtime_mode": FAST_RUNTIME_MODE,
                    "payload_profile": PAYLOAD_PROFILE,
                    "metadata": metadata,
                },
                sort_keys=True,
            )
        )
        return 0
    except KeyboardInterrupt:
        return 130
    except module.RunFailure as error:
        print(f"ERROR[{error.classification}]: {error}", file=sys.stderr)
        return 30
    finally:
        if module._ACTIVE_HEARTBEAT is not None:
            module._ACTIVE_HEARTBEAT.stop()
            module._ACTIVE_HEARTBEAT = None


if __name__ == "__main__":
    raise SystemExit(main())
