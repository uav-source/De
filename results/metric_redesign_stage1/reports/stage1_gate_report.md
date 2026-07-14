# Metric Redesign Stage 1 Gate Report

Scientific decision: **NO-GO**.

Execution success and scientific acceptance are separate. A NO-GO does not indicate a pipeline failure.

## Independent-sample accounting

- Geometry sequences: 15
- Independent sensor runs: 30
- Process trials are aggregated within each sensor run and are not counted as independent ODI samples.

## Level summary

| Level | N sensor | ODI_trans median | lambda_min_trans_normalized median | weak-subspace alignment median | axis drift median |
|---|---:|---:|---:|---:|---:|
| L0 | 6 | 0.0617491 | 126.144 | 0 | 3.79692e-05 |
| L1 | 6 | 0.490806 | 4.84244 | 0.997932 | 0.000567429 |
| L2 | 6 | 0.503566 | 3.19408 | 0.99943 | 0.000120354 |
| L3 | 6 | 0.518191 | 1.20745 | 0.999937 | 0.000778224 |
| L4 | 6 | 0.529614 | 0.188788 | 0.999999 | 0.00158867 |

## Correlation summary

| Metric | Expected | rho | block bootstrap 95% CI | N | seed direction stable | gate |
|---|---|---:|---:|---:|---|---|
| ODI | positive | 0.373043 | [0.0352928, 0.54441] | 24 | True | False |
| ODI_trans | positive | 0.377391 | [-0.024732, 0.543871] | 24 | True | False |
| AIS_trans_normalized | negative | -0.383478 | [-0.551998, 0.0837242] | 24 | True | False |
| lambda_min_trans_normalized | negative | -0.401739 | [-0.603571, 0.101548] | 24 | True | False |
| condition_number_trans | positive | 0.384348 | [-0.100802, 0.580749] | 24 | True | False |
| weak_trans_subspace_alignment | positive | 0.384348 | [-0.00879808, 0.563783] | 24 | True | False |

## Gate checks

- all_levels_present: True
- lambda_strictly_decreases: True
- lambda_not_all_zero: True
- ODI_trans_increases: True
- weak_alignment_L2_L4: True
- oc_false_trigger_ratio: 0.0
- oc_false_trigger_pass: True
- at_least_one_redesigned_metric_passes: False

## Claim boundary

This stage evaluates finite-patch synthetic geometry and a 6DoF motion-propagation surrogate only. It does not validate ODI, implement a weak-subspace update, or constitute a complete Degen-LIO estimator.
