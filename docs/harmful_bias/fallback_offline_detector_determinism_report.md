# Fallback C Offline Production Detector Determinism Report

Fallback C did not pass. `fresh_process_run_1` stopped at frozen `record_index=284` (`scan_index=287`, five correspondences): the existing runtime adapter returned structured `TOO_FEW_CORRESPONDENCES` with null formal metrics, while the direct production entrypoint returned metrics. The locked comparison helper then raised on the null/numeric structural mismatch. The locked run directory could not be deleted or replayed.

Runs 2 and 3 each completed 487 inputs and outputs (486 valid, one invalid), with zero input mutation, detector exception, schema rejection, or forbidden output field. Their per-record checksums, exact JSON lines, and whole-file SHA matched, but two completed runs cannot establish the required three-process result. No canonical run_1 output was designated.

`OFFLINE_PRODUCTION_DETECTOR_DETERMINISM_PASS=false`, `FALLBACK_C_PASS=false`, `DAY6_FALLBACK_FUNCTIONAL_DIAGNOSTICS_RECOMMENDED=false`, and `DAY6_QUICK_DIAGNOSTICS_AUTHORIZED=false`. This is engineering failure evidence only; detector effectiveness and harmful-bias detectability were not evaluated. No ROS, FAST-LIO2, Development, Holdout, or Future Test execution occurred. Formal Degen-LIO remains incomplete.
