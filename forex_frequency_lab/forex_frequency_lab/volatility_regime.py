import numpy as np

from .candle_features import atr as compute_atr


def discover_volatility_regime_bias(df, atr_period=14, forward_k=5, regime_quantile=0.8, min_samples=20):
    """On in-sample data: after an unusually large-range bar (top
    `regime_quantile` of ATR), does price tend to keep moving the same way
    (continuation) or snap back (reversion)? Returns whichever mode showed
    an edge, with the ATR threshold that defines "unusually large" — that
    threshold is reused as-is on out-of-sample data, never recomputed there.
    """
    close = df["Close"].values
    atr_values = compute_atr(df, atr_period).values
    n = len(df)

    threshold = np.nanquantile(atr_values, regime_quantile)
    bar_return = np.concatenate([[np.nan], (close[1:] - close[:-1])])
    fwd = np.full(n, np.nan)
    if n > forward_k:
        fwd[: n - forward_k] = (close[forward_k:] - close[:-forward_k]) / close[:-forward_k]

    valid = ~np.isnan(atr_values) & ~np.isnan(bar_return) & ~np.isnan(fwd) & (atr_values >= threshold) & (bar_return != 0)
    n_samples = int(valid.sum())
    if n_samples < min_samples:
        return None

    bar_dir = np.sign(bar_return[valid])
    aligned = fwd[valid] * bar_dir  # >0 if forward return matches the big bar's direction

    mean_aligned = float(aligned.mean())
    if abs(mean_aligned) < 1e-6:
        return None

    return {
        "atr_period": atr_period,
        "regime_quantile": regime_quantile,
        "forward_k": forward_k,
        "atr_threshold": float(threshold),
        "mode": "continuation" if mean_aligned > 0 else "reversion",
        "mean_aligned_return": mean_aligned,
        "sample_size": n_samples,
    }


def signal_end_indices_and_directions(df, rule):
    close = df["Close"].values
    atr_values = compute_atr(df, rule["atr_period"]).values
    bar_return = np.concatenate([[np.nan], (close[1:] - close[:-1])])
    threshold = rule["atr_threshold"]

    signal_ends = []
    directions = {}
    for i in range(len(df)):
        if np.isnan(atr_values[i]) or np.isnan(bar_return[i]) or atr_values[i] < threshold or bar_return[i] == 0:
            continue
        bar_dir = 1 if bar_return[i] > 0 else -1
        if rule["mode"] == "continuation":
            direction = "long" if bar_dir > 0 else "short"
        else:
            direction = "short" if bar_dir > 0 else "long"
        signal_ends.append(i)
        directions[i] = direction

    return signal_ends, directions
