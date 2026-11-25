# TP-HL-001 – Heated loop endurance test procedure (fictitious example)

This document is a fictitious example created for the Engineering Data Assistant demo.
It does not describe any real facility or product.

## Purpose

Verify that the heated water loop reaches its nominal operating point and stays within
its acceptance limits during a 60-second steady-state run.

## Test conditions

- Inlet water temperature: 40 °C ± 2 °C.
- Heater set point: outlet temperature 78 °C.
- Pump speed: nominal (about 1490 rpm).
- Sampling: all channels recorded at 400 Hz.

## Acceptance criteria

The run is accepted only if all the following criteria are met over the whole recording:

- Outlet temperature (outlet_temp_C) must never exceed 85 °C.
- Loop pressure (pressure_bar) must stay between 2.0 bar and 3.5 bar.
- Flow rate (flow_rate_kg_s) must never drop below 0.8 kg/s.
- Pump vibration (accel_pump_g) RMS over the run must not exceed 0.35 g.

## Actions on failure

If a criterion is not met, record the time and duration of the exceedance in the test
report, inform the test lead, and refer to the troubleshooting guide TG-HL-003 before
repeating the run.
