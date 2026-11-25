"""Matplotlib figures used by the app and the PDF report."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .data import TestDataset, spectrum  # noqa: E402

COLOR = "#1f3a5f"


def time_series(ds: TestDataset, channels: list[str] | None = None, limits: dict | None = None):
    """One subplot per channel, with optional horizontal acceptance limits."""
    channels = channels or ds.channels
    limits = limits or {}
    fig, axes = plt.subplots(len(channels), 1, figsize=(8, 1.9 * len(channels)), sharex=True, squeeze=False)
    for ax, name in zip(axes[:, 0], channels):
        ax.plot(ds.time, ds.channel(name), color=COLOR, linewidth=0.8)
        lim = limits.get(name, {})
        for key in ("lower", "upper"):
            # An RMS limit is not comparable to instantaneous values, so it is not drawn.
            value = None if lim.get("metric") == "rms" else lim.get(key)
            if value is not None:
                ax.axhline(value, color="#c0392b", linestyle="--", linewidth=1, label=f"{key} limit")
        ax.set_ylabel(name, fontsize=8)
        ax.grid(alpha=0.3)
    axes[-1, 0].set_xlabel(f"{ds.time_column}")
    fig.tight_layout()
    return fig


def psd(ds: TestDataset, channel: str):
    """Power spectral density on a log scale."""
    freqs, power = spectrum(ds, channel)
    fig, ax = plt.subplots(figsize=(8, 3))
    ax.semilogy(freqs, power, color=COLOR, linewidth=0.9)
    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel(f"PSD of {channel}")
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    return fig
