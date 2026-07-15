# Day 11A deterministic diagnostic case lock contract

Day 11A performs protocol registration only. It does not import or execute the
estimator, online logger, GT evaluator, causal window statistics, plotting
libraries, or the Stage 2C runtime runner.

## Frozen inputs

The lock reads only the frozen Stage 2C Test config, update lock, compact Test
manifest, common config, and stress config. The compact manifest does not
inline seed or stress lists. Its matching config-bundle hash and successful
seed-isolation, stress-parameter, source, and config verification bind it to
the frozen Test config and update lock without altering the historical file.

The Test geometry, sensor, and process seed lists must match the update lock
exactly and remain disjoint from Development. The complete stress set in the
config and lock must be exactly:

```text
clean
coherent_subhuber_slip
gross_outlier_control
```

The historical Test and Day 11B replay set must both be exactly:

```text
clean
coherent_subhuber_slip
```

The replay matrix is two sweeps by two stress regimes by two methods, or eight
method replays. Day 11A executes none of them.

## Candidate construction and selection

Geometry candidates use levels `L3`, `L4`; Observation candidates use `O3`,
`O4`. Each pool is the Cartesian product with the frozen Test geometry,
sensor, and process seeds, sorted by the Python tuple `(level, geometry_seed,
sensor_seed, process_seed)`.

Each candidate is represented as:

```text
level=<LEVEL>|geometry_seed=<G>|sensor_seed=<S>|process_seed=<P>
```

For each frozen label, selection computes the full SHA-256 digest, interprets
all 32 bytes as an unsigned big-endian integer, and selects
`digest_integer % candidate_count`. Indices are zero-based. Python `hash()`,
random sampling, metric inputs, aliases, and overrides are prohibited.

The candidate CSV, case lock, protocol revision manifest, forbidden-dependency
audit, summary, and run manifest must round-trip through strict validation.
Exactly one row per sweep is selected, historical artifacts remain unchanged,
and all experiment/replay/figure/threshold/classification flags remain false.
