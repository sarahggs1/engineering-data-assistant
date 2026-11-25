# IG-HL-002 – Heated loop instrumentation (fictitious example)

This document is a fictitious example created for the Engineering Data Assistant demo.

## Channels

| Channel | Sensor | Unit | Accuracy |
|---|---|---|---|
| inlet_temp_C | Type K thermocouple | °C | ± 0.5 °C |
| outlet_temp_C | Type K thermocouple | °C | ± 0.5 °C |
| flow_rate_kg_s | Coriolis flow meter | kg/s | ± 0.2 % |
| pressure_bar | Piezoresistive pressure transducer | bar | ± 0.05 bar |
| accel_pump_g | Piezoelectric accelerometer on pump casing | g | ± 2 % |

## Sampling

All channels are sampled synchronously at 400 Hz. Frequency analysis is therefore valid
up to 200 Hz (Nyquist frequency).
