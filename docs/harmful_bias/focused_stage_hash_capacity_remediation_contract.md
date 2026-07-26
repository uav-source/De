# Focused Stage-Hash Capacity Remediation Contract

This bounded Day 6 remediation changes only the diagnostic stage-record
capacity from 26 to 51. The inclusive scan window remains 155 through 205.
The maximum is a compile-time named constant; a 52-record window must remain
rejected.

The authorized FAST delta is limited to the stage-hash header, implementation,
and its unit test. Formal estimator mathematics, hash serialization, coherent
map snapshots, ikd-tree behavior, `laserMapping.cpp`, build configuration, and
thread configuration remain frozen.

Four new Quick Shack replay identities are authorized only after the capacity,
build, FAST test, Degen test, source-lock, and binary-lock gates all pass. The
runs are sequential and use ROS master ports 20311 through 20314. A fifth run
is not authorized.

The existing focused comparison and classification semantics remain frozen.
This remediation cannot authorize Day 7, Stage 3, Stage 4, FAST-LIO2
integration, detector execution, ODI, weak-direction computation, or public
risk claims. `STAGE2_GATE` remains `FAIL` and `TRANSITION` remains `PIVOT`.
