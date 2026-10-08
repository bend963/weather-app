# Forecast methodology

All values are stored in SI (°C, mm, m/s) and converted only in the API
response.

## Ensemble statistics (`forecast/ensemble.py`)

For every hour, across ensemble members:

* temperature P10, P25, P50, P75, P90
* median dewpoint and cloud cover
* wind speed P10/P50/P90 per member, and direction from the **mean wind
  vector** (averaging angles directly would turn 350° and 10° into 180°)
* precipitation P50/P75/P90, ensemble mean, and exceedance probabilities
  for: trace (>0.1 mm), ≥0.01″, ≥0.10″, ≥0.25″, ≥0.50″, ≥1.00″

"Chance of rain" (`precip_probability`) follows the NWS PoP definition: the
fraction of members with at least 0.01″.

## Daily summaries

Computed **per member first**, then summarized: each member's daily high, low,
total precipitation and peak wind, then percentiles across members. The median
of members' highs is a true "most likely high"; the maximum of hourly medians
would understate it. Days are local days in the grid point's timezone; a day
needs at least 12 forecast hours to be summarized. A histogram of members'
highs is stored for the detail drawer.

## Confidence (`forecast/confidence.py`)

Confidence is **ensemble agreement**, not a calibrated probability of being
correct.

* Temperature agreement: `100 · exp(−max(P90 − P10 − 1 °C, 0) / 4 °C)`.
  A 2 °C spread scores ~78, 4 °C ~47, 6 °C ~29.
* Rain agreement: `100 · |2p − 1|`. Members agreeing on dry (p≈0) or wet (p≈1)
  score high; a 50% chance scores 0.
* Overall: 0.6 · temperature + 0.4 · rain.
* Levels: high ≥ 65, medium ≥ 35, otherwise low.

Once observations are collected, these should be recalibrated by lead time
against actual forecast error (forecast history makes that possible).

## Rain outlook

The next window where hourly chance reaches 40% opens the outlook; it extends
while chance stays at or above 25%. *Expected* is the sum of hourly ensemble
means across the window (means add across hours; percentiles don't). The
*high-end scenario* is the 90th-percentile daily total for the day(s) the window
falls on, or the expected amount if larger.

## Mock provider (`forecast/providers/mock.py`)

A synthetic 50-member ensemble, deterministic per (grid cell, run):

* climatology by latitude and season, with hemispheres flipped
* diurnal cycle on local solar time, damped by cloud
* "true" weather systems: sums of multi-day waves driving temperature and a
  moisture index; rain falls when moisture crosses a threshold, with lognormal
  amount spread and warm-afternoon convective boosts
* per-run error that grows with lead time, so successive runs converge on the
  same target (what makes the history page meaningful)
* per-member perturbations with spread growing with lead time
