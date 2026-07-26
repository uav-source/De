# Fallback C Offline Remediation Contract

This task preserves the production detector, detector configuration and lock,
the runtime adapter, the canonical adapter output, and the frozen observation
records. It changes only the offline comparison contract.

Records whose Jacobian has rows greater than or equal to columns are in the
production-executed domain. Their adapter metrics must match the direct
production entrypoint at absolute tolerance 1e-12. Records whose Jacobian has
fewer rows than columns are in the adapter-precondition domain. They must
retain `TOO_FEW_CORRESPONDENCES`, null metric fields, and false direction
booleans; direct production metrics are diagnostic only.

The null-safe comparator never converts null to float. Booleans compare
exactly, finite numerics use the fixed tolerance, and lists compare
element-by-element. Unsupported and non-finite values produce structured
mismatches.

This is internal engineering determinism evidence only. It authorizes no ROS,
FAST-LIO2, bag reading, threshold tuning, scientific effectiveness analysis,
labeled split, or Day 6 execution.
