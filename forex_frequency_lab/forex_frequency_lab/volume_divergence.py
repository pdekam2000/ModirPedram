import numpy as np
import pandas as pd


def _rolling_zscore(values, window):
    s = pd.Series(values)
    mean = s.rolling(window, min_periods=window).mean()
    std = s.rolling(window, min_periods=window).std()
    return ((s - mean) / std).values


def discover_volume_divergence_bias(df, window=20, forward_k=5, extreme_quantile=0.8, min_samples=20):
    """On in-sample data: when a bar's move is unusually large relative to
    its recent history but tick volume behind it is unusually low (weak
    participation for the size of the move), does price tend to keep going
    (continuation) or fade back (reversal)? Thresholds are derived here and
    reused as-is out-of-sample.
    """
    close = df["Close"].values
    volume = df["Volume"].values
    n = len(df)

    bar_return = np.concatenate([[np.nan], (close[1:] - close[:-1]) / close[:-1]])
    abs_return_z = _rolling_zscore(np.abs(bar_return), window)
    volume_z = _rolling_zscore(volume, window)

    fwd = np.full(n, np.nan)
    if n > forward_k:
        fwd[: n - forward_k] = (close[forward_k:] - close[:-forward_k]) / close[:-forward_k]

    move_threshold = np.nanquantile(abs_return_z, extreme_quantile)
    volume_low_threshold = np.nanquantile(volume_z, 1 - extreme_quantile)

    valid = (
        ~np.isnan(abs_return_z)
        & ~np.isnan(volume_z)
        & ~np.isnan(bar_return)
        & ~np.isnan(fwd)
        & (abs_return_z >= move_threshold)
        & (volume_z <= volume_low_threshold)
        & (bar_return != 0)
    )
    n_samples = int(valid.sum())
    if n_samples < min_samples:
        return None

    bar_dir = np.sign(bar_return[valid])
    aligned = fwd[valid] * bar_dir

    mean_aligned = float(aligned.mean())
    if abs(mean_aligned) < 1e-6:
        return None

    return {
        "window": window,
        "forward_k": forward_k,
        "extreme_quantile": extreme_quantile,
        "move_z_threshold": float(move_threshold),
        "volume_z_threshold_low": float(volume_low_threshold),
        "mode": "continuation" if mean_aligned > 0 else "fade",
        "mean_aligned_return": mean_aligned,
        "sample_size": n_samples,
    }


def signal_end_indices_and_directions(df, rule):
    close = df["Close"].values
    volume = df["Volume"].values
    bar_return = np.concatenate([[np.nan], (close[1:] - close[:-1]) / close[:-1]])
    abs_return_z = _rolling_zscore(np.abs(bar_return), rule["window"])
    volume_z = _rolling_zscore(volume, rule["window"])

    move_threshold = rule["move_z_threshold"]
    volume_low_threshold = rule["volume_z_threshold_low"]

    signal_ends = []
    directions = {}
    for i in range(len(df)):
        if np.isnan(abs_return_z[i]) or np.isnan(volume_z[i]) or np.isnan(bar_return[i]) or bar_return[i] == 0:
            continue
        if abs_return_z[i] < move_threshold or volume_z[i] > volume_low_threshold:
            continue
        bar_dir = 1 if bar_return[i] > 0 else -1
        if rule["mode"] == "continuation":
            direction = "long" if bar_dir > 0 else "short"
        else:
            direction = "short" if bar_dir > 0 else "long"
        signal_ends.append(i)
        directions[i] = direction

    return signal_ends, directions
