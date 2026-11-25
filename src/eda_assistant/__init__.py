"""Engineering Data Assistant: analyze test data, generate reports, ask questions in plain language."""

from .data import TestDataset, channel_statistics, from_frame, load_csv, overview, spectrum_peaks, threshold_check
from .docs import DocumentIndex

__all__ = [
    "TestDataset",
    "DocumentIndex",
    "load_csv",
    "from_frame",
    "overview",
    "channel_statistics",
    "spectrum_peaks",
    "threshold_check",
]
__version__ = "0.1.0"
