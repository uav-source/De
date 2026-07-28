# Phase A v1.2 Stage-1 Result Contract Invalidation

The Stage-1 authorization rooted at commit
`02b24c2a0d2d492b756a0dfb8f762410352455fa` is invalidated before execution.
No formal run ID was created, no backend was executed, no trial result was
written, and no scientific result was exposed.

The frozen writer omitted `scene_variant` and `snapshot_lock_sha256`, used
legacy solver and failure-classification names, used an invalid Open3D
correspondence field name, and used an invalid PCL exit-code field name. Resume
did not validate the complete output schema, and no frozen independent result
verifier or publisher existed.

This is an execution-contract failure. It is not an Open3D, PCL, snapshot, or
zero-perturbation scientific failure.
