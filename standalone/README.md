# Standalone research snapshots

## Zero-Perturbation Phase A harness

The directory `zero_perturbation_phase_a_harness/` is an auditable source
snapshot imported from:

- source repository:
  `/home/lj/zero_perturbation_phase_a_harness_20260729_1407`
- source branch:
  `feature/zero-perturbation-synthetic-confirmatory-v4-prerun`
- source commit:
  `47c2d4934e0791736144d312699e5f017b1d4ac2`

The import contains 618 files tracked by the source commit plus 19 small,
seed-free fixture-audit files required by the harness tests. Source and
destination content hashes were checked after copying. The source
`.gitignore` is preserved byte-for-byte as `.gitignore.source`; the active
copy only adds negations that make those 19 fixture files visible to the
parent Degen-LIO repository.

The import intentionally excludes the source `.git` directory, Python caches,
environment directories, large snapshot data under `data/`, experiment
results under `results/`, and the large generated
`artifacts/full_synthetic_development_v1/` result package. The original
standalone repository was not modified.

This directory is a code and audit snapshot, not a newly qualified formal
runtime location. Existing formal Git gates, release-tag bindings, and some
absolute-path checks still refer to the original standalone repository. They
must be explicitly redesigned and requalified before formal execution from
this nested location.
