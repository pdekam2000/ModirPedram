import numpy as np


def _forward_returns(close_values, k):
    n = len(close_values)
    out = np.full(n, np.nan)
    if n > k:
        out[: n - k] = (close_values[k:] - close_values[:-k]) / close_values[:-k]
    return out


def discover_seasonal_bias(df, forward_k=5, group_by="hour", min_samples=30, min_edge=0.0003):
    """Find the single hour-of-day (or day-of-week) bucket with the
    strongest average forward return, on in-sample data only. Returns a
    rule describing that bucket + direction, or None if nothing clears the
    thresholds.
    """
    close = df["Close"].values
    fwd = _forward_returns(close, forward_k)

    if group_by == "hour":
        keys = df["Time"].dt.hour.values
    elif group_by == "dayofweek":
        keys = df["Time"].dt.dayofweek.values
    else:
        raise ValueError(f"unknown group_by: {group_by}")

    valid = ~np.isnan(fwd)
    keys_valid = keys[valid]
    fwd_valid = fwd[valid]

    best = None
    for key in np.unique(keys_valid):
        mask = keys_valid == key
        n = int(mask.sum())
        if n < min_samples:
            continue
        mean_fwd = float(fwd_valid[mask].mean())
        if abs(mean_fwd) < min_edge:
            continue
        score = abs(mean_fwd) * n
        if best is None or score > best["score"]:
            best = {
                "group_by": group_by,
                "key": int(key),
                "forward_k": forward_k,
                "direction": "long" if mean_fwd > 0 else "short",
                "mean_forward_return": mean_fwd,
                "sample_size": n,
                "score": score,
            }
    return best


def signal_end_indices(df, rule):
    """Every bar index matching the discovered hour/day-of-week bucket —
    the signal "completes" at that bar's close, so backtest_entries will
    enter on the next bar's open."""
    if rule["group_by"] == "hour":
        keys = df["Time"].dt.hour.values
    else:
        keys = df["Time"].dt.dayofweek.values
    return [i for i, k in enumerate(keys) if k == rule["key"]]
