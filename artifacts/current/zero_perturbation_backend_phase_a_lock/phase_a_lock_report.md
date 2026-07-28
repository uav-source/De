# Zero-Perturbation Dual-Backend Phase A Protocol Lock

## Decision

Protocol-lock status is `true` and future Phase A run
authorization is `true`. This never means Phase A ran:
`BACKEND_PHASE_A_EXECUTED=false`, `BACKEND_PHASE_A_COMPLETE=false`, two-backend
qualification remains false, and Day 1 scientific validation is NOT_EVALUATED.

## Planned matrix

The plan contains 210 snapshot IDs and 420 trial
IDs: seven scenes × three Development geometry seeds × two Development
measurement seeds × five repeats × IDEAL_MATCHED only. Open3D and PCL each have
210 planned rows; Native has zero. CSV construction used Cartesian enumeration
only and contains no coordinates or point-cloud paths.

The exact protocol self-audit results are:

- `PROTOCOL_HAS_EXACTLY_7_SCENES=True`
- `PROTOCOL_HAS_EXACTLY_3_GEOMETRY_SEEDS=True`
- `PROTOCOL_HAS_EXACTLY_2_MEASUREMENT_SEEDS=True`
- `PROTOCOL_HAS_EXACTLY_5_REPEATS=True`
- `PROTOCOL_HAS_ONLY_IDEAL_MATCHED=True`
- `PROTOCOL_HAS_EXACTLY_2_BACKENDS=True`
- `PLANNED_SNAPSHOT_COUNT=210`
- `PLANNED_TRIAL_COUNT=420`
- `NATIVE_PLANNED_TRIAL_COUNT=0`
- `OPEN3D_PLANNED_TRIAL_COUNT=210`
- `PCL_PLANNED_TRIAL_COUNT=210`
- `PHASE_A_RNG_INSTANTIATION_COUNT=0`
- `PHASE_A_SNAPSHOT_GENERATION_COUNT=0`
- `PHASE_A_BACKEND_EXECUTION_COUNT=0`
- `PHASE_A_TRIAL_RESULT_COUNT=0`
- `NEW_PROTOCOL_AMBIGUITIES_FOUND=False`

## Input and transform contracts

Both backends share C-contiguous little-endian float32 source/target coordinates
with SHA-256 over raw bytes, and the same little-endian float64 4×4 reference
pose. `T_reference` and `T_estimated` both map source to target/map;
`T_delta=inverse(T_reference)@T_estimated`. Translation is the delta-translation
norm. Rotation is reflection-safe nearest-SO(3) plus atan2, subject first to the
raw matrix-quality Gate.

## Backend parameter locks

Open3D 0.19.0+b012259 parameter SHA is
`94a2d1e991658b7088be43ad1a82f9b1d783264736c3beb0217d6dd1c7a26413`. PCL 1.15.1 parameter SHA is
`16b3d124f466f33c41a1ecfb27a103a570c3ad2055db9c87ae92c74dbba64abd`. Both lock checks are
`true` and maximum correspondence distance is the
same 0.50 m. No backend implementation was changed.

## Failure and Gate contracts

Open3D and PCL failure vocabularies are stored in `gate_contract.json`.
Unexecuted trials remain NOT_EVALUATED, never zero failures. Median uses
`numpy.median`; q95 uses `numpy.quantile(q=0.95, method="linear")`. Per backend,
all 210 future trials must be complete, finite, failure-free and pass unchanged
translation/rotation Gates. Each scene/backend median is gated over 30 trials.
Each scene also needs at least ten unique source checksums over 30 snapshots.

## Non-execution and scope audit

RNG instantiations=0, generated Phase A
snapshots=0, backend executions=
0, and trial results=
0. Confirmatory/old-Test RNG and Native
formal execution counts are zero. Phase A/B, real data, vision and the runner
were not invoked. Open3D, PCL, Native, ODI, d50, FAST-LIO2 and the frozen scene
generator are unchanged; no push occurred.
