"""Plotting helpers shared by the model modules."""
from __future__ import annotations

import base64
import io

import matplotlib
matplotlib.use("Agg")           # headless backend: render to buffer, never a window
import matplotlib.pyplot as plt

NAVY = "#1E2761"
DECLINE = "#B85042"


def fig_to_base64(fig) -> str:
    """Serialise a Matplotlib figure to a base64 PNG data string and close it."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")
