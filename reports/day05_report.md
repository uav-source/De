# Day 05 Report

Date: 2026-05-27 CST

## Completed Items

- Implemented Day 5 observation simulator:
  - `src/minibench/observation_simulator.py`
- Implemented CLI script:
  - `scripts/01_simulate_observations.py`
- Added tests:
  - `tests/test_observation_simulator.py`
- Generated `observations.npz` for all four Day 14 minimum sequences.
- Generated sanity summary table:
  - `results/day14/tables/day05_observation_summary.csv`

Day 5 did not implement ODI, toy LIO, or plotting.

## CT Risk Fix

The Day 4 risk was addressed directly:

- `CT-L2-S01-M2/planes.csv` still contains only representative fixed planes.
- Day 5 does not use those fixed CT normals for all frames.
- For CT, the simulator constructs local framewise planes from `axis.csv`:

```text
tangent = normalize(axis)
side_normal = normalize([-ay, ax, 0])
left/right wall normals = +/- side_normal
floor/ceiling normals = [0, 0, +/-1]
```

The test suite checks that CT local side normals are orthogonal to the local
axis and vary between the first and last frame.

## Commands Run

```bash
git status --short
git rev-parse --short HEAD
find data/minibench -maxdepth 2 -type f | sort
sed -n '1,240p' src/minibench/scene_generator.py
sed -n '241,520p' src/minibench/scene_generator.py
chmod +x scripts/01_simulate_observations.py
python3 scripts/check_env.py
python3 -m pytest -q
python3 scripts/01_simulate_observations.py --seq data/minibench/OC-L0-S01-M1 --config configs/detector/odi_default.yaml
python3 scripts/01_simulate_observations.py --seq data/minibench/ST-L3-S01-M1 --config configs/detector/odi_default.yaml
python3 scripts/01_simulate_observations.py --seq data/minibench/CT-L2-S01-M2 --config configs/detector/odi_default.yaml
python3 scripts/01_simulate_observations.py --seq data/minibench/RT-L4-S01-M1 --config configs/detector/odi_default.yaml
python3 scripts/01_simulate_observations.py --all --config configs/detector/odi_default.yaml
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
27 passed in 1.11s
```

Observation generation:

```text
generated observations: seq=OC-L0-S01-M1 frames=200 points_per_frame=360 out=data/minibench/OC-L0-S01-M1/observations.npz
generated observations: seq=ST-L3-S01-M1 frames=240 points_per_frame=320 out=data/minibench/ST-L3-S01-M1/observations.npz
generated observations: seq=CT-L2-S01-M2 frames=220 points_per_frame=320 out=data/minibench/CT-L2-S01-M2/observations.npz
generated observations: seq=RT-L4-S01-M1 frames=260 points_per_frame=464 out=data/minibench/RT-L4-S01-M1/observations.npz
```

`--all` mode also generated the same four outputs.

## NPZ Contract

Each `observations.npz` contains:

```text
timestamps
packed_J
r_list
R_diag_list
num_points_per_frame
axis_per_frame
pose_gt
normals_world
points_lidar
```

Shapes:

| Sequence | `packed_J` | `r_list` | `R_diag_list` | `axis_per_frame` | `pose_gt` |
| --- | --- | --- | --- | --- | --- |
| `OC-L0-S01-M1` | `(200, 360, 6)` | `(200, 360)` | `(200, 360)` | `(200, 3)` | `(200, 8)` |
| `ST-L3-S01-M1` | `(240, 320, 6)` | `(240, 320)` | `(240, 320)` | `(240, 3)` | `(240, 8)` |
| `CT-L2-S01-M2` | `(220, 320, 6)` | `(220, 320)` | `(220, 320)` | `(220, 3)` | `(220, 8)` |
| `RT-L4-S01-M1` | `(260, 464, 6)` | `(260, 464)` | `(260, 464)` | `(260, 3)` | `(260, 8)` |

## Information Matrix Sanity

Summary table path:

- `/home/lj/Degen-LIO/results/day14/tables/day05_observation_summary.csv`

Mean translational information diagonal and eigenvalue sanity:

| Sequence | mean Htxx | mean Htyy | mean Htzz | min eigenvalue | median weak-axis alignment |
| --- | ---: | ---: | ---: | ---: | ---: |
| `OC-L0-S01-M1` | 333333.333 | 333333.333 | 233333.333 | 209683 | 0.000 |
| `ST-L3-S01-M1` | 0.000 | 400000.000 | 400000.000 | -1.74623e-10 | 1.000 |
| `CT-L2-S01-M2` | 153070.237 | 246929.763 | 400000.000 | -6.1118e-10 | 1.000 |
| `RT-L4-S01-M1` | 0.000 | 371200.000 | 371200.000 | -1.16415e-10 | 1.000 |

Interpretation:

- ST and RT have near-zero x translation information, as required.
- OC has balanced x/y/z translation information and is not single-axis
  concentrated.
- CT has nonzero global x/y information because the local tunnel axis rotates,
  but the local translational weak direction aligns with `axis.csv`.
- Tiny negative eigenvalues in ST/CT/RT are numerical roundoff around zero, not
  evidence of an invalid information matrix.

## Output Paths

- Observation simulator:
  `/home/lj/Degen-LIO/src/minibench/observation_simulator.py`
- CLI script:
  `/home/lj/Degen-LIO/scripts/01_simulate_observations.py`
- Tests:
  `/home/lj/Degen-LIO/tests/test_observation_simulator.py`
- Observations:
  - `/home/lj/Degen-LIO/data/minibench/OC-L0-S01-M1/observations.npz`
  - `/home/lj/Degen-LIO/data/minibench/ST-L3-S01-M1/observations.npz`
  - `/home/lj/Degen-LIO/data/minibench/CT-L2-S01-M2/observations.npz`
  - `/home/lj/Degen-LIO/data/minibench/RT-L4-S01-M1/observations.npz`
- Summary table:
  `/home/lj/Degen-LIO/results/day14/tables/day05_observation_summary.csv`
- Day 5 report:
  `/home/lj/Degen-LIO/reports/day05_report.md`

## Failed Or Deferred Items

- Initial CT-specific test used an overly strict "near-orthogonal" start/end
  side-normal threshold. The actual CT curve changes the side normal clearly
  but not by 90 degrees. The test was corrected to require significant
  non-constant local normals and local weak-axis alignment.
- Day 6 ODI/AIS/lambda/condition-number computation was not implemented by
  design.
- Day 7 toy LIO was not implemented by design.
- No Day 14 figures were generated by design.

## Tomorrow's Single Most Important Task

Implement WhitenedInfo and ODITracker:

- `src/degen_detector/whitened_info.py`
- `src/degen_detector/odi_tracker.py`
- `scripts/02_compute_odi.py`

Day 6 must compute and export, for every frame:

```text
eig_1 ... eig_6
ODI
AIS
lambda_min
condition_number
num_points
```

