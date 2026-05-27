# Day 02 Report

Date: 2026-05-27 CST

## Completed Items

- Created dependency specification:
  - `requirements.txt`
- Created executable environment checker:
  - `scripts/check_env.py`
- Created frozen default detector config:
  - `configs/detector/odi_default.yaml`
- Created run manifest template:
  - `results/day14/manifests/manifest_template.json`
- Created Day 14 reproduction skeleton:
  - `scripts/reproduce_day14.sh`
- Created initial pytest framework:
  - `tests/test_whitened_info.py`
  - `tests/test_odi_tracker.py`
  - `tests/test_weak_direction.py`
  - `tests/test_metrics.py`
- Ran environment check and pytest successfully after fixing one Python 3.8
  compatibility issue.

## Commands Run

```bash
chmod +x scripts/check_env.py scripts/reproduce_day14.sh
python3 scripts/check_env.py
command -v pytest
python3 -m pip --version
python3 -m pytest --version
python3 - <<'PY'
import sys
print(sys.executable)
print(sys.path)
try:
    import numpy, scipy, pandas, matplotlib, yaml, tqdm
    print('core deps ok')
except Exception as exc:
    print(type(exc).__name__, exc)
PY
python3 -m pip install --user pytest
python3 scripts/check_env.py
python3 -m pytest -q
bash scripts/reproduce_day14.sh --dry-run
python3 -m pytest -q
python3 scripts/check_env.py
```

## Result Summary

Initial environment check failed because `pytest` was missing from the active
Python environment:

```text
status: FAIL
error: missing packages: pytest
install hint: python -m pip install -r requirements.txt
```

`pytest` was installed with:

```bash
python3 -m pip install --user pytest
```

The first pytest run then exposed a real Python 3.8 compatibility bug in the
placeholder test code:

```text
ERROR tests/test_odi_tracker.py - TypeError: 'type' object is not subscriptable
```

The cause was a runtime annotation using `dict[str, str]` without postponed
annotations. It was fixed by using `typing.Dict`.

Final environment check:

```text
Degen-LIO Day 2 environment check
repo_root: /home/lj/Degen-LIO
git_commit: 9c1b801
random_seed: 42
manifest: /home/lj/Degen-LIO/results/day14/manifests/day02_env_check.json
status: OK
```

Final pytest result:

```text
5 passed in 0.02s
```

Post-commit verification was run after the Day 2 artifact commit. The exact
current commit is regenerated into
`results/day14/manifests/day02_env_check.json` whenever
`python3 scripts/check_env.py` is rerun:

```text
Degen-LIO Day 2 environment check
repo_root: /home/lj/Degen-LIO
git_commit: <current HEAD at check time>
random_seed: 42
manifest: /home/lj/Degen-LIO/results/day14/manifests/day02_env_check.json
status: OK
```

```text
5 passed in 0.01s
```

Reproduction skeleton dry run:

```text
Degen-LIO Day 14 reproduction skeleton
repo: /home/lj/Degen-LIO
mode: --dry-run
Planned steps:
  python scripts/00_generate_minibench.py --all
  python scripts/01_simulate_observations.py --all
  python scripts/02_run_toy_lio.py --all
  python scripts/03_eval_metrics.py --all
  python scripts/04_plot_day14.py --results results/day14 --out results/day14/figures
Day 2 skeleton only: future scripts are intentionally not required yet.
```

## Environment Manifest

Output path:

- `/home/lj/Degen-LIO/results/day14/manifests/day02_env_check.json`

Key values from the manifest:

| Field | Value |
| --- | --- |
| Python | 3.8.10 |
| Git commit at first successful check | `9c1b801` |
| Git commit at final verification | recorded in `day02_env_check.json` |
| Random seed | `42` |
| Missing packages | none |
| numpy | 1.24.4 |
| scipy | 1.10.1 |
| pandas | 2.0.3 |
| matplotlib | 3.7.5 |
| PyYAML | 6.0.3 |
| pytest | 8.3.5 |
| tqdm | 4.67.3 |

## Output Paths

- Requirements: `/home/lj/Degen-LIO/requirements.txt`
- Environment checker: `/home/lj/Degen-LIO/scripts/check_env.py`
- Default ODI config: `/home/lj/Degen-LIO/configs/detector/odi_default.yaml`
- Manifest template:
  `/home/lj/Degen-LIO/results/day14/manifests/manifest_template.json`
- Reproduction skeleton:
  `/home/lj/Degen-LIO/scripts/reproduce_day14.sh`
- Environment check manifest:
  `/home/lj/Degen-LIO/results/day14/manifests/day02_env_check.json`
- Day 2 report: `/home/lj/Degen-LIO/reports/day02_report.md`

## Failed Or Deferred Items

- `pytest` was missing initially and had to be installed.
- The first pytest run failed due to a Python 3.8 type-annotation issue; this
  was fixed and the final pytest run passed.
- `scripts/reproduce_day14.sh --run` is intentionally not ready on Day 2
  because the future pipeline scripts do not exist yet.
- No minibench sequence configs were created today; Day 3 owns that work.

## Tomorrow's Single Most Important Task

Create the four fixed minimum sequence configs and data specification:

- `configs/minibench/OC-L0-S01-M1.yaml`
- `configs/minibench/ST-L3-S01-M1.yaml`
- `configs/minibench/CT-L2-S01-M2.yaml`
- `configs/minibench/RT-L4-S01-M1.yaml`
- `docs/minibench_spec.md`
