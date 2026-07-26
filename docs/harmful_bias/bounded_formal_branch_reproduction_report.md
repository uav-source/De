# Day 6 Bounded Formal Branch Reproduction Report

## Decision

The fixed four-replay execution completed successfully, but the formal branch reproduction Gate remains closed. Five of six semantic run pairs diverged beginning at scan 164 or scan 196, while the frozen stage-hash window ends at scan 160. The existing stage evidence therefore cannot localize the first semantic formal divergence. `FORMAL_BRANCH_REPRODUCED=false`, `FORMAL_BRANCH_STAGE_LOCALIZED=false`, `EXPERIMENT_A_PASS=false`, `DAY7_RECOMMENDED=false`, and `DAY7_AUTHORIZED=false`.

This is an evidence gap, not a no-difference result and not a root-cause proof. No classifier, comparator, finalizer, window, or Gate was modified after the runtime lock.

## Execution evidence

Exactly four sequential Quick Shack replays ran on ROS master ports 20211, 20212, 20213, and 20214. All wrapper exit codes were 0. Every run recorded 491 LiDAR callbacks, 9953 IMU callbacks, 490 runtime scans, 487 compact observations, 26 stage records over scans 135–160, and 52 coherent map snapshots. Across all runs, 208/208 snapshots were coherent and cross-scan continuity violations, tap drops, writer errors, in-call mutations, diagnostic mutations, schema rejects, and GT consumption were zero.

The raw runner exit code was 30 for each run; raw tail handoff was false and the frozen V5 adjudicated handoff was true for each run. Drain, normal shutdown, runtime products, and post-run process cleanup passed.

## Six-pair result

Semantic mismatch counts were 294, 0, 326, 294, 326, and 326 in fixed pair order r1-r2, r1-r3, r1-r4, r2-r3, r2-r4, r3-r4. The first divergences were record 193/scan 196 for r1-r2 and r2-r3, no divergence for r1-r3, and record 161/scan 164 for the three pairs involving r4.

The 135–160 stage window contained only map traversal-order differences. Raw LiDAR, IMU bundle, undistorted cloud, prior state/covariance, logical map content before/after, formal correspondence/J/h/residual, post-update state/covariance, and insertion batch all matched for every pair in that window. All six window-local classifications are `NO_FORMAL_DIVERGENCE`; globally, the later semantic divergence is unlocalized and therefore remains `EVIDENCE_GAP_FIXED_STAGE_WINDOW_DOES_NOT_COVER_FIRST_SEMANTIC_DIVERGENCE`.

Formal trajectory clustering produced three clusters: r1+r3, r2, and r4. No cluster is claimed to be correct.

## Scope and claim boundary

Map traversal differences alone are not formal FAST branches. Later semantic evidence shows formal correspondence/J/h/residual differences and subsequent prior-state/covariance differences, but the fixed stage evidence cannot identify the first divergent stage. Logical map-content, post-update-state, and insertion-batch identity outside the fixed stage window was not recorded here and is not inferred.

No detector ran; ODI/AIS and weak-direction quantities were not computed; GT was not used. FAST-LIO2, coherent snapshots, thread configuration, and scientific parameters were not modified. FAST was not rebuilt or tested. No commit or push was created. No fifth replay was run or recommended.

Day 7 still requires separate GPT audit authorization. The current evidence does not authorize FAST robust-update integration.

Fixed state remains `STAGE2_GATE=FAIL`, `TRANSITION=PIVOT`, `STAGE3_START_AUTHORIZED=false`, `FAST_LIO2_INTEGRATION_AUTHORIZED=false`, and `CROSS_PROCESS_BITWISE_REPLAY_EQUIVALENCE=NOT_PROVEN`.
