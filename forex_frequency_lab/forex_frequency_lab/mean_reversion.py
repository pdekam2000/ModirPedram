import numpy as np
import pandas as pd


def _zscore_from_ma(close, window):
    s = pd.Series(close)
    ma = s.rolling(window, min_periods=window).mean()
    std = s.rolling(window, min_periods=window).std()
    return ((s - ma) / std).values


def discover_mean_reversion_bias(df, ma_window=20, forward_k=5, extreme_quantile=0.9, min_samples=30):
    """On in-sample data: when price is unusually far (top `extreme_quantile`
    of |z-score|) from its own rolling moving average, does it tend to keep
    extending (continuation/momentum) or snap back toward the average
    (mean-reversion)? The z-score threshold that defines "unusually far" is
    fixed here and reused as-is out-of-sample.
    """
    close = df["Close"].values
    n = len(df)
    z = _zscore_from_ma(close, ma_window)

    fwd = np.full(n, np.nan)
    if n > forward_k:
        fwd[: n - forward_k] = (close[forward_k:] - close[:-forward_k]) / close[:-forward_k]

    threshold = np.nanquantile(np.abs(z), extreme_quantile)
    valid = ~np.isnan(z) & ~np.isnan(fwd) & (np.abs(z) >= threshold)
    n_samples = int(valid.sum())
    if n_samples < min_samples:
        return None

    z_dir = np.sign(z[valid])
    aligned = fwd[valid] * z_dir  # >0 = continuation (extends further from MA), <0 = reversion (back toward MA)

    mean_aligned = float(aligned.mean())
    if abs(mean_aligned) < 1e-6:
        return None

    return {
        "ma_window": ma_window,
        "forward_k": forward_k,
        "extreme_quantile": extreme_quantile,
        "z_threshold": float(threshold),
        "mode": "continuation" if mean_aligned > 0 else "reversion",
        "mean_aligned_return": mean_aligned,
        "sample_size": n_samples,
    }


def signal_end_indices_and_directions(df, rule):
    close = df["Close"].values
    z = _zscore_from_ma(close, rule["ma_window"])
    threshold = rule["z_threshold"]

    signal_ends = []
    directions = {}
    for i in range(len(df)):
        if np.isnan(z[i]) or abs(z[i]) < threshold:
            continue
        z_dir = 1 if z[i] > 0 else -1
        if rule["mode"] == "continuation":
            direction = "long" if z_dir > 0 else "short"
        else:
            direction = "short" if z_dir > 0 else "long"
        signal_ends.append(i)
        directions[i] = direction

    return signal_ends, directions
