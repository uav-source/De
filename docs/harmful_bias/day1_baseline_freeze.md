# Harmful-Bias Multihyp Research Spike — Day 1 Baseline Freeze

## Outcome

Day 1 Remediation V2 restored the trusted historical HOME state, recovered the full Degen-LIO pytest baseline, and froze the approved four-layer engineering data namespace.

```text
HOME_STATE_RESTORATION_PASS=true
DEGEN_LIO_BASELINE_PASS=true
FASTLIO2_BASELINE_PASS=true
DATA_SPLIT_APPROVAL_APPLIED=true
DATA_NAMESPACE_FROZEN=true
DAY1_REMEDIATION_DIFF_SCOPE_PASS=true
DAY1_REMEDIATION_PASS=true
DAY1_BASELINE_FREEZE_PASS=true
DAY2_INTERFACE_AUDIT_AUTHORIZED=true
```

This authorization permits the separately scoped Day 2 interface audit. Day 2 has not started in this task.

## Frozen Git starting point

- starting branch: `decision/stage2-day14`
- starting HEAD: `531e25de917ec527645d2e6633592145826c81d6`
- Pivot tag: `checkpoint/stage2-day14-pivot-pass`
- spike branch: `spike/harmful-bias-multihyp-dev`
- tag and branch commit: `531e25de917ec527645d2e6633592145826c81d6`

The four pre-existing Day 1 files were preserved. No commit and no push were performed.

## Trusted HOME restoration

The trusted archive `$HOME/Degen-LIO-Day14-audit-v3.tar.gz` matched SHA-256:

```text
99ada237ea91e943c227d36324e77b853ceccde7c06e18d99fb42a4a275735e1
```

The archive passed gzip verification and its internal hash list had zero failures. Eight required historical HOME files were restored, with zero pre-existing matches and zero conflicts. No `before` evidence was regenerated.

The full pytest changed from:

```text
576 passed, 14 failed, 1 warning in 39.05s
```

to:

```text
590 passed, 1 warning in 51.96s
```

No source or test change was used to obtain the passing baseline.

## FAST-LIO2 baseline

The literal V2 text path `$HOME/FAST_LIO` is absent. The repository previously identified by the user and verified for this workspace is:

```text
$HOME/fastlio2_ws/src/FAST_LIO
```

- branch: `main`
- commit: `7cc4175de6f8ba2edf34bab02a42195b141027e9`
- worktree clean: `true`
- source modified: `false`
- build run: `false`
- rosbag run: `false`

The resolved real repository is therefore the frozen FAST-LIO2 baseline.

## Frozen namespace

Approval ID: `HBMH_DATA_SPLIT_APPROVAL_V1`.

The allocation is an engineering namespace decision, not scientific truth. All degenerate/control roles remain `UNVERIFIED`, ineligible as ground-truth labels, and ineligible as AUROC labels.

- Quick: one degenerate and one control.
- Development: three degenerate, two control, and one auxiliary.
- Holdout-Dev: one degenerate and one control.
- Future Test: four degenerate and four control from five sources.

All sequence IDs are unique. Cross-namespace overlap, cross-location-family overlap, Day 13 overlap, SubT selection, and Stairs selection are all zero. Holdout and Future execution remain unauthorized; Future run count is zero.

The Day 1 close-out hardening makes every namespace entry self-contained and explicitly marks both Holdout-Dev and Future Test as `sealed: true`. Every entry carries its canonical source ID, role, availability, hash semantics, provenance, scientific-label status, and `run_authorized: false`.

The frozen machine-readable files are:

- `manifests/harmful_bias/data_split_source_resolution.json`
- `manifests/harmful_bias/data_split_approval_v1.json`
- `manifests/harmful_bias/data_inventory_day1.csv`
- `manifests/harmful_bias/data_namespace_v1.yaml`
- `manifests/harmful_bias/data_namespace_selection_audit.csv`

## Scope boundary

No `src/`, `scripts/`, `tests/`, or `configs/` file changed. FAST-LIO2 stayed read-only. No data was downloaded, no observation tap was implemented, and no Quick, Development, Holdout, Future, scientific, rosbag, or build run occurred.

The scientific decision remains:

```text
STAGE2_GATE=FAIL
TRANSITION=PIVOT
STAGE3_START_AUTHORIZED=false
FAST_LIO2_INTEGRATION_AUTHORIZED=false
```

Formal Degen-LIO is not complete.
