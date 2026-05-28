#!/usr/bin/env python3
"""Prewarm Matplotlib font/cache state for reproduction plotting."""

from __future__ import annotations

import os
from pathlib import Path


def main() -> int:
    os.environ.setdefault("MPLBACKEND", "Agg")
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import font_manager
    import matplotlib.pyplot as plt

    font_manager._load_fontmanager(try_read_cache=False)
    fig, ax = plt.subplots(figsize=(1.0, 1.0))
    ax.plot([0.0, 1.0], [0.0, 1.0])
    ax.set_title("prewarm")
    out_dir = Path(os.environ.get("MPLCONFIGDIR", "."))
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / "prewarm_matplotlib.png", dpi=30)
    plt.close(fig)
    print(f"matplotlib prewarmed: MPLCONFIGDIR={out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
