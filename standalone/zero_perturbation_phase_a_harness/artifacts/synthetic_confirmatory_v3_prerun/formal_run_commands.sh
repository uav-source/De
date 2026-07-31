#!/usr/bin/env bash
set -euo pipefail
# Frozen commands only; this file was not executed during pre-run qualification.
cd /home/lj/zero_perturbation_phase_a_harness_20260729_1407
git switch feature/zero-perturbation-synthetic-confirmatory-v3-prerun
test "$(git rev-parse HEAD)" = "$(git rev-list -n 1 archive/zero-perturbation-synthetic-confirmatory-v3-pre-run-pass)"
# Fresh and infrastructure-resume modes intentionally execute the exact same frozen command.
case "${1:-fresh}" in
  fresh) env -u PYTHONPATH PYTHONNOUSERSITE=1 MAMBA_ROOT_PREFIX=/home/lj/.local/share/degen-lio-micromamba /home/lj/.local/bin/micromamba run -n degen-lio-zprm-py311 python scripts/run_synthetic_confirmatory_v3.py --manifest frozen_assets/synthetic_confirmatory_formal_manifest_v3.json --run-id synthetic-confirmatory-v3 --runtime-root /home/lj/zero_perturbation_runtime/confirmatory/synthetic_confirmatory_v3 --workers 2 --resume ;;
  resume) env -u PYTHONPATH PYTHONNOUSERSITE=1 MAMBA_ROOT_PREFIX=/home/lj/.local/share/degen-lio-micromamba /home/lj/.local/bin/micromamba run -n degen-lio-zprm-py311 python scripts/run_synthetic_confirmatory_v3.py --manifest frozen_assets/synthetic_confirmatory_formal_manifest_v3.json --run-id synthetic-confirmatory-v3 --runtime-root /home/lj/zero_perturbation_runtime/confirmatory/synthetic_confirmatory_v3 --workers 2 --resume ;;
  *) echo 'usage: formal_run_commands.sh [fresh|resume]' >&2; exit 2 ;;
esac
env -u PYTHONPATH PYTHONNOUSERSITE=1 MAMBA_ROOT_PREFIX=/home/lj/.local/share/degen-lio-micromamba /home/lj/.local/bin/micromamba run -n degen-lio-zprm-py311 python scripts/analyze_synthetic_confirmatory_v3.py --manifest frozen_assets/synthetic_confirmatory_formal_manifest_v3.json --runtime-root /home/lj/zero_perturbation_runtime/confirmatory/synthetic_confirmatory_v3
env -u PYTHONPATH PYTHONNOUSERSITE=1 MAMBA_ROOT_PREFIX=/home/lj/.local/share/degen-lio-micromamba /home/lj/.local/bin/micromamba run -n degen-lio-zprm-py311 python scripts/verify_synthetic_confirmatory_v3.py --manifest frozen_assets/synthetic_confirmatory_formal_manifest_v3.json --runtime-root /home/lj/zero_perturbation_runtime/confirmatory/synthetic_confirmatory_v3
env -u PYTHONPATH PYTHONNOUSERSITE=1 MAMBA_ROOT_PREFIX=/home/lj/.local/share/degen-lio-micromamba /home/lj/.local/bin/micromamba run -n degen-lio-zprm-py311 python scripts/publish_synthetic_confirmatory_v3.py --manifest frozen_assets/synthetic_confirmatory_formal_manifest_v3.json --runtime-root /home/lj/zero_perturbation_runtime/confirmatory/synthetic_confirmatory_v3
env -u PYTHONPATH PYTHONNOUSERSITE=1 MAMBA_ROOT_PREFIX=/home/lj/.local/share/degen-lio-micromamba /home/lj/.local/bin/micromamba run -n degen-lio-zprm-py311 python scripts/verify_synthetic_confirmatory_v3_artifact.py --manifest frozen_assets/synthetic_confirmatory_formal_manifest_v3.json --runtime-root /home/lj/zero_perturbation_runtime/confirmatory/synthetic_confirmatory_v3
