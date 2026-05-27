# Day 1-14 Problem Statement

## Frozen Question

Day 1-14 validates one question only:

> Do tunnel-like environments cause a concentrated whitened pose information
> spectrum, does the resulting weak direction align with the tunnel axis or
> the maximum drift direction, and can ODI explain axis/weak-direction drift?

This phase is a minimum probe. It is not a paper draft, not a full benchmark,
not a full Degen-LIO method, and not a claim that a production LIO system has
already been improved.

## Scope

The phase uses a synthetic minimum benchmark with four sequences:

| Sequence | Role |
| --- | --- |
| Open Control | Negative control: low degeneracy and no stable weak direction. |
| Straight Tunnel | Primary positive case: weak translation along tunnel axis. |
| Curved Tunnel | Local-axis case: weak direction should follow local geometry. |
| Repetitive Tunnel | Hard positive case: axis weakness plus repeated structure risk. |

Only the 6DoF pose perturbation block is analyzed:

```text
delta x_p = [delta theta, delta p] in R^6
```

Velocity and IMU bias are intentionally excluded from the main Day 1-14
spectrum analysis. They may be added later only after the 6DoF contract is
validated.

## Main Hypothesis

In tunnel-like geometry, point-to-plane LiDAR constraints provide strong
information in wall-normal and floor-normal directions but weak information
along the tunnel axis. After pose-scale whitening, this appears as a
concentrated information spectrum. The weakest translation component should
align with the tunnel axis or with the observed dominant drift direction.

## Evidence Required By Day 14

The Day 14 decision must be based on generated files and scripts:

- Four minimum sequences generated and evaluated.
- Whitened information matrices without NaN/Inf and with PSD behavior.
- ODI, AIS, lambda_min, and condition_number exported for every frame.
- Weak direction and axis alignment exported for every frame where reliable.
- Axis/cross/weak-drift metrics computed from estimated and ground-truth poses.
- Script-generated figures and tables.
- A Go/No-Go report that includes failures instead of hiding them.

## Non-Goals

- No large-scale benchmark.
- No FAST-LIO2 integration requirement during Day 1-14.
- No full Degen-LIO weak-subspace update.
- No real-data generalization.
- No paper polishing.
- No manual figure editing.
- No claims based only on ATE.

