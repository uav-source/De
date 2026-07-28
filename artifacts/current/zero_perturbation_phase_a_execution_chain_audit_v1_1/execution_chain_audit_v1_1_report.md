# Phase A Execution-Chain Audit v1.1 — Failed Gate

**FIXTURE EXECUTION-CHAIN AUDIT — NOT SCIENTIFIC PHASE-A DATA**

The audit ran in the frozen `degen-lio-zprm-py311` environment (Python 3.11.15, Open3D 0.19.0+b012259) with the unchanged three fixtures and six main fixture trials.

- IDENTITY: Open3D PASS; PCL PASS.
- NONIDENTITY_REFERENCE: Open3D PASS; PCL PASS.
- NO_CORRESPONDENCE: both backends returned the expected `NO_CORRESPONDENCES` classification.
- Main analysis trial count: 6.
- Independent-verifier trial count: 6.
- Analysis/verifier differences: 0.
- Tampered result rejected: true.
- Publisher tables/figures: 10/5.
- Artifact SHA verification: PASS.

The mandatory interruption/resume equivalence gate failed. For `fixture-audit-v1/nonidentity-reference/open3d_point_to_plane`, the resumed and fresh payloads differed only in `backend_diagnostics.inlier_rmse`:

- resumed: `2.029631763843318e-08`
- fresh: `2.0296317638433184e-08`
- absolute difference: `3.308722450212111e-24`

The audit contract compares semantic payloads exactly after removing only `runtime_ms`; therefore `RESUMED_AND_FRESH_RESULT_EQUIVALENT = false`, `PHASE_A_EXECUTION_CHAIN_INTERRUPTION_RESUME_PASS = false`, and `PHASE_A_EXECUTION_CHAIN_AUDIT_PASS = false`.

The failure-stop rule is active. No resume, analysis, verifier, publisher, schema, writer, backend, metric, parameter, scene, seed, or Gate implementation was changed. No Formal Execution Lock was built, no formal Stage-0 cache was read, and no formal backend trial ran.
