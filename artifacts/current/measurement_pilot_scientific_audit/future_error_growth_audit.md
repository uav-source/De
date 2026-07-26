# Future Error Growth Audit

The original formal implementation is

`e_k = ||R p_hat_k + t - r(t_k)||_2`

`j(k) = min{j : t_j >= t_k + 5.0 s}`

`future_growth_k = e_j(k) - e_k`.

It is scalar absolute-position-error growth, not the norm of a difference of
error vectors.  RTK is interpolated at estimator timestamps; alignment is one
global rigid SE(3) Kabsch fit with unit scale.  The first-at-or-after index makes
the actual horizon median 5.053112 s, q95
5.099507 s, and maximum
5.154748 s.  Exact vector interpolation at `t+5`
changes the frozen-interval ODI correlation only non-materially and does not
change any gate.  Tail frames without five seconds remain missing rather than
reusing the current frame.  The 1/3/10 s results are sensitivity diagnostics;
five seconds remains the sole formal window.
