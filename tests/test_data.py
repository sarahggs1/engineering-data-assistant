import numpy as np
import pandas as pd
import pytest

from eda_assistant.data import channel_statistics, from_frame, lowpass, overview, spectrum_peaks, threshold_check


def test_overview(dataset):
    info = overview(dataset)
    assert info["samples"] == 24000
    assert info["sample_rate_hz"] == pytest.approx(400)
    assert "outlet_temp_C" in info["channels"]
    assert "time_s" not in info["channels"]


def test_time_column_is_detected_and_data_sorted():
    frame = pd.DataFrame({"Time": [2.0, 0.0, 1.0], "x": [3.0, 1.0, 2.0]})
    ds = from_frame(frame)
    assert ds.time_column == "Time"
    assert list(ds.channel("x")) == [1.0, 2.0, 3.0]


def test_statistics_window(dataset):
    full = channel_statistics(dataset, "outlet_temp_C")
    steady = channel_statistics(dataset, "outlet_temp_C", start_s=50, end_s=60)
    assert steady["window_s"][0] >= 50
    assert steady["std"] < full["std"]


def test_unknown_channel(dataset):
    with pytest.raises(KeyError):
        channel_statistics(dataset, "nope")


def test_overshoot_is_detected(dataset):
    result = threshold_check(dataset, "outlet_temp_C", upper=85)
    assert not result["passed"]
    assert 40 < result["first_violation_s"] < 45


def test_limits_that_pass(dataset):
    assert threshold_check(dataset, "pressure_bar", lower=2.0, upper=3.5)["passed"]
    assert threshold_check(dataset, "accel_pump_g", upper=0.35, metric="rms")["passed"]


def test_spectrum_finds_pump_frequencies(dataset):
    freqs = [p["frequency_hz"] for p in spectrum_peaks(dataset, "accel_pump_g", n_peaks=2)["peaks"]]
    assert any(abs(f - 24.8) < 0.5 for f in freqs)
    assert any(abs(f - 124.0) < 0.5 for f in freqs)


def test_lowpass_removes_vibration(dataset):
    filtered = lowpass(dataset, "accel_pump_g", cutoff_hz=5)
    assert np.std(filtered) < 0.1 * np.std(dataset.channel("accel_pump_g"))
