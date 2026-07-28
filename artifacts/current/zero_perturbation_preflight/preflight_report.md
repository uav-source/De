# Zero-Perturbation Registration Measurement — Preflight v2

## Decision

`ZERO_PERTURBATION_PREFLIGHT_PASS = true`

`ZERO_PERTURBATION_DEVELOPMENT_AUTHORIZED = true`

Only Development is authorized. No Development or Confirmatory registration experiment was run. The current `ZERO_PERTURBATION_ROUTE_PASS=false` means not evaluated; it is not a scientific negative result.

## Provenance-aware seed audit

The earlier bare-number search produced false positives because metric values, correspondence counts, trial identifiers, poses, timestamps, and hash substrings can accidentally equal a candidate integer. The v2 audit treats a value as a collision only in a seed-bearing context:

- JSON/YAML keys containing `seed`, `random_state`, or `rng`, including nested seed lists;
- CSV columns whose names contain those seed markers;
- Python/C++ RNG initialization, including NumPy/random, `default_rng`, MT19937, bootstrap, and seeded scene-generation calls;
- historical run/protocol/test locks through their structured seed fields.

Bare numeric matches in non-seed metric columns are ignored. The frozen namespace had no pre-existing match, all 19 derived seeds are unique, the split overlap is zero, and no derived seed has historical provenance in a seed-bearing context.

## Frozen seed schedule

Payload: `{namespace}|{split}|{domain}|{index}`. The first eight SHA-256 digest bytes are read big-endian, reduced modulo 2147483647, and zero is replaced by one.

| Split | Domain | Label | Seed |
|---|---|---|---:|
| development | geometry | geometry_0 | `1850310744` |
| development | geometry | geometry_1 | `1957656152` |
| development | geometry | geometry_2 | `1334931069` |
| development | measurement | measurement_0 | `217775206` |
| development | measurement | measurement_1 | `1664898153` |
| development | bootstrap | bootstrap_0 | `1191248828` |
| development | backend | native | `738007943` |
| development | backend | open3d | `1004155548` |
| confirmatory | geometry | geometry_0 | `248284635` |
| confirmatory | geometry | geometry_1 | `376488233` |
| confirmatory | geometry | geometry_2 | `198112089` |
| confirmatory | geometry | geometry_3 | `229684695` |
| confirmatory | geometry | geometry_4 | `226655024` |
| confirmatory | measurement | measurement_0 | `469989467` |
| confirmatory | measurement | measurement_1 | `1088311622` |
| confirmatory | measurement | measurement_2 | `916609326` |
| confirmatory | bootstrap | bootstrap_0 | `1083684578` |
| confirmatory | backend | native | `910140651` |
| confirmatory | backend | open3d | `326720362` |

## Python 3.11 environment

The machine initially had no Conda/Mamba executable, so micromamba 2.8.1 was bootstrapped without sudo. The named environment uses Python 3.11.15, Open3D 0.19.0+b012259, NumPy 1.26.4, and SciPy 1.11.4. The initial Conda Python builds exposed two old environment-sensitive tests; applying the repository's exact `requirements-lock-py311.txt` PyPI wheels fixed both without changing old scientific code or results.

Final full pytest: **1493 passed, 1 skipped, 262 warnings** in 64.51 seconds.

## Scope controls

- `OLD_CAPTURE_RANGE_TEST_SEEDS_ACCESSED = false`
- `ZERO_PERTURBATION_EXPERIMENT_STARTED = false`
- ODI was not modified; d50 was not restored; FAST-LIO2 was not modified.
- No real data or vision was used, and nothing was pushed.
