# Stage 2 Day 14 Final Decision Contract

Day 14 is a read-only scientific decision over frozen Stage 2 evidence. It asks
whether coherent weak-direction bias is stably detectable by an online statistic
that requires no ground truth. It does not run calibration, evaluation, Reserved
Test, MAP/LIO, Stage 2B/2C updates, or any Stage 3 component.

The primary statistic remains `huber_cusum_max`, and the locked threshold remains
`13.745952939169019`. No statistic, threshold, window, stress, or seed may be
selected or modified after seeing the Day 13 evidence.

## Four non-compensating Gates

The overall Gate passes only if all four Gates pass. There is no averaging,
majority vote, or mechanism-based override.

1. Separability requires the frozen AUROC/FPR criteria. Both the lenient
   interpretation (at least one sweep reaches AUROC 0.80) and strict interpretation
   (both sweeps reach it) are reported. Low matched-clean FPR cannot replace poor
   AUROC or the observed low TPR.
2. Cross-geometry stability uses only the locked per-geometry median
   coherent-minus-clean score effect and treats geometry seed as the independent
   unit. Pooled frames are not substitutes.
3. Causal consistency separates harmful-update association from Huber gross-control
   stability. A harmful mechanism may be supported while stable online
   discrimination is not.
4. The no-GT Gate requires static dependency audit plus trajectory,
   detector/window, and primary-statistic equivalence after GT removal. GT remains
   permitted only in offline causal evaluation.

## Frozen conclusion

The corrected Geometry and Observation AUROCs are below 0.80, so separability
fails even under the most lenient interpretation. Geometry L4 gross handling is
also level-dependent. Stage 2 therefore fails and the route transitions to
`PIVOT`. `DAY14_DECISION_PASS` means only that the evidence audit and decision
program completed correctly; it never means `STAGE2_GATE=PASS`.

Stage 3, Stage 4, Patent 2, the complete robust Degen-LIO T-RO route, FAST-LIO2
estimator integration, and risk-warning claims are not authorized.

