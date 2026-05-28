# Day 07 Report

Date: 2026-05-28 CST

## Completed Items

- Implemented the minimum synthetic LIO probe:
  - `src/minibench/toy_lio.py`
- Implemented CLI runner:
  - `scripts/02_run_toy_lio.py`
- Added tests:
  - `tests/test_toy_lio.py`
- Updated reproduction skeleton:
  - `scripts/reproduce_day14.sh`
- Generated four TUM estimated trajectories:
  - `results/day14/raw/OC-L0-S01-M1_pose_est_toy.tum`
  - `results/day14/raw/ST-L3-S01-M1_pose_est_toy.tum`
  - `results/day14/raw/CT-L2-S01-M2_pose_est_toy.tum`
  - `results/day14/raw/RT-L4-S01-M1_pose_est_toy.tum`
- Generated summary table:
  - `results/day14/tables/day07_toy_lio_summary.csv`

Day 7 did not implement the full Day 8 metrics system, weak direction
alignment, or figures.

## Anti-Circularity Check

`toy_lio.py` does not read detector CSV files and does not use detector scores
to set drift. The test suite checks for detector CSV dependency traces in the
toy source.

The toy probe drift comes from:

1. GT trajectory increments used as synthetic motion increments;
2. deterministic process noise with stronger axis component in tunnel-like
   sequences;
3. point-to-plane LiDAR update using the framewise Jacobian and residual;
4. weak axis directions remaining poorly corrected because the information
   matrix lacks translational constraint in that direction.

## Commands Run

```bash
git status --short
git rev-parse --short HEAD
sed -n '1,180p' scripts/reproduce_day14.sh
chmod +x scripts/02_run_toy_lio.py
python3 scripts/check_env.py
python3 -m pytest -q
python3 scripts/00_generate_minibench.py --all
python3 scripts/01_simulate_observations.py --all --config configs/detector/odi_default.yaml
python3 scripts/02_compute_odi.py --all --config configs/detector/odi_default.yaml
python3 scripts/02_run_toy_lio.py --all --config configs/detector/odi_default.yaml
```

## Pytest Result

```text
46 passed in 1.97s
```

The Day 7 tests check:

- output pose count matches GT;
- `pose_est_toy.tum` uses TUM format:
  `timestamp tx ty tz qx qy qz qw`;
- open control does not obviously diverge;
- ST axis error exceeds cross error;
- RT axis error exceeds cross error;
- fixed random seed gives reproducible trajectories;
- toy LIO does not read detector CSV outputs.

## Toy LIO Output

Command:

```bash
python3 scripts/02_run_toy_lio.py --all --config configs/detector/odi_default.yaml
```

Output:

```text
toy_lio: seq=OC-L0-S01-M1 poses=200 final_axis=0.000017 final_cross=0.002841 out=/home/lj/Degen-LIO/results/day14/raw/OC-L0-S01-M1_pose_est_toy.tum
toy_lio: seq=ST-L3-S01-M1 poses=240 final_axis=5.222598 final_cross=0.003415 out=/home/lj/Degen-LIO/results/day14/raw/ST-L3-S01-M1_pose_est_toy.tum
toy_lio: seq=CT-L2-S01-M2 poses=220 final_axis=3.479322 final_cross=0.002666 out=/home/lj/Degen-LIO/results/day14/raw/CT-L2-S01-M2_pose_est_toy.tum
toy_lio: seq=RT-L4-S01-M1 poses=260 final_axis=6.717231 final_cross=0.000507 out=/home/lj/Degen-LIO/results/day14/raw/RT-L4-S01-M1_pose_est_toy.tum
```

## Summary Table

CSV path:

- `/home/lj/Degen-LIO/results/day14/tables/day07_toy_lio_summary.csv`

| Sequence | final_translation_error | final_axis_error | final_cross_error | mean_axis_error | mean_cross_error |
| --- | ---: | ---: | ---: | ---: | ---: |
| `OC-L0-S01-M1` | 0.002841 | 0.000017 | 0.002841 | 0.001343 | 0.002306 |
| `ST-L3-S01-M1` | 5.222599 | 5.222598 | 0.003415 | 2.625349 | 0.001961 |
| `CT-L2-S01-M2` | 3.479323 | 3.479322 | 0.002666 | 1.739733 | 0.001959 |
| `RT-L4-S01-M1` | 6.717231 | 6.717231 | 0.000507 | 3.377445 | 0.001995 |

## Sanity Assessment

- OC did not obviously diverge: final translation error is about `0.0028 m`.
- ST produced strong axis drift: final axis error is about `5.22 m`, while
  final cross error is about `0.0034 m`.
- RT produced strong axis drift: final axis error is about `6.72 m`, while
  final cross error is about `0.0005 m`.
- CT also shows local-axis drift, which is expected because Day 5 made CT
  normals follow the local centerline tangent.

If a future run loses the axis > cross trend, the repair order is:

1. check the point-to-plane Jacobian and residual sign;
2. check tunnel plane normals and CT local normals;
3. check process noise axis/cross decomposition;
4. do not modify detector scores to manufacture drift.

## Output Paths

- Toy LIO module:
  `/home/lj/Degen-LIO/src/minibench/toy_lio.py`
- Toy LIO CLI:
  `/home/lj/Degen-LIO/scripts/02_run_toy_lio.py`
- Toy LIO tests:
  `/home/lj/Degen-LIO/tests/test_toy_lio.py`
- Summary table:
  `/home/lj/Degen-LIO/results/day14/tables/day07_toy_lio_summary.csv`
- Day 7 report:
  `/home/lj/Degen-LIO/reports/day07_report.md`

## Failed Or Deferred Items

- Initial source-dependency test was too broad: the substring `odi` appeared
  inside the word `encoding`. The test was tightened to check actual detector
  output dependency traces such as `_odi`, `odi.csv`, and `ODI`.
- No Day 8 metrics module was implemented by design.
- Weak direction alignment was not implemented by design.
- No Day 14 figures were generated by design.

## Tomorrow's Single Most Important Task

Implement Day 8 evaluation metrics:

- `src/eval/metrics.py`
- `scripts/03_eval_metrics.py`

The first Day 8 sanity target is to recompute axis/cross error from the saved
TUM trajectories rather than trusting the toy LIO internal summary.

