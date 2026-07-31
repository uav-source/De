# Full Synthetic Development Protocol v1

This is a prospectively frozen Development experiment. It is not Confirmatory evidence and does not authorize a paper mainline, a Confirmatory run, or a real-data run.

## Frozen matrix

The combined design contains seven unchanged synthetic scenes, three Development geometry seeds, two Development measurement seeds, five repeats, and six conditions. The 210 `IDEAL_MATCHED` snapshots and 420 trials are imported read-only from the passed Phase A run. They are never regenerated or copied-and-edited.

The five newly executed conditions are `INDEPENDENT_NOISE_FREE`, `SCAN_NOISE_ONLY`, `MAP_NOISE_ONLY`, `DROPOUT_ONLY`, and `FULL_NOISE`. Their noise and dropout values are exactly those in `frozen_assets/full_synthetic_development_protocol_v1.json`. They contain 1,050 new snapshots and 2,100 new trials. The combined matrix is 1,260 snapshots and 2,520 trials. Every new snapshot is shared byte-for-byte by one Open3D and one PCL trial; Native is forbidden.

The 42-snapshot Phase B overlap retains the published `phase-b-signal-v1/...` IDs because the canonical snapshot checksum includes the ID. These snapshots are regenerated into the new cache and their 84 backend trials are rerun. Published identity, condition, backend, failure, input checksum, final transform, metric, fitness, and diagnostic fields are compared at `atol=rtol=1e-12`. Runtime and the new protocol/implementation/lock identity fields are explicitly excluded from scientific numerical equivalence.

## Assets and execution

The new snapshot key is `(scene, geometry seed, measurement seed, repeat, condition)`. Generation uses the byte-exact Phase B-exported generator and snapshot builder with the original Development seed derivation. Method names never enter a snapshot seed. Confirmatory and old capture-range test seeds are forbidden before RNG construction.

Snapshots reside only in `data/full_synthetic_development_v1_snapshots/` and contain C-contiguous little-endian float32 source/target arrays, one float64 4×4 reference pose, and strict metadata. Writes are atomic. Resume validates every existing file, raw payload checksum, metadata checksum, and canonical snapshot checksum and never overwrites a corrupt snapshot.

The one manifest is `frozen_assets/full_synthetic_development_manifest_v1.json`. Its full-run authorization starts false. A separately bounded Phase B subset run is allowed while full execution remains false. Full authorization changes only once, from false to true, after raw JUnit, Phase A import, snapshot preparation, dry-run, and actual Phase B subset reproduction evidence are independently reread and recomputed. Full execution uses run ID `full-synthetic-development-v1`, output `results/full_synthetic_development_v1`, two workers, and mandatory `--resume`.

The subset permission is also fail-closed: before any of its 84 backend calls, the runner directly revalidates the frozen protocol, Phase A import, Phase B PASS archive and tag, all 1,050 prepared snapshots, dry-run design and zero-execution fields, and the exact JUnit collections. A one-time immutable evidence manifest binds the 84 subset trial IDs, paths, and result SHA-256 values. The formal raw manifest may subsequently grow to 2,100 entries; authorized resume projects and revalidates those immutable 84 entries and ignores only additional IDs that belong to the frozen full plan.

Authorization adds the pre-run gate-report SHA and every raw-evidence SHA to the same manifest. Every authorized load re-derives the report, verifies the immutable subset evidence and compares every binding. To avoid a self-referential future-commit hash, the safe operational sequence is: authorize from complete raw evidence; commit all authorized pre-run files with `chore: freeze full synthetic development experiment`; create `archive/zero-perturbation-full-synthetic-development-pre-run` at that HEAD; then start formal execution. The formal entry requires that exact branch, tag equal to HEAD, a clean worktree, and a manifest worktree blob identical to the committed blob.

Python entry points require `MAMBA_ROOT_PREFIX=/home/lj/.local/share/degen-lio-micromamba` and `PYTHONNOUSERSITE=1`, and reject any `sys.path` or `PYTHONPATH` element—including an empty element interpreted as the current working directory—that resolves into `/home/lj/Degen-LIO`. The manifest binds the full transitive local execution closure, frozen generator package initializers and modules, environment manifest, CLI, schema, writer, resume validator, and attempt-event implementation. The Development runtime hard-locks Python 3.11.15, NumPy 1.26.4, SciPy 1.11.4, Open3D `0.19.0+b012259`, scikit-learn 1.9.0, and Matplotlib 3.8.2 directly in the single Development manifest. The older Phase A environment manifest is retained byte-for-byte; its stale Matplotlib entry is not used as the Development value. Before execution the gate also checks the PCL CLI SHA and its PCL 1.15.1 linkage without running registration.

