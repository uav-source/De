#!/usr/bin/env python3
"""Minimal Matplotlib/Agg smoke check without forcing a font scan."""

from __future__ import annotations

import os
from pathlib import Path


def main() -> int:
    os.environ.setdefault("MPLBACKEND", "Agg")

    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    out_dir = Path(os.environ.get("MPLCONFIGDIR", "."))
    out_dir.mkdir(parents=True, exist_ok=True)

    fig = plt.figure(figsize=(0.5, 0.5))
    fig.savefig(out_dir / "prewarm_matplotlib.png", dpi=10)
    plt.close(fig)

    print(f"matplotlib prewarm minimal OK: MPLCONFIGDIR={out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
