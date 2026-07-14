# Stage 2B Column-Scaling Failure

Stage 2B is frozen at commit `c5fe3c5` and tag
`archive/weak-update-stage2b-no-go`. Its selective update transformed the
normal equation with a column operator (A):

\[
H_{old}=A^T H A, \qquad b_{old}=A^T b.
\]

Along one weak direction this produces (H_{old}=\alpha H) but
(b_{old}=\sqrt{\alpha}b). Consequently,

\[
\delta_{old}=-\frac{\sqrt{\alpha}b}{\Lambda_{prior}+\alpha H}.
\]

When measurement information dominates the prior, the correction approaches
(\delta_{full}/\sqrt{\alpha}): reducing alpha can increase the weak-direction
correction. This violates the intended attenuation semantics.

The compact evidence and checksums are preserved in
`artifacts/history/stage2b_column_scaling_no_go/`. The outcome remains:

- selective update: FAIL;
- FAST-LIO2 integration: NOT AUTHORIZED;
- risk warning: NOT AUTHORIZED.

