# Phase A v1.1 Runner Correction Lock

## Decision

The v1 formal run authorization is invalidated because its locked runner was a
placeholder.  Phase A v1.1 changes only the executable runner contract.  The
v1.1 protocol lock pass is `true` and next-round formal run
authorization is `true`.  This correction round did not run
Phase A or Phase B; Day 1 remains NOT_EVALUATED.

## Scientific equality

All six scientific difference counters are zero.  The seven scenes, five
Development repeat indices, 3×2 Development seed schedule, IDEAL_MATCHED-only
condition, 210/420 plan, backend parameters, transforms, checksums, rotation
metric, failures, q95 algorithm, Gates, and thresholds are inherited unchanged
from the verified v1 YAML.

## Executable runner

Old runner SHA: `9b53842e090e69e5d8a2ff5aa5de534c53394401571cbe0b0e20d8c3565fce84`.  New runner SHA: `87fd8ebcdfa2c17cfe8359047cbb39e26c1dab7bbf03bc6b7e23d5394315ee6f`.
The runner supports only `--dry-run, --help, --output-dir, --protocol-lock, --resume, --run-id, --workers`.  It validates v1.1 authority,
implementation and plan hashes before the formal boundary; writes atomically;
validates resume results; refuses overwrite, corruption, mismatch, old v1 locks,
and Native/backend/threshold/seed overrides.

## Non-formal evidence

The deterministic fixture contains 911 unique
3-D points, one snapshot and two trials.  Open3D pass is
`True` and PCL pass is
`True`; input checksum mismatch count is
`0`.  Dry-run reports 210
planned snapshots and 420 planned trials with zero RNG, snapshot, backend and
trial-result activity.

## Prohibited activity

Formal RNG constructions, snapshots, backend executions and trial results are
all zero.  Confirmatory/old-Test seed access and Native formal execution are
zero.  Open3D, PCL parameters/CLI, snapshot builder, scenes, seed schedule,
Native, ODI, d50 and FAST-LIO2 are unchanged.  No push occurred.
