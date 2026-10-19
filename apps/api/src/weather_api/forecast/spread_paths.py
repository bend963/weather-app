"""Turn published percentiles into "spread paths" the member-based pipeline can use.

WeatherNext 3's BigQuery tables publish, for every hour, the 10th, 25th, 50th,
75th and 90th percentiles (and the mean) across its ensemble, not the members
themselves. The rest of the app computes everything from members, so each
hour's percentiles are expanded into PATH_COUNT values at evenly spaced
quantile levels, and path k takes the same level at every hour.

What that preserves, and what it doesn't:

* Hourly percentiles come back exactly. The levels are 0, 1/40, ..., 1, so
  np.percentile over the paths lands on the published p10/p25/p50/p75/p90.
* Hourly chances (rain above a threshold) are read off the interpolated
  distribution, which is as good as five percentiles allow.
* Precipitation keeps its published mean: what the paths miss is added to the
  wettest paths above p90, where a skewed distribution's mass is.
* Day-level values assume the paths are perfectly correlated in time (a warm
  path stays warm all day). Daily highs and lows are then close to what the
  members would give; daily rain totals spread somewhat wider than the real
  members would, because real wet hours don't always line up.

Outside p10..p90 the distribution is extended by continuing the outer slopes,
then clipped to each variable's physical range.
"""

import numpy as np

#: The published percentile levels, as fractions.
KNOTS = np.array([0.10, 0.25, 0.50, 0.75, 0.90])
PATH_COUNT = 41
LEVELS = np.linspace(0.0, 1.0, PATH_COUNT)

# Quantile levels with the two extrapolated ends, and the matrix that maps the
# seven values at those levels onto the path levels (linear interpolation).
_XS = np.concatenate([[0.0], KNOTS, [1.0]])
_WEIGHTS = np.stack([np.interp(LEVELS, _XS, np.eye(len(_XS))[j]) for j in range(len(_XS))], axis=1)


def spread_paths(
    percentiles: np.ndarray,
    *,
    lower: float | None = None,
    upper: float | None = None,
) -> np.ndarray:
    """(5, T) values at KNOTS -> (PATH_COUNT, T) paths, sorted low to high."""
    q = np.sort(np.asarray(percentiles, dtype=float), axis=0)  # guard against rounding
    ends = 0.10 / 0.15  # the outer gaps (0.10) relative to the knot gaps next to them (0.15)
    lo = q[0] - (q[1] - q[0]) * ends
    hi = q[4] + (q[4] - q[3]) * ends
    values = _WEIGHTS @ np.vstack([lo, q, hi])
    if lower is not None or upper is not None:
        values = np.clip(values, lower, upper)
    return values


def precipitation_paths(percentiles: np.ndarray, mean: np.ndarray) -> np.ndarray:
    """Spread paths for precipitation that also keep the published hourly mean."""
    paths = spread_paths(percentiles, lower=0.0)
    deficit = np.asarray(mean, dtype=float) - paths.mean(axis=0)
    tail = KNOTS[-1] < LEVELS
    # Adding to the paths above p90 keeps p10..p90 untouched and the order intact.
    add = np.where(deficit > 0, deficit * PATH_COUNT / tail.sum(), 0.0)
    paths[tail] += add
    return paths


def wind_paths(
    speed_percentiles: np.ndarray, mean_u: np.ndarray, mean_v: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """u and v paths whose speeds follow the speed percentiles.

    Every path points along the mean wind, so the direction the app shows
    (worked out from the mean u and v) is the published mean wind's direction.
    """
    speed = spread_paths(speed_percentiles, lower=0.0)
    mean_u = np.asarray(mean_u, dtype=float)
    mean_v = np.asarray(mean_v, dtype=float)
    norm = np.hypot(mean_u, mean_v)
    calm = norm < 1e-9
    unit_u = np.where(calm, 0.0, mean_u / np.where(calm, 1.0, norm))
    # With no mean wind there is no direction to keep; call it northerly.
    unit_v = np.where(calm, -1.0, mean_v / np.where(calm, 1.0, norm))
    return speed * unit_u, speed * unit_v
