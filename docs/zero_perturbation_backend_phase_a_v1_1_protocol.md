# Zero-Perturbation Dual-Backend Phase A v1.1 Implementation Lock

## Amendment scope

Version 1.1 is an implementation-only correction to Phase A v1.  The v1 static
scientific contract remains the sole source of truth for the seven scenes,
Development seed schedule, five repeats, IDEAL_MATCHED condition, two formal
backends, input and transform semantics, backend parameters, rotation metric,
failure definitions, aggregation algorithms, Gates, and thresholds.

The v1 runner was a placeholder that always stopped after validating its input.
Consequently, v1 formal run authorization is invalidated without classifying an
Open3D, PCL, Phase A, or scientific failure.  No formal snapshot or trial was
created under v1.  The v1 lock artifact remains unchanged as historical
evidence.

## Scientific equality with v1

The v1.1 loader reads the frozen v1 YAML only after verifying its SHA-256.  It
copies the enumerated snapshot/trial plan and every scientific section directly
from that verified base.  The machine-readable diff must report zero scene,
seed, threshold, backend-parameter, metric, and other scientific-parameter
differences.  Only the runner implementation and implementation-lock evidence
may differ.

## Runner authority boundary

Formal execution requires a v1.1 lock whose complete payload hash verifies,
whose protocol and implementation hashes match the current repository, and
whose `formal_execution_authorized` field is exactly `true`.  The old v1 lock
does not contain that field and is rejected before RNG construction, snapshot
generation, or backend execution.

The command accepts only the lock, run ID, output directory, worker count,
resume flag, and dry-run flag.  There is no parameter, threshold, scene, seed,
backend-subset, failure-skipping, Native, or lock-bypass option.

## Formal workflow

After authority and clean-worktree verification, the runner verifies the exact
210-row snapshot and 420-row trial manifests.  It builds each snapshot once,
canonicalizes source/target coordinates to little-endian C-contiguous float32
and the reference pose to little-endian C-contiguous float64, and computes raw
byte SHA-256 checksums.  Open3D and PCL receive the same canonical values,
reference pose, snapshot identity, and checksums.  Neither backend may read the
other backend's result.

Each snapshot and trial result is written to a temporary sibling, flushed and
fsynced, and atomically renamed.  Existing results are never silently
overwritten.  Resume accepts a result only when its identity, protocol hash,
implementation hash, and checksums verify; corruption or mismatch stops the
run.  Completed, pending, failed, and resumed trial-ID sets are recorded and
must be mutually consistent.

## Failure and interruption semantics

Scientific solver failures, backend exceptions, nonfinite output, lock
mismatches, corrupt existing results, and infrastructure interruptions remain
distinct classifications.  Missing or interrupted trials are not assigned zero
error and do not become solver passes.  Formal analysis is allowed only after
all 420 trials have a final result.

## Fixture and dry-run boundaries

Runner integration tests use one independent, deterministic, asymmetric 3-D
identity fixture.  It is marked `fixture_only=true` and
`is_formal_phase_a=false`; it does not call the seven-scene generator and uses
no Development, Confirmatory, or old capture-range Test seed.  Its temporary
results never enter a formal Phase A artifact directory.

Dry-run validates the v1.1 lock, exact plan cardinalities, output path,
backend discovery, and PCL CLI hash.  It builds no snapshot, instantiates no
RNG, executes no backend, and writes no trial result.  This correction round
may publish a v1.1 formal-execution authorization only after every lock and
test requirement passes, but it must not use that authorization to run Phase A.

