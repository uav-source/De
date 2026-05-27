# Day 04 Report

Date: 2026-05-27 CST

## Completed Items

- Implemented the Day 4 minimum scene generator:
  - `src/minibench/scene_generator.py`
- Implemented the CLI generator:
  - `scripts/00_generate_minibench.py`
- Added package marker:
  - `src/minibench/__init__.py`
- Added generator tests:
  - `tests/test_scene_generator.py`
- Generated all four Day 14 minimum geometry sequences:
  - `data/minibench/OC-L0-S01-M1/`
  - `data/minibench/ST-L3-S01-M1/`
  - `data/minibench/CT-L2-S01-M2/`
  - `data/minibench/RT-L4-S01-M1/`

Day 4 did not implement `observations.npz`, `toy_lio`, or plotting.

## Commands Run

The requested `python` commands exposed that `/usr/bin/python` is Python 2.7:

```bash
python scripts/check_env.py
python -m pytest -q
python --version
```

Observed failure:

```text
Python 2.7.18
File "scripts/check_env.py", line 58
  def repo_root() -> Path:
                  ^
SyntaxError: invalid syntax
/usr/bin/python: No module named pytest
```

Fix used for this repository: continue using the Day 2 verified interpreter
`python3`.

Successful commands:

```bash
python3 scripts/check_env.py
python3 -m pytest -q
python3 scripts/00_generate_minibench.py --config configs/minibench/OC-L0-S01-M1.yaml --out data/minibench/OC-L0-S01-M1
python3 scripts/00_generate_minibench.py --config configs/minibench/ST-L3-S01-M1.yaml --out data/minibench/ST-L3-S01-M1
python3 scripts/00_generate_minibench.py --config configs/minibench/CT-L2-S01-M2.yaml --out data/minibench/CT-L2-S01-M2
python3 scripts/00_generate_minibench.py --config configs/minibench/RT-L4-S01-M1.yaml --out data/minibench/RT-L4-S01-M1
find data/minibench -maxdepth 2 -type f | sort
python3 scripts/00_generate_minibench.py --all
```

## Validation Output

Environment check:

```text
Degen-LIO Day 2 environment check
repo_root: /home/lj/Degen-LIO
git_commit: <current HEAD at check time>
random_seed: 42
manifest: /home/lj/Degen-LIO/results/day14/manifests/day02_env_check.json
status: OK
```

Pytest result:

```text
18 passed in 0.22s
```

Single-sequence generation output:

```text
generated OC-L0-S01-M1: frames=200 planes=18 features=240 out=data/minibench/OC-L0-S01-M1
generated ST-L3-S01-M1: frames=240 planes=4 features=320 out=data/minibench/ST-L3-S01-M1
generated CT-L2-S01-M2: frames=220 planes=4 features=320 out=data/minibench/CT-L2-S01-M2
generated RT-L4-S01-M1: frames=260 planes=58 features=428 out=data/minibench/RT-L4-S01-M1
```

Batch generation output:

```text
generated OC-L0-S01-M1: frames=200 planes=18 features=240 out=/home/lj/Degen-LIO/data/minibench/OC-L0-S01-M1
generated ST-L3-S01-M1: frames=240 planes=4 features=320 out=/home/lj/Degen-LIO/data/minibench/ST-L3-S01-M1
generated CT-L2-S01-M2: frames=220 planes=4 features=320 out=/home/lj/Degen-LIO/data/minibench/CT-L2-S01-M2
generated RT-L4-S01-M1: frames=260 planes=58 features=428 out=/home/lj/Degen-LIO/data/minibench/RT-L4-S01-M1
```

## Generated Files

Each sequence directory contains:

- `gt.tum`
- `axis.csv`
- `planes.csv`
- `scene_metadata.json`
- `feature_points.csv`

The required Day 4 files exist for all four sequences:

```text
data/minibench/CT-L2-S01-M2/axis.csv
data/minibench/CT-L2-S01-M2/gt.tum
data/minibench/CT-L2-S01-M2/planes.csv
data/minibench/CT-L2-S01-M2/scene_metadata.json
data/minibench/OC-L0-S01-M1/axis.csv
data/minibench/OC-L0-S01-M1/gt.tum
data/minibench/OC-L0-S01-M1/planes.csv
data/minibench/OC-L0-S01-M1/scene_metadata.json
data/minibench/RT-L4-S01-M1/axis.csv
data/minibench/RT-L4-S01-M1/gt.tum
data/minibench/RT-L4-S01-M1/planes.csv
data/minibench/RT-L4-S01-M1/scene_metadata.json
data/minibench/ST-L3-S01-M1/axis.csv
data/minibench/ST-L3-S01-M1/gt.tum
data/minibench/ST-L3-S01-M1/planes.csv
data/minibench/ST-L3-S01-M1/scene_metadata.json
```

## Degeneracy Geometry Check

| Sequence | Frames | Planes | Features | max abs(nx) | mean abs(nx) | Expected Degeneracy |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `OC-L0-S01-M1` | 200 | 18 | 240 | 1.0 | 0.5248 | low |
| `ST-L3-S01-M1` | 240 | 4 | 320 | 0.0 | 0.0 | high_axis_translation |
| `CT-L2-S01-M2` | 220 | 4 | 320 | 0.0 | 0.0 | medium_local_axis |
| `RT-L4-S01-M1` | 260 | 58 | 428 | 0.0 | 0.0 | high_axis_translation_and_association_ambiguity |

Open control normal distribution check:

```text
OC-L0-S01-M1 mean_norm 0.0000 eig 0.2593,0.3704,0.3704 max_abs_nx 1.0
```

This supports the intended negative control: open-control normals are spread
across directions rather than concentrated in one wall/floor family.

Straight and repetitive tunnel check:

```text
ST-L3-S01-M1 mean_norm 0.0000 eig 0.0000,0.5000,0.5000 max_abs_nx 0.0
RT-L4-S01-M1 mean_norm 0.6583 eig 0.0000,0.5000,0.5000 max_abs_nx 0.0
```

This preserves the intended tunnel degeneracy: structural normals do not
provide direct point-to-plane constraint along the global `x` tunnel axis.

## Output Paths

- Scene generator:
  `/home/lj/Degen-LIO/src/minibench/scene_generator.py`
- CLI generator:
  `/home/lj/Degen-LIO/scripts/00_generate_minibench.py`
- Generator tests:
  `/home/lj/Degen-LIO/tests/test_scene_generator.py`
- Generated data root:
  `/home/lj/Degen-LIO/data/minibench/`
- Day 4 report:
  `/home/lj/Degen-LIO/reports/day04_report.md`

## Failed Or Deferred Items

- `python scripts/check_env.py` and `python -m pytest -q` failed because
  `python` is Python 2.7 on this machine. The working interpreter is `python3`.
  Next fix order if strict `python` compatibility is required:
  1. use `python3` explicitly in all project commands;
  2. optionally create a virtual environment whose `python` resolves to
     Python 3;
  3. do not backport project code to Python 2.
- Day 5 `observations.npz` was not implemented by design.
- Day 7 `toy_lio` was not implemented by design.
- No Day 14 figures were generated by design.

## Tomorrow's Single Most Important Task

Implement the observation simulator and generate `observations.npz` for each
sequence:

- `src/minibench/observation_simulator.py`
- `scripts/01_simulate_observations.py`

The Day 5 acceptance focus is the point-to-plane Jacobian:

```text
J_i = [n_i^T (-R [p_i]_x), n_i^T]
```

and the straight-tunnel information matrix must show weak `x` translation
information before any ODI claims are made.

