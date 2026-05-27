# Day 03 Report

Date: 2026-05-27 CST

## Completed Items

- Created the four frozen Day 14 minimum sequence configs:
  - `configs/minibench/OC-L0-S01-M1.yaml`
  - `configs/minibench/ST-L3-S01-M1.yaml`
  - `configs/minibench/CT-L2-S01-M2.yaml`
  - `configs/minibench/RT-L4-S01-M1.yaml`
- Created the minibench data specification:
  - `docs/minibench_spec.md`
- Added executable config validation tests:
  - `tests/test_minibench_configs.py`
- Verified that all configs parse with PyYAML.
- Verified that pytest passes after adding the Day 3 tests.

## Sequence Roles

| Sequence | Scientific Role |
| --- | --- |
| `OC-L0-S01-M1` | Negative control: low ODI and no stable weak direction. |
| `ST-L3-S01-M1` | Primary positive case: weak translation along tunnel axis. |
| `CT-L2-S01-M2` | Local-axis case: weak direction should rotate with centerline tangent. |
| `RT-L4-S01-M1` | Hard positive case: tunnel-axis weakness plus repeated features. |

All four configs freeze `random_seed: 42` for the Day 14 minimum probe.

## Commands Run

```bash
git status --short
git rev-parse --short HEAD
find configs docs tests reports -maxdepth 2 -type f | sort
python3 -m pytest -q
python3 - <<'PY'
from pathlib import Path
import yaml
for path in sorted(Path('configs/minibench').glob('*.yaml')):
    data = yaml.safe_load(path.read_text())
    print(path.name, data['sequence_id'], data['scene_family'], data['difficulty'], data['frames'], data['random_seed'])
PY
python3 scripts/check_env.py
bash scripts/reproduce_day14.sh --dry-run
```

## Validation Output

Pytest result:

```text
11 passed in 0.05s
```

Config parse summary:

```text
CT-L2-S01-M2.yaml CT-L2-S01-M2 CT L2 220 42
OC-L0-S01-M1.yaml OC-L0-S01-M1 OC L0 200 42
RT-L4-S01-M1.yaml RT-L4-S01-M1 RT L4 260 42
ST-L3-S01-M1.yaml ST-L3-S01-M1 ST L3 240 42
```

Environment check:

```text
Degen-LIO Day 2 environment check
repo_root: /home/lj/Degen-LIO
git_commit: <current HEAD at check time>
random_seed: 42
manifest: /home/lj/Degen-LIO/results/day14/manifests/day02_env_check.json
status: OK
```

Reproduction skeleton dry run remains valid:

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

## Output Paths

- Open control config:
  `/home/lj/Degen-LIO/configs/minibench/OC-L0-S01-M1.yaml`
- Straight tunnel config:
  `/home/lj/Degen-LIO/configs/minibench/ST-L3-S01-M1.yaml`
- Curved tunnel config:
  `/home/lj/Degen-LIO/configs/minibench/CT-L2-S01-M2.yaml`
- Repetitive tunnel config:
  `/home/lj/Degen-LIO/configs/minibench/RT-L4-S01-M1.yaml`
- Data specification:
  `/home/lj/Degen-LIO/docs/minibench_spec.md`
- Config validation test:
  `/home/lj/Degen-LIO/tests/test_minibench_configs.py`
- Day 3 report:
  `/home/lj/Degen-LIO/reports/day03_report.md`

## Failed Or Deferred Items

- No sequence data was generated today by design. Day 4 owns
  `scripts/00_generate_minibench.py` and `src/minibench/scene_generator.py`.
- No `observations.npz`, `gt.tum`, `axis.csv`, or `planes.csv` files exist yet.
- The environment manifest path is reused from Day 2; it is still valid for
  dependency checks but does not replace the Day 3 report.

## Tomorrow's Single Most Important Task

Implement the scene generator and generate the four sequence directories:

- `src/minibench/scene_generator.py`
- `scripts/00_generate_minibench.py`
- `data/minibench/OC-L0-S01-M1/`
- `data/minibench/ST-L3-S01-M1/`
- `data/minibench/CT-L2-S01-M2/`
- `data/minibench/RT-L4-S01-M1/`

The Day 4 acceptance focus is geometry: straight and repetitive tunnel plane
normals must preserve weak constraint along the tunnel axis.

