import numpy as np


def _detect_gap_indices(df, gap_multiplier=1.5):
    """Bar indices where the time since the previous bar is unusually large
    relative to the series' typical spacing — i.e. a weekend (or holiday)
    gap, regardless of which exact days the broker's calendar uses.
    """
    diffs = df["Time"].diff().dt.total_seconds().values / 60.0
    valid_diffs = diffs[~np.isnan(diffs)]
    if len(valid_diffs) == 0:
        return np.array([], dtype=int)
    typical = np.median(valid_diffs)
    threshold = typical * gap_multiplier
    return np.where(diffs > threshold)[0]


def discover_gap_fill_bias(df, forward_k=10, gap_multiplier=1.5, min_samples=15):
    """On in-sample data: after a weekend/holiday gap, does price tend to
    keep moving in the gap's direction (continuation) or retrace back
    toward the pre-gap level (fill)?
    """
    close = df["Close"].values
    open_ = df["Open"].values
    n = len(df)

    gap_indices = _detect_gap_indices(df, gap_multiplier)
    gap_indices = gap_indices[(gap_indices > 0) & (gap_indices < n - forward_k)]
    if len(gap_indices) == 0:
        return None

    gap_size = open_[gap_indices] - close[gap_indices - 1]
    keep = gap_size != 0
    gap_indices = gap_indices[keep]
    gap_size = gap_size[keep]
    if len(gap_indices) < min_samples:
        return None

    gap_dir = np.sign(gap_size)
    fwd = (close[gap_indices + forward_k - 1] - open_[gap_indices]) / open_[gap_indices]
    aligned = fwd * gap_dir  # >0 = continuation (further in gap direction), <0 = fill (reverts)

    mean_aligned = float(aligned.mean())
    if abs(mean_aligned) < 1e-6:
        return None

    return {
        "gap_multiplier": gap_multiplier,
        "forward_k": forward_k,
        "mode": "continuation" if mean_aligned > 0 else "fill",
        "mean_aligned_return": mean_aligned,
        "sample_size": int(len(gap_indices)),
    }


def signal_end_indices_and_directions(df, rule):
    """Signal "completes" on the last pre-gap bar, so backtest_entries
    enters right at the gap-open bar's open — the earliest point the gap
    size is actually known.
    """
    close = df["Close"].values
    open_ = df["Open"].values
    n = len(df)
    gap_indices = _detect_gap_indices(df, rule["gap_multiplier"])
    gap_indices = gap_indices[(gap_indices > 0) & (gap_indices < n)]

    signal_ends = []
    directions = {}
    for idx in gap_indices:
        gap_size = open_[idx] - close[idx - 1]
        if gap_size == 0:
            continue
        gap_dir = 1 if gap_size > 0 else -1
        if rule["mode"] == "continuation":
            direction = "long" if gap_dir > 0 else "short"
        else:
            direction = "short" if gap_dir > 0 else "long"
        signal_end = idx - 1
        signal_ends.append(signal_end)
        directions[signal_end] = direction

    return signal_ends, directions
