# ODI / Entropy Equivalence Audit

For the exported three-eigenvalue translation spectrum,

`effective_rank_trans = 3 - 2 * ODI_trans`

and

`spectral_entropy_trans = log(3 - 2 * ODI_trans)`.

The derivative is strictly negative throughout the valid ODI domain.  Across
all 1719 valid real frames, ODI versus
raw entropy has Spearman -1.000000000000,
Kendall -1.000000000000, risk-rank
equality 1.000000000000,
and zero monotonic violations.  The fixed-seed 10,000-positive-spectrum audit
also has zero violations.

ODI cannot claim independent ranking or AUROC advantage over spectral entropy.
The stored normalized eigenvalues omit epsilon, so their independently
recomputed unregularized entropy has a tiny numerical difference; this does not
undo the exact relationship between ODI and the entropy field actually exported
by Measurement mode.
