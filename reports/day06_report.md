# Day 06 Report

Date: 2026-05-28 CST

## Completed Items

- Fixed Day 5 reproducibility risk in `load_sequence_config(metadata)`:
  - original `metadata["config_path"]` is tried first;
  - if missing, the loader falls back to
    `configs/minibench/<sequence_id>.yaml` under the current repository;
  - if no candidate exists, it raises `FileNotFoundError` instead of silently
    returning `{}`.
- Implemented WhitenedInfo:
  - `src/degen_detector/whitened_info.py`
- Implemented ODITracker:
  - `src/degen_detector/odi_tracker.py`
- Implemented ODI CLI:
  - `scripts/02_compute_odi.py`
- Updated reproduction skeleton to use `python3` and include the ODI step:
  - `scripts/reproduce_day14.sh`
- Updated tests:
  - `tests/test_observation_simulator.py`
  - `tests/test_whitened_info.py`
  - `tests/test_odi_tracker.py`
- Generated ODI CSV files for all four sequences.
- Generated ODI summary table:
  - `results/day14/tables/day06_odi_summary.csv`

Day 6 did not implement weak direction alignment, toy LIO, or Day 14 figures.

## Commands Run

```bash
git status --short
git rev-parse --short HEAD
find src scripts tests reports results/day14 -maxdepth 3 -type f | sort
sed -n '1,260p' src/minibench/observation_simulator.py
sed -n '260,620p' src/minibench/observation_simulator.py
sed -n '1,240p' tests/test_observation_simulator.py
sed -n '1,220p' tests/test_whitened_info.py
sed -n '1,220p' tests/test_odi_tracker.py
chmod +x scripts/02_compute_odi.py
python3 -m pytest -q
python3 scripts/check_env.py
python3 scripts/00_generate_minibench.py --all
python3 scripts/01_simulate_observations.py --all --config configs/detector/odi_default.yaml
python3 scripts/02_compute_odi.py --all --config configs/detector/odi_default.yaml
python3 scripts/02_compute_odi.py --seq data/minibench/ST-L3-S01-M1 --config configs/detector/odi_default.yaml --out results/day14/raw/ST-L3-S01-M1_odi.csv
```

## Pytest Result

```text
40 passed in 1.28s
```

The test suite now covers:

- `H_tilde` symmetry and PSD sanity;
- finite eigenvalues, AIS, lambda_min, condition number;
- isotropic spectrum gives ODI near 0;
- rank-1 dominant spectrum gives high ODI;
- condition number can explode while ODI remains finite;
- ST/RT ODI is clearly higher than OC;
- CT output is not identical to a fixed global ST pattern;
- stale absolute `config_path` falls back to current repo config;
- `RT-L4-S01-M1` fallback config reads `point_noise_std_m: 0.025`.

## Generated ODI Files

Raw framewise CSV files:

- `/home/lj/Degen-LIO/results/day14/raw/OC-L0-S01-M1_odi.csv`
- `/home/lj/Degen-LIO/results/day14/raw/ST-L3-S01-M1_odi.csv`
- `/home/lj/Degen-LIO/results/day14/raw/CT-L2-S01-M2_odi.csv`
- `/home/lj/Degen-LIO/results/day14/raw/RT-L4-S01-M1_odi.csv`

Each CSV contains:

```text
timestamp,eig_1,eig_2,eig_3,eig_4,eig_5,eig_6,ODI,AIS,lambda_min,condition_number,num_points
```

Summary CSV:

- `/home/lj/Degen-LIO/results/day14/tables/day06_odi_summary.csv`

## ODI Summary

| Sequence | mean_ODI | median_ODI | mean_AIS | median_lambda_min | median_condition_number | mean_num_points |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `OC-L0-S01-M1` | 0.512403 | 0.512430 | 9.496386 | 1401.462676 | 59.502801 | 360.0 |
| `ST-L3-S01-M1` | 0.728854 | 0.728799 | 7.080828 | -9.21122e-27 | 2892726.215880 | 320.0 |
| `CT-L2-S01-M2` | 0.728128 | 0.728232 | 7.113469 | 2.27374e-13 | 2892852.985923 | 320.0 |
| `RT-L4-S01-M1` | 0.728880 | 0.728770 | 7.007698 | -9.45845e-27 | 2892412.243235 | 464.0 |

## Trend Assessment

Expected trend:

```text
OC lower than ST/CT/RT
ST and RT high due to tunnel-axis weak translation
CT high, but not a fixed global-x ST copy
```

Observed:

- ST median ODI exceeds OC by about `0.216`.
- CT median ODI exceeds OC by about `0.216`.
- RT median ODI exceeds OC by about `0.216`.
- ST/RT lambda_min is near numerical zero, matching the intended weak axis.
- CT lambda_min is also near zero, and tests confirm CT is driven by local
  framewise normals from `axis.csv`, not fixed global `planes.csv`.

OC ODI is not close to zero; it is about `0.51`. This is a caution, not a Day 6
No-Go, because the relative tunnel-vs-open trend is clear. Likely contributors:

1. the open-control scene is still a finite synthetic plane set, not a truly
   uniform 6DoF information source;
2. rotational and translational pose blocks are whitened by fixed
   `s_theta=0.05`, `s_p=0.5`, which can still yield spectral concentration;
3. ODI measures spectral concentration, not absolute information sufficiency.

If later gates require OC ODI to be much lower, the first repair order is:

1. improve open-control geometry diversity;
2. re-check pose-block whitening scales;
3. only then revisit the ODI definition.

## Output Paths

- WhitenedInfo:
  `/home/lj/Degen-LIO/src/degen_detector/whitened_info.py`
- ODITracker:
  `/home/lj/Degen-LIO/src/degen_detector/odi_tracker.py`
- ODI CLI:
  `/home/lj/Degen-LIO/scripts/02_compute_odi.py`
- Day 6 report:
  `/home/lj/Degen-LIO/reports/day06_report.md`
- Summary table:
  `/home/lj/Degen-LIO/results/day14/tables/day06_odi_summary.csv`

## Failed Or Deferred Items

- No Day 6 test failure remained at the end of the day.
- OC ODI is moderate rather than near zero; this is recorded as a watch item
  for Day 10 metric validity and Day 12 sensitivity.
- Weak direction alignment was not implemented by design.
- Toy LIO was not implemented by design.
- Day 14 plots were not generated by design.

## Tomorrow's Single Most Important Task

Implement the Day 7 toy LIO / synthetic LIO probe so the project has a drift
signal to correlate with ODI:

- `src/minibench/toy_lio.py`
- `scripts/02_run_toy_lio.py`

The Day 7 acceptance focus is directional drift:

```text
ST/RT axis error should exceed cross error.
Open control should not obviously diverge.
```

