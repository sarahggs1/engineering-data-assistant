# TG-HL-003 – Heated loop troubleshooting guide (fictitious example)

This document is a fictitious example created for the Engineering Data Assistant demo.

## Outlet temperature overshoot

A short overshoot of the outlet temperature after the heater reaches its set point usually
comes from an aggressive heater controller tuning. Check the controller gains and the
derivative filter. An overshoot longer than 10 seconds may indicate a stuck flow valve.

## Pump vibration

The pump shaft frequency is about 24.8 Hz at nominal speed. A dominant peak at the
blade-pass frequency (5 × shaft frequency, about 124 Hz) is normal. A peak at 2 × shaft
frequency (about 50 Hz) suggests misalignment; a broadband rise suggests cavitation or
bearing wear. Compare the RMS value with the acceptance limit in TP-HL-001.

## Pressure drift

A slow pressure rise during warm-up is expected because of thermal expansion. A pressure
above 3.5 bar requires checking the expansion tank pre-charge.
