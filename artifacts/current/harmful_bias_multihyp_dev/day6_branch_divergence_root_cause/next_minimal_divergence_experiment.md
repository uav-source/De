# Next minimal branch-divergence experiment

Design only. No experiment is authorized or executed by this audit.

## Rank 1: A_INPUT_AND_MAP_STAGE_HASHES

- Question: Do identical raw inputs reach scan 147, and does map identity diverge before formal correspondence construction?
- Minimal changes: Read-only per-scan digests for raw LiDAR payload, IMU bundle, undistorted cloud, map before measurement, map after insertion, insertion batch, and formal correspondence; scan 135-160 only.
- Expected evidence: First differing stage and exact scan without exporting point clouds or maps.
- Risk: Low-to-medium instrumentation perturbation risk.
- Runtime cost: One bounded Quick Shack diagnostic pair.
- Data volume: Small digest-only window.
- Success criterion: All stage digests exist and the earliest differing digest is localized.
- Limitation: A digest localizes stage identity, not scientific detector effectiveness.

## Rank 2: C_CORRESPONDENCE_FINE_GRAIN_AUDIT

- Question: Which accepted source index, plane digest, or neighbor identity first differs?
- Minimal changes: Read-only accepted indices, plane-parameter digests, neighbor IDs/digests, and compression mappings for scan 140-152 only.
- Expected evidence: Element-level correspondence onset evidence.
- Risk: Medium data-collection and observer-effect risk.
- Runtime cost: One bounded diagnostic replay pair.
- Data volume: Moderate, limited to 13 scans.
- Success criterion: The first differing correspondence element and upstream identity are recorded.
- Limitation: Element localization does not alone establish map or scheduling causality.

## Rank 3: B_THREAD_SENSITIVITY

- Question: Is the branch sensitive to the current thread configuration?
- Minimal changes: Compare the current frozen configuration with OMP_NUM_THREADS=1 using the same digest instrumentation.
- Expected evidence: Configuration-conditioned stage digests around the onset window.
- Risk: Medium; configuration changes timing and are diagnostic only.
- Runtime cost: Two bounded executions after separate authorization.
- Data volume: Small digest-only window.
- Success criterion: Thread-conditioned divergence is reproducibly localized or absent.
- Limitation: Sensitivity would not by itself prove a specific data race.

`NEXT_DIAGNOSTIC_EXPERIMENT_RECOMMENDED=true`

`NEXT_DIAGNOSTIC_EXPERIMENT_AUTHORIZED=false`
