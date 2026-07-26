# Measurement Pilot Scientific Audit

This stage audits the failed MUN-FRL Measurement pilot without tuning the
detector or trying to improve its reported result.  The source pilot remains at
`artifacts/current/measurement_real_validation_pilot/`; its deterministic tree
SHA-256 is
`d4185c7269a0cd2c34aaa5951793962503cca88b0b8691c85428a23442fce849`.

The audit freezes score polarity from the formula contract, checks the positive
class and ranking implementation, proves or rejects ODI spectral independence,
reconstructs the exact future-error and timing definitions, traces the
weak-direction coordinate chain, tests the preregistered interval labels and
reference axis, and distinguishes trigger implementation from real-domain
threshold transfer.

Run:

```bash
python3.11 scripts/140_run_measurement_pilot_scientific_audit.py \
  --repository-root /home/lj/Degen-LIO \
  --pilot-artifact-dir /home/lj/Degen-LIO/artifacts/current/measurement_real_validation_pilot \
  --bag /home/lj/Degen-LIO-data/day7_minimal_samples/mun_frl/lighthouse_francis_sample.bag \
  --output-dir /home/lj/Degen-LIO/artifacts/current/measurement_pilot_scientific_audit

python3.11 scripts/141_verify_measurement_audit_artifacts.py \
  --audit-dir /home/lj/Degen-LIO/artifacts/current/measurement_pilot_scientific_audit
```

The generator refuses to overwrite an existing audit directory and verifies
the frozen pilot tree and bag checksums before analysis.  The verifier requires
all tables, figures, reports, decisions, corrected-evaluation evidence, and
complete SHA-256 coverage.

The composite `EVALUATION_BUG_CONFIRMED` follows decision rule A: a component
implementation defect must materially change a formal result.  Component flags
remain explicit even when their corrected values do not change any gate.  If
the frozen labels are invalid, rule B takes precedence as the primary category;
concurrent reference insufficiency is retained as a secondary scientific
limitation rather than hidden.

No audit code changes ODI, AIS, Schur information, eigengap, weak-direction,
threshold, interval, reference axis, or the original negative artifact.
