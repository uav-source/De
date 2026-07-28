# Zero-Perturbation Phase A Lock Architecture v2

This protocol separates the Phase A execution authorization into four acyclic
layers. It is an execution-control requalification, not a scientific run.

The Scientific Protocol Lock owns only scientific choices projected from the
frozen Phase A v1 scientific base. The existing 210-snapshot lock remains the
single snapshot authority and is referenced byte-for-byte. The Execution
Implementation Lock owns only executable and fixture-contract SHA bindings.
The Formal Run Lock owns the one-time authorization edge and references the
other three layers plus the frozen trial plan.

The dependency graph is:

```text
Scientific Protocol Lock v2 ─┐
Snapshot Lock ────────────────┼──> Formal Run Lock v2
Execution Implementation v2 ─┘
```

No upstream layer may reference the Formal Run Lock. The Formal Run Lock may
not duplicate thresholds, backend parameters, scenes, seeds, repeats, or
implementation component SHA values.

The legacy v1.2 protocol lock remains immutable historical evidence. Its
scientific values are projected automatically, but its embedded Stage-1
implementation SHA values are never used as runtime implementation authority.
This is a layer correction, not an instruction to ignore or override a failed
legacy lock.

Before any formal cache data is read, the v2 runner must validate the Formal
Run Lock schema and payload, all three upstream layers, current implementation
SHA values, the exact snapshot/trial plans, backend allow/deny lists, formal
authorization, and the environment/worktree contract. Every validation failure
must stop with a layer-specific classification.

The v2 implementation is first qualified on the frozen three-snapshot,
six-trial fixture chain. Those figures and tables must state “FIXTURE AUDIT —
NOT SCIENTIFIC DATA.” A subsequent formal dry-run may verify existence and SHA
of all 210 Stage-0 cache entries, but it may not access formal seeds, execute a
backend, write a trial result, or emit an attempt STARTED event.

Authorization for a later 420-trial formal run is allowed only when the
scientific projection has zero differences, the snapshot lock is inherited at
its original SHA, the fixture audit passes, all 23 lock-layer tamper cases are
rejected before cache access, the 210/420 dry-run passes with zero execution,
and the complete artifact verifies independently.

