"""Loading and analysis of engineering test data.

A test dataset is a table with one time column and one or more measurement
channels (temperatures, pressures, flow rates, accelerations...). Every
function here is deterministic and runs locally: the LLM assistant only ever
sees the small, structured results these functions return, never raw data.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import signal

TIME_CANDIDATES = ("time_s", "time", "t", "timestamp")


@dataclass
class TestDataset:
    """A loaded test run: a time axis plus numeric measurement channels."""

    name: str
    frame: pd.DataFrame
    time_column: str

    @property
    def channels(self) -> list[str]:
        return [c for c in self.frame.columns if c != self.time_column]

    @property
    def time(self) -> np.ndarray:
        return self.frame[self.time_column].to_numpy(dtype=float)

    @property
    def sample_rate_hz(self) -> float:
        dt = np.diff(self.time)
        return float(1.0 / np.median(dt))

    def channel(self, name: str) -> np.ndarray:
        if name not in self.channels:
            raise KeyError(f"Unknown channel '{name}'. Available: {', '.join(self.channels)}")
        return self.frame[name].to_numpy(dtype=float)


def load_csv(path: str | Path, time_column: str | None = None) -> TestDataset:
    """Load a CSV test file and validate it."""
    path = Path(path)
    frame = pd.read_csv(path)
    return from_frame(frame, name=path.stem, time_column=time_column)


def from_frame(frame: pd.DataFrame, name: str = "dataset", time_column: str | None = None) -> TestDataset:
    if time_column is None:
        lowered = {c.lower(): c for c in frame.columns}
        time_column = next((lowered[c] for c in TIME_CANDIDATES if c in lowered), frame.columns[0])
    if time_column not in frame.columns:
        raise ValueError(f"Time column '{time_column}' not found")

    numeric = frame.apply(pd.to_numeric, errors="coerce")
    keep = [c for c in numeric.columns if numeric[c].notna().any()]
    numeric = numeric[keep].dropna(subset=[time_column]).sort_values(time_column).reset_index(drop=True)
    if len(numeric) < 2:
        raise ValueError("The dataset needs at least two samples")
    return TestDataset(name=name, frame=numeric, time_column=time_column)


def overview(ds: TestDataset) -> dict:
    """Short description of the dataset: duration, sampling, channels, gaps."""
    t = ds.time
    missing = {c: int(ds.frame[c].isna().sum()) for c in ds.channels if ds.frame[c].isna().any()}
    return {
        "name": ds.name,
        "samples": int(len(t)),
        "duration_s": round(float(t[-1] - t[0]), 3),
        "sample_rate_hz": round(ds.sample_rate_hz, 3),
        "channels": ds.channels,
        "missing_values": missing,
    }


def channel_statistics(ds: TestDataset, channel: str, start_s: float | None = None, end_s: float | None = None) -> dict:
    """Descriptive statistics of one channel, optionally on a time window."""
    t, x = ds.time, ds.channel(channel)
    mask = np.ones_like(t, dtype=bool)
    if start_s is not None:
        mask &= t >= start_s
    if end_s is not None:
        mask &= t <= end_s
    x = x[mask]
    x = x[~np.isnan(x)]
    if x.size == 0:
        raise ValueError("No samples in the requested window")
    return {
        "channel": channel,
        "window_s": [float(t[mask][0]), float(t[mask][-1])],
        "count": int(x.size),
        "mean": float(np.mean(x)),
        "std": float(np.std(x)),
        "min": float(np.min(x)),
        "max": float(np.max(x)),
        "rms": float(np.sqrt(np.mean(x**2))),
        "p05": float(np.percentile(x, 5)),
        "p95": float(np.percentile(x, 95)),
    }


def lowpass(ds: TestDataset, channel: str, cutoff_hz: float, order: int = 4) -> np.ndarray:
    """Zero-phase Butterworth low-pass filter (useful to remove sensor noise)."""
    nyquist = ds.sample_rate_hz / 2
    if not 0 < cutoff_hz < nyquist:
        raise ValueError(f"cutoff_hz must be between 0 and {nyquist:.1f} Hz")
    b, a = signal.butter(order, cutoff_hz / nyquist)
    return signal.filtfilt(b, a, ds.channel(channel))


def spectrum(ds: TestDataset, channel: str) -> tuple[np.ndarray, np.ndarray]:
    """Power spectral density (Welch method) of a channel."""
    x = ds.channel(channel)
    x = x[~np.isnan(x)]
    nperseg = int(min(len(x), 4096))
    return signal.welch(x - np.mean(x), fs=ds.sample_rate_hz, nperseg=nperseg)


def spectrum_peaks(ds: TestDataset, channel: str, n_peaks: int = 3) -> dict:
    """Dominant frequencies of a channel, e.g. to identify a vibration source."""
    freqs, psd = spectrum(ds, channel)
    idx, _ = signal.find_peaks(psd, prominence=np.max(psd) * 0.05)
    idx = idx[np.argsort(psd[idx])[::-1]][:n_peaks]
    return {
        "channel": channel,
        "frequency_resolution_hz": float(freqs[1] - freqs[0]),
        "peaks": [{"frequency_hz": round(float(freqs[i]), 2), "power": float(psd[i])} for i in idx],
    }


def threshold_check(
    ds: TestDataset,
    channel: str,
    lower: float | None = None,
    upper: float | None = None,
    metric: str = "value",
) -> dict:
    """Check a channel against acceptance limits.

    metric="value" checks every sample; metric="rms" checks the RMS over the run.
    """
    if lower is None and upper is None:
        raise ValueError("Give at least one limit (lower or upper)")
    t, x = ds.time, ds.channel(channel)

    if metric == "rms":
        rms = float(np.sqrt(np.nanmean(x**2)))
        ok = (lower is None or rms >= lower) and (upper is None or rms <= upper)
        return {"channel": channel, "metric": "rms", "value": rms, "lower": lower, "upper": upper, "passed": bool(ok)}
    if metric != "value":
        raise ValueError("metric must be 'value' or 'rms'")

    bad = np.zeros_like(x, dtype=bool)
    if lower is not None:
        bad |= x < lower
    if upper is not None:
        bad |= x > upper
    result = {
        "channel": channel,
        "metric": "value",
        "lower": lower,
        "upper": upper,
        "passed": not bool(bad.any()),
        "samples_out_of_limits": int(bad.sum()),
        "fraction_out_of_limits": round(float(bad.mean()), 4),
        "min": float(np.nanmin(x)),
        "max": float(np.nanmax(x)),
    }
    if bad.any():
        result["first_violation_s"] = float(t[bad][0])
        result["last_violation_s"] = float(t[bad][-1])
    return result
