#!/usr/bin/env python3
"""Run the Day 14 reproduction steps with per-step logs and timeouts."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Sequence


ROOT = Path(__file__).resolve().parents[1]
SEQUENCES = [
    "OC-L0-S01-M1",
    "ST-L3-S01-M1",
    "CT-L2-S01-M2",
    "RT-L4-S01-M1",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--timestamp", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--results", type=Path, default=ROOT / "results/day14")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    results_dir = args.results if args.results.is_absolute() else ROOT / args.results
    clean_generated(results_dir)

    manifest_dir = results_dir / "manifests"
    log_dir = manifest_dir / "logs" / args.run_id
    log_dir.mkdir(parents=True, exist_ok=True)
    command_log = manifest_dir / f"day14_commands_{args.run_id}.txt"
    step_records_path = manifest_dir / f"day14_step_records_{args.run_id}.json"
    command_log.write_text("", encoding="utf-8")

    env = reproduction_env(manifest_dir / f"mplconfig_{args.run_id}")
    records: List[Dict[str, object]] = []
    start_monotonic = time.monotonic()

    steps = reproduction_steps()
    for idx, (name, command) in enumerate(steps, start=1):
        record = run_step(
            idx,
            name,
            command,
            timeout_seconds=args.timeout_seconds,
            command_log=command_log,
            log_dir=log_dir,
            env=env,
        )
        records.append(record)
        write_json(step_records_path, records)
        if record["timeout"]:
            print_step_tail(record)
            return 124
        if record["return_code"] != 0:
            print_step_tail(record)
            return int(record["return_code"])

    runtime_seconds = time.monotonic() - start_monotonic
    manifest_command = [
        "python3",
        "scripts/07_reproduction_manifest.py",
        "--results",
        "results/day14",
        "--commands-file",
        str(command_log.relative_to(ROOT)),
        "--run-id",
        args.run_id,
        "--timestamp",
        args.timestamp,
        "--runtime-seconds",
        f"{runtime_seconds:.3f}",
        "--status",
        "OK",
    ]
    record = run_step(
        len(steps) + 1,
        "07_reproduction_manifest",
        manifest_command,
        timeout_seconds=args.timeout_seconds,
        command_log=command_log,
        log_dir=log_dir,
        env=env,
    )
    records.append(record)
    write_json(step_records_path, records)
    if record["timeout"]:
        print_step_tail(record)
        return 124
    if record["return_code"] != 0:
        print_step_tail(record)
        return int(record["return_code"])

    print(f"Day 14 reproduction complete: run_id={args.run_id} runtime_seconds={runtime_seconds:.3f}")
    print(f"step records: {step_records_path}")
    return 0


def reproduction_steps() -> List[tuple[str, List[str]]]:
    return [
        ("check_env", ["python3", "scripts/check_env.py"]),
        ("00_generate_minibench", ["python3", "scripts/00_generate_minibench.py", "--all"]),
        (
            "01_simulate_observations",
            ["python3", "scripts/01_simulate_observations.py", "--all", "--config", "configs/detector/odi_default.yaml"],
        ),
        (
            "02_compute_odi",
            ["python3", "scripts/02_compute_odi.py", "--all", "--config", "configs/detector/odi_default.yaml"],
        ),
        (
            "02_run_toy_lio",
            ["python3", "scripts/02_run_toy_lio.py", "--all", "--config", "configs/detector/odi_default.yaml"],
        ),
        (
            "03_eval_metrics",
            ["python3", "scripts/03_eval_metrics.py", "--all", "--config", "configs/detector/odi_default.yaml"],
        ),
        ("05_metric_validity", ["python3", "scripts/05_metric_validity.py", "--config", "configs/detector/odi_default.yaml"]),
        ("04_plot_day14", ["python3", "scripts/04_plot_day14.py", "--results", "results/day14", "--out", "results/day14/figures"]),
        (
            "06_sensitivity",
            [
                "python3",
                "scripts/06_sensitivity.py",
                "--config",
                "configs/detector/odi_default.yaml",
                "--results",
                "results/day14",
                "--out",
                "results/day14/tables",
                "--figures-out",
                "results/day14/figures",
            ],
        ),
    ]


def clean_generated(results_dir: Path) -> None:
    for dirname in ["raw", "metrics", "tables", "figures", "manifests"]:
        directory = results_dir / dirname
        directory.mkdir(parents=True, exist_ok=True)
        for path in directory.iterdir():
            if path.name in {".gitkeep", "manifest_template.json"}:
                continue
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    for seq in SEQUENCES:
        seq_dir = ROOT / "data/minibench" / seq
        if seq_dir.exists():
            shutil.rmtree(seq_dir)


def reproduction_env(mpl_config_dir: Path) -> Dict[str, str]:
    mpl_config_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": str(mpl_config_dir),
            "PYTHONUNBUFFERED": "1",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
        }
    )
    return env


def run_step(
    index: int,
    name: str,
    command: Sequence[str],
    *,
    timeout_seconds: int,
    command_log: Path,
    log_dir: Path,
    env: Dict[str, str],
) -> Dict[str, object]:
    stdout_path = log_dir / f"{index:02d}_{name}.stdout.log"
    stderr_path = log_dir / f"{index:02d}_{name}.stderr.log"
    start_time = utc_now()
    start = time.monotonic()
    command_text = " ".join(command)
    append_line(command_log, f"RUN step={name} timeout={timeout_seconds}s command={command_text}")
    print(f"+ [{name}] timeout={timeout_seconds}s {command_text}", flush=True)

    timeout = False
    return_code = 0
    stdout = ""
    stderr = ""
    try:
        completed = subprocess.run(
            list(command),
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        return_code = int(completed.returncode)
    except subprocess.TimeoutExpired as exc:
        timeout = True
        return_code = 124
        stdout = decode_output(exc.stdout)
        stderr = decode_output(exc.stderr)
        append_line(command_log, f"TIMEOUT step={name} after={timeout_seconds}s command={command_text}")
    except OSError as exc:
        return_code = 127
        stderr = str(exc)

    stdout_path.write_text(stdout, encoding="utf-8")
    stderr_path.write_text(stderr, encoding="utf-8")
    if stdout:
        print(stdout, end="" if stdout.endswith("\n") else "\n", flush=True)
    if stderr:
        print(stderr, end="" if stderr.endswith("\n") else "\n", file=sys.stderr, flush=True)

    end_time = utc_now()
    runtime = time.monotonic() - start
    if timeout:
        status = "TIMEOUT"
    elif return_code == 0:
        status = "OK"
    else:
        status = "FAILED"
    append_line(command_log, f"{status} step={name} return_code={return_code} runtime_seconds={runtime:.3f}")
    return {
        "step_name": name,
        "command": list(command),
        "start_time": start_time,
        "end_time": end_time,
        "runtime_seconds": runtime,
        "return_code": return_code,
        "timeout": timeout,
        "stdout_log_path": relative_to_root(stdout_path),
        "stderr_log_path": relative_to_root(stderr_path),
    }


def print_step_tail(record: Dict[str, object]) -> None:
    print(f"ERROR: step failed: {record['step_name']}", file=sys.stderr)
    for key in ["stdout_log_path", "stderr_log_path"]:
        path = ROOT / str(record[key])
        print(f"--- {key} last 100 lines: {path} ---", file=sys.stderr)
        if path.exists():
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            for line in lines[-100:]:
                print(line, file=sys.stderr)
        else:
            print("(missing)", file=sys.stderr)


def decode_output(output) -> str:
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode(errors="replace")
    return str(output)


def append_line(path: Path, line: str) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def write_json(path: Path, records: Sequence[Dict[str, object]]) -> None:
    path.write_text(json.dumps(list(records), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def relative_to_root(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
