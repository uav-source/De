# Diagnostic Benchmark Paper Skeleton

This paper is positioned as a diagnostic benchmark / failure-analysis contribution, not a validated Degen-LIO estimator method.

## Title Candidates

- [T01] A Diagnostic Benchmark for LiDAR-Inertial Degeneracy in Synthetic Tunnel-Like Scenes (diagnostic benchmark; recommended=true)
- [T02] Failure Analysis of Metric Validity under Synthetic Tunnel-Like Degeneracy (failure analysis; recommended=false)
- [T03] A Reproducible Degeneracy Diagnosis Package for LIO Metric Stress Testing (artifact paper; recommended=false)
- [T04] Degen-LIO Estimator Update for Robust Tunnel Navigation (method paper; recommended=false)

Working title: **A Diagnostic Benchmark for LiDAR-Inertial Degeneracy in Synthetic Tunnel-Like Scenes**

## Abstract Skeleton

Background: LiDAR-inertial degeneracy can be diagnosed through controlled synthetic geometry and whitened information analysis.

Problem: Legacy toy evidence can be confounded by scene-family bias, and single metrics can fail strict validation.

Approach: We present a reproducible diagnostic benchmark, bias audit, unbiased toy probe, within-sequence/grouped/controlled metric stress tests, and a go/no-go claim-boundary gate.

Finding: The package supports diagnostic and failure-analysis claims, while method-update claims remain blocked.

Scope: No estimator update or weak-subspace update is implemented or authorized.

## Introduction

Goal: Position the work as diagnostic benchmark / failure analysis

Key points:
- degeneracy matters; previous overclaims are risky; this paper emphasizes reproducible boundaries

Evidence to cite:
- Day14 decision and Day24 claim map

Figures / tables:
- T01, F01

Claim boundary:
- do not imply method validation

Writing risk:
- overpromising novelty


## Related Work

Goal: Connect LIO degeneracy metrics, benchmarks, and reproducible artifacts

Key points:
- observability, information matrices, synthetic benchmarks, failure analysis

Evidence to cite:
- literature plus internal claim map

Figures / tables:
- none

Claim boundary:
- avoid claiming a new estimator

Writing risk:
- missing broader citations


## Problem Formulation and Diagnostic Objective

Goal: Define diagnostic objective and 6DoF pose-block information scope

Key points:
- pose-block spectrum; weak direction; metric validity as diagnostic target

Evidence to cite:
- Day6-9 definitions

Figures / tables:
- F02, Table P1

Claim boundary:
- diagnostic objective only

Writing risk:
- too close to method framing


## Synthetic Degeneracy Benchmark

Goal: Describe OC/ST/CT/RT scenes and reproducibility

Key points:
- geometry, GT, observations, configs, seeds, manifests

Evidence to cite:
- Day14/Day24 artifact inventory

Figures / tables:
- F01, Table B1

Claim boundary:
- synthetic benchmark only

Writing risk:
- synthetic-only attack


## Whitened Information and Weak-Direction Diagnostics

Goal: Show information spectra and weak-axis alignment

Key points:
- spectrum concentration; local-axis alignment; unreliable OC handling

Evidence to cite:
- Day9/Day14 figures and tables

Figures / tables:
- F02, F03

Claim boundary:
- geometry diagnosis, not drift proof

Writing risk:
- ODI overclaim risk


## Bias Audit and Unbiased Toy Probe

Goal: Explain legacy bias and unbiased protocol

Key points:
- legacy scene-family bias; all-zero applied bias; multi-trial probe

Evidence to cite:
- Day15-17 outputs

Figures / tables:
- F04, Table B2

Claim boundary:
- toy_lio is a probe, not real LIO

Writing risk:
- toy_lio attack


## Metric Validity Stress Tests

Goal: Report Day18-21 validation including negative results

Key points:
- within-sequence, grouped/LOSO, controlled partial, joint risk

Evidence to cite:
- Day18-21 tables

Figures / tables:
- F05-F08, Tables V1-V4

Claim boundary:
- negative evidence is informative

Writing risk:
- temptation to hide failures


## Go/No-Go Gate and Claim Boundary

Goal: Formalize why method update is blocked

Key points:
- Day22 No-Go; Day23/24 Route B; allowed/forbidden claims

Evidence to cite:
- Day22-24 tables

Figures / tables:
- Table G1, Table C1

Claim boundary:
- No-Go is valid outcome

Writing risk:
- appearing too conservative


## Discussion and Limitations

Goal: Discuss reviewer risks and future redesign routes

Key points:
- synthetic-only, toy_lio, metric failure, no estimator update

Evidence to cite:
- Day24 risk register

Figures / tables:
- Table R1

Claim boundary:
- future work must remain gated

Writing risk:
- reviewer skepticism


## Reproducibility Package

Goal: List scripts, manifests, release checklist

Key points:
- commands, smoke vs real plots, excluded caches

Evidence to cite:
- Day24 checklist and Day25 plan

Figures / tables:
- Table Rep1

Claim boundary:
- artifact reproducibility with scope limits

Writing risk:
- package hygiene


## Conclusion

Goal: Conclude diagnostic benchmark contribution with explicit boundaries

Key points:
- benchmark package; negative validity evidence; no method update

Evidence to cite:
- Day25 claim boundary

Figures / tables:
- none

Claim boundary:
- no estimator-method conclusion

Writing risk:
- overclaiming


## Forbidden Claims

- ODI robustly predicts drift: Do not use this robust ODI wording.
- ODI is superior to AIS/lambda_min: Do not claim ODI superiority.
- Degen-LIO estimator method is validated: Do not present an estimator method as validated.
- weak-subspace update is authorized: Do not implement or claim update authorization.
- joint risk features are validated predictors: Do not present joint risk as validated.

## Allowed Claims

- diagnostic benchmark is reproducible: The diagnostic benchmark package is reproducible under recorded scripts and manifests.
- legacy biased toy_lio is diagnostic only: Legacy biased toy_lio is useful as a bias-audit lesson only.
- negative metric-validity evidence is informative: Negative metric-validity evidence identifies failure modes and redesign needs.

## Figure/Table Checklist

- F01 (figure): Benchmark geometry overview: OC/ST/CT/RT scenes and local tunnel axes. source=configs/minibench and results/day14 artifacts
- F02 (figure): Weak-direction alignment examples from whitened information spectra. source=results/day14/tables/day09_alignment_summary.csv
- F03 (figure): Legacy vs unbiased toy_lio bias audit. source=results/day30/tables/day15_bias_audit.csv and day16 summary
- T01 (table): Day17 unbiased trial summary across sequences. source=results/day30/tables/day17_unbiased_probe_summary.csv
- T02 (table): Day18 within-sequence validation results. source=results/day30/tables/day18_sequence_validity_summary.csv
- T03 (table): Day19 grouped / LOSO summary. source=results/day30/tables/day19_loso_selection_results.csv
- T04 (table): Day20 controlled partial validity. source=results/day30/tables/day20_incremental_validity_summary.csv
- T05 (table): Day21 joint risk comparison. source=results/day30/tables/day21_joint_risk_comparison.csv
- T06 (table): Day22 gate decision. source=results/day30/tables/day22_gate_decision.csv
- T07 (table): Claim boundary table for paper writing. source=results/day30/tables/day25_claim_boundary_for_paper.csv
- T08 (table): Reproducibility command table. source=results/day30/tables/day25_reproducibility_plan.csv
