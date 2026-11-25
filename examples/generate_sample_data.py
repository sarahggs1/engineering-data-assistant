"""Generate a synthetic test run for a heated water loop.

The data is entirely fictitious. It mimics what a thermal-hydraulics test bench
records: inlet/outlet temperatures, pressure, flow rate and pump vibration.
A short outlet-temperature overshoot is included on purpose, so the acceptance
check has something to find.

    python examples/generate_sample_data.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

RATE_HZ = 400
DURATION_S = 60
PUMP_HZ = 24.8          # pump shaft speed (about 1490 rpm)
BLADE_PASS_HZ = 124.0   # 5 impeller blades x shaft speed


def generate(seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    t = np.arange(0, DURATION_S, 1 / RATE_HZ)

    ramp = 1 - np.exp(-t / 8)
    inlet = 40 + 0.3 * np.sin(2 * np.pi * t / 30) + rng.normal(0, 0.05, t.size)
    rise = 38 * ramp
    overshoot = 8.5 * np.exp(-(((t - 42.5) / 1.2) ** 2))  # heater controller overshoot
    outlet = inlet + rise + overshoot + rng.normal(0, 0.08, t.size)

    flow = 1.5 * (1 - np.exp(-t / 3)) + 0.02 * np.sin(2 * np.pi * 0.2 * t) + rng.normal(0, 0.01, t.size)
    flow = np.clip(flow, 0.85, None)
    pressure = 2.1 + 1.0 * ramp + rng.normal(0, 0.02, t.size)

    accel = (
        0.28 * np.sin(2 * np.pi * PUMP_HZ * t)
        + 0.12 * np.sin(2 * np.pi * BLADE_PASS_HZ * t + 0.4)
        + rng.normal(0, 0.05, t.size)
    )

    return pd.DataFrame(
        {
            "time_s": t.round(4),
            "inlet_temp_C": inlet.round(3),
            "outlet_temp_C": outlet.round(3),
            "flow_rate_kg_s": flow.round(4),
            "pressure_bar": pressure.round(4),
            "accel_pump_g": accel.round(4),
        }
    )


if __name__ == "__main__":
    out = Path(__file__).parent / "data" / "heated_loop_run_042.csv"
    out.parent.mkdir(exist_ok=True)
    generate().to_csv(out, index=False)
    print(f"Wrote {out}")
