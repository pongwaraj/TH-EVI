# Chiang Mai observed DC session energy

Effective local model reference: 19 October 2026. The versioned profile uses
**27 kWh per meaningful charging order**, rounded from 27.35075201988813.
This is connector energy per charging event, not power in kW or unique cars.

| Station | Observation window | Meaningful orders | Connector kWh | kWh/order |
| --- | --- | ---: | ---: | ---: |
| Meta Mall | 1 July - 30 September 2026 | 3,147 | 86,285.97 | 27.41848 |
| Grand Siri | 9 - 18 October 2026 | 71 | 1,728.75 | 24.34859 |
| Pooled | Non-overlapping station samples | 3,218 | 88,014.72 | 27.35075 |

Both samples use Normal orders with duration >= 300 seconds and connector
energy >= 1 kWh. The pooled mean is total kWh / total orders, not the mean of
the two station means. Grand Siri includes its opening day for order-size
analysis; this does not treat the partial opening day as a full demand day.
No customer, order, VIN or account identifiers are bundled. Source hashes and
the Grand Siri workbook sheet/range are recorded in
`data/chiang_mai_dc_session_energy.json`.

## Runtime behaviour

- `data/charging_behavior_profiles.json` is the shared province registry.
- `resolve_dc_session_energy` verifies counts, energy, pooling, rounding and
  profile provenance before applying a default. Missing/inconsistent evidence
  fails closed rather than falling back to 32 or 35 kWh.
- `/api/charging-demand/preview` and `/api/charging-demand/site-preview` may
  omit their session-energy field (or pass null) to use the province reference.
  Explicit positive values override it, with `source=caller_override` in
  `session_energy_basis`. In the Python site preview the same resolution occurs.
- `/api/charging-demand/basis` and `/site-reference` expose the reference and
  limitations. Provinces without their own evidence still require an explicit
  session-energy value; they do not borrow Chiang Mai's default.
- Provincial travel, AC access and efficiency inputs remain independently
  required. Supplying order size does not activate a provincial energy budget.
- Site choice and the reference-station daily kWh remain unchanged. The daily
  scale is still anchored to Meta Mall, not the new pooled order count. Only
  energy-to-event conversion and the existing order-size-dependent throughput
  limit use the new divisor. Under a binding throughput limit, served energy
  may change through plug-overhead accounting; energy demand must not inflate.

## Scope and limitations

This is an initial **urban public DC** reference, dominated by Meta Mall
(97.79% of orders). It is not validated for highways, other provinces, charging
visit counts, station choice or investment returns. Grand Siri has only ten
calendar days and is in its opening period. Future observations should be
held out from this calibration before evaluating accuracy.

The screening Heat Map remains screening scores and has no session divisor.
Legacy diagnostic calculations, manually specified API values, historical
proposals and previously saved preview outputs are **not silently rewritten**.
Do not use a legacy 35 kWh output alongside a new 27 kWh event count without
recalculating both with the same basis.

At fixed daily energy, changing 35 to 27 kWh increases event equivalents by
29.63%, not energy or revenue. At fixed event counts it reduces energy by
22.86%. These two calculation directions must not be mixed.

This change does not publish to Vercel or update a production database.
