# Phase A Execution-Chain Audit v1.1 Failure Package

The frozen-environment audit passed all three main fixture expectations, strict schema/writer checks, primary analysis, independent verification, tamper rejection, publication, and artifact SHA verification. It failed the mandatory interruption/resume equivalence gate because one Open3D `inlier_rmse` value differed by one floating-point tail value between the resumed and fresh runs.

This package records the failure without relaxing exact equivalence or changing any prohibited implementation. The authoritative audit artifact remains in `artifacts/current/zero_perturbation_phase_a_execution_chain_audit_v1_1/` with `PHASE_A_EXECUTION_CHAIN_AUDIT_PASS = false`.

Per the stop rule:

- no Formal Execution Lock v1.1 was built;
- no formal cache data was read;
- no formal seed was accessed;
- no formal Open3D/PCL or Native backend ran;
- no formal trial result was written;
- Phase A and Phase B were not run;
- no next patch version was started.