The frozen formal command is:

```bash
MAMBA_ROOT_PREFIX=/home/lj/.local/share/degen-lio-micromamba PYTHONNOUSERSITE=1 /home/lj/.local/bin/micromamba run -n degen-lio-zprm-py311 python scripts/run_full_synthetic_development.py --manifest frozen_assets/full_synthetic_development_manifest_v1.json --run-id full-synthetic-development-v1 --output-dir results/full_synthetic_development_v1 --workers 2 --resume
```

## Metrics and gates

Translation error is the norm of estimated minus reference translation. Rotation uses reflection-safe nearest-SO(3) projection and an atan2 geodesic angle. Repeated groups contain the two measurement seeds by five repeats for a fixed scene, geometry seed, condition, and backend. Systematic offset, ddof=1 repeatability covariance/RMS, systematic fraction, and nonzero direction concentration follow the frozen JSON contract.

For each trial, `T_delta = inverse(T_reference) @ T_estimated`, `rho = t_estimated - t_reference`, and `phi = Log_SO3(R_reference.T @ R_estimated)`. Translation and rotation error are `norm(rho)` and `norm(phi)`. For each ten-observation repeated group, systematic translation offset is `norm(mean(rho))`; translation repeatability RMS is `sqrt(trace(cov(rho, ddof=1)))`. The analogous rotation quantities use `phi`. Systematic translation fraction is `norm(mean(rho)) / mean(norm(rho_k))`, and is null when the denominator is at most `1e-12`. Direction concentration excludes zero vectors. Quantiles use `numpy.quantile(..., method="linear")`; the 2,000-repetition intervals remain exploratory because there are only three geometry seeds.

The common association diagnostic uses `scipy.spatial.cKDTree`, a 0.50 m maximum distance, k=50 PCA target normals, at least ten neighbors, no normal orientation unification, independently recomputed initial/final matches, and Jaccard turnover. It is a common offline diagnostic and is not either backend's internal correspondence set. ODI, AIS, and d50 are absent.

Model A and Model B use Ridge with alpha 1.0, an intercept, train-fold-only standardization, and leave-one-geometry-seed-out cross-validation. Bootstrap descriptions use geometry seed as the outer unit, 2,000 repetitions, and Development bootstrap seed 1191248828. With only three geometry seeds, intervals are exploratory.

All primary scene-effect, cross-backend, scene-rank, systematic-offset wording, reassociation, common-association validity, and local-metric incremental-value thresholds are immutable in the JSON protocol. Automatic non-equivalence candidates remain `AUTOMATIC_CANDIDATE`; no automated process may label one a valid scientific counterexample.

The scene-rank gate has ten non-IDEAL condition-by-backend combinations. `GEOMETRY_RICH_ROOM` must rank among the two lowest-error scenes in at least eight; either `LONG_CORRIDOR` or `END_FACE_TRANSITION_ABSENT` must rank among the three highest-error scenes in at least eight. The systematic-offset wording gate uses only `LONG_CORRIDOR` under `INDEPENDENT_NOISE_FREE` and `FULL_NOISE`: for every backend-by-condition combination, at least two of three geometry groups must have offset at least 0.005 m and systematic fraction at least 0.60, and the three fractions must have median at least 0.70. All four combinations must pass. This wording gate is not itself required for the overall Development gate.

Automatic non-equivalence pairs are searched within backend and non-IDEAL condition. They require normalized translational-Hessian eigenvalue cosine similarity at least 0.98, absolute log condition-number and initial-RMSE ratios at most 0.20, correspondence-count ratio in `[0.90, 1.10]`, translation-error ratio at least 5, absolute turnover difference at least 0.15, and finite errors and turnovers. The alternative local-metric gate needs at least ten candidates per backend and at least three distinct scene pairs across both backends. The only permitted automatic review status is `AUTOMATIC_CANDIDATE`.

Test evidence consists of one exact 65-test collection for the original minimal harness plus Phase B, and one exact 35-test collection for Full Synthetic Development. The 65-test testcase-collection SHA-256 is `c7fd7d9cc860606065281548a0dc3a776b0fc2077d0bf030e06c7da167b0ff28`; the 35-test testcase-collection SHA-256 is `9674fad7a77002d06f346cfecd3647110fe3bcb53758185e7b011748443c133d`. Their full commands, file lists, counts, collection hashes, and test-source SHA-256 bindings are frozen in the protocol and manifest. A passing but incomplete one-test JUnit file is rejected.
