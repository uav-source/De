import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SEQUENCES = [
    "OC-L0-S01-M1",
    "ST-L3-S01-M1",
    "CT-L2-S01-M2",
    "RT-L4-S01-M1",
]


@pytest.fixture(scope="session")
def day14_tmp_pipeline(tmp_path_factory):
    base = tmp_path_factory.mktemp("day14_pipeline")
    data_root = base / "data" / "minibench"
    results = base / "results" / "day14"
    raw = results / "raw"
    metrics = results / "metrics"
    tables = results / "tables"
    raw.mkdir(parents=True, exist_ok=True)
    metrics.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)

    for sequence_id in SEQUENCES:
        run_cmd(
            [
                sys.executable,
                str(ROOT / "scripts/00_generate_minibench.py"),
                "--config",
                str(ROOT / "configs/minibench" / f"{sequence_id}.yaml"),
                "--out",
                str(data_root / sequence_id),
            ],
            base,
        )
        run_cmd(
            [
                sys.executable,
                str(ROOT / "scripts/01_simulate_observations.py"),
                "--seq",
                str(data_root / sequence_id),
                "--config",
                str(ROOT / "configs/detector/odi_default.yaml"),
            ],
            base,
        )

    st_dir = data_root / "ST-L3-S01-M1"
    run_cmd(
        [
            sys.executable,
            str(ROOT / "scripts/02_compute_odi.py"),
            "--seq",
            str(st_dir),
            "--config",
            str(ROOT / "configs/detector/odi_default.yaml"),
            "--out",
            str(raw / "ST-L3-S01-M1_odi.csv"),
        ],
        base,
    )
    run_cmd(
        [
            sys.executable,
            str(ROOT / "scripts/02_run_toy_lio.py"),
            "--seq",
            str(st_dir),
            "--config",
            str(ROOT / "configs/detector/odi_default.yaml"),
            "--out",
            str(raw / "ST-L3-S01-M1_pose_est_toy.tum"),
        ],
        base,
    )

    return {
        "base": base,
        "data_root": data_root,
        "results": results,
        "raw": raw,
        "metrics": metrics,
        "seq": lambda sequence_id: data_root / sequence_id,
        "odi": lambda sequence_id: raw / f"{sequence_id}_odi.csv",
        "toy": lambda sequence_id: raw / f"{sequence_id}_pose_est_toy.tum",
    }


def run_cmd(command, base: Path) -> None:
    env = os.environ.copy()
    env.update(
        {
            "MPLBACKEND": "Agg",
            "PYTHONUNBUFFERED": "1",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "MPLCONFIGDIR": str(base / "mplconfig"),
        }
    )
    try:
        result = subprocess.run(
            command,
            cwd=str(ROOT),
            env=env,
            text=True,
            capture_output=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        print(f"fixture command timed out: {' '.join(map(str, command))}")
        print_tail("stdout", exc.stdout)
        print_tail("stderr", exc.stderr)
        raise
    if result.returncode != 0:
        print(f"fixture command failed rc={result.returncode}: {' '.join(map(str, command))}")
        print_tail("stdout", result.stdout)
        print_tail("stderr", result.stderr)
    result.check_returncode()


def print_tail(label: str, content) -> None:
    if content is None:
        print(f"--- {label} empty ---")
        return
    if isinstance(content, bytes):
        content = content.decode(errors="replace")
    lines = str(content).splitlines()
    print(f"--- {label} last {min(100, len(lines))} lines ---")
    for line in lines[-100:]:
        print(line)


@pytest.fixture(scope="session")
def nested_geometry_outputs(tmp_path_factory):
    sys.path.insert(0, str(ROOT / "src"))
    from eval.synthetic_pipeline_common import generate_or_validate_sequence, load_yaml, make_spec
    from minibench.nested_geometry_observations import simulate_nested_geometry_observations

    base = tmp_path_factory.mktemp("nested_geometry")
    common = load_yaml(ROOT / "configs/redesign/detector_stage2a_common.yaml")
    outputs = {}
    for level, count in common["geometry_levels"].items():
        spec = make_spec(
            common["scene"],
            "geometry",
            level,
            101,
            "quick",
            active_patch_count=int(count),
        )
        sequence_dir = base / level
        generate_or_validate_sequence(sequence_dir, spec)
        outputs[level] = simulate_nested_geometry_observations(
            sequence_dir,
            ROOT / "configs/detector/odi_stage2a.yaml",
            geometry_seed=101,
            sensor_seed=11,
            points_per_square_meter=float(common["geometry_points_per_square_meter"]),
            min_points_per_patch=int(common["geometry_min_points_per_patch"]),
        )
    return outputs
