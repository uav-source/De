# Day 6 Bounded Formal Branch Reproduction Contract

This internal engineering audit executes exactly four sequential Quick Shack
replays with the frozen FAST-LIO2 binary, runtime parameters, coherent map
snapshot implementation, observation tap, compact writer, and in-call audit.
No fifth replay is authorized.

All six run pairs are compared using `SEMANTIC_OBSERVATION_V1` and the fixed
scan 135–160 stage-hash window. Identity fields, self checksums, output paths,
process identity, lock timing, snapshot copy timing, rebuild generation, and
map traversal order alone cannot establish a formal branch.

A formal branch requires a difference in prior state/covariance, logical map
content, formal correspondence, accepted-index digest, formal Jacobian,
innovation/residual, post-update state/covariance, insertion batch, or logical
map content after insertion. A traversal difference followed by a formal
correspondence difference at the same scan is only an association candidate,
not a root-cause proof.

The reproduction gate fails closed unless all four runs are complete, all 208
snapshot records are coherent, all continuity checks pass, all six semantic
and stage comparisons complete, and every semantic formal mismatch is
localized by complete stage evidence without an evidence gap.

Day 7 may only be recommended for a localized formal branch under the fixed
scope mapping. Day 7 remains unauthorized pending separate GPT audit.
Detector execution, ODI/AIS computation, weak-direction analysis, GT use,
FAST-LIO2 modification, rebuild, or test execution are outside this contract.

Fixed scientific state remains `STAGE2_GATE=FAIL`, `TRANSITION=PIVOT`,
`CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE=NOT_PROVEN`, and
`HARMFUL_BIAS_DETECTABILITY_STATUS=NOT_EVALUATED_DAY6_BOUNDED_FORMAL_BRANCH_REPRODUCTION`.
