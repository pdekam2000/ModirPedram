import json

import numpy as np
import pandas as pd

from .candle_features import encode_candles
from .motif_discovery import discover_patterns
from .periodicity import analyze_periodicity
from .trend_metrics import window_trend


def forward_return(close_values, end_index, k):
    if end_index + k >= len(close_values):
        return None
    return float((close_values[end_index + k] - close_values[end_index]) / close_values[end_index])


def build_frequency_catalog(
    df,
    window_sizes=(3, 4, 5),
    min_occurrences=5,
    forward_k=5,
    atr_period=14,
    **candle_kwargs,
):
    """Run the full pipeline: encode candles, find recurring patterns per
    window size, and attach trend/periodicity/forward-outcome stats to each.

    Returns a list of records sorted by occurrence count (most recurring
    first), each labeled "Frequency 1", "Frequency 2", ...
    """
    close_values = df["Close"].values
    timestamps = df["Time"]
    symbols = encode_candles(df, atr_period=atr_period, **candle_kwargs)

    catalog = []
    for window_size in window_sizes:
        patterns = discover_patterns(symbols, window_size, min_occurrences=min_occurrences)
        for code, starts in patterns.items():
            trends = [window_trend(close_values[s : s + window_size]) for s in starts]
            angles = np.array([t["angle_degrees"] for t in trends])
            r2s = np.array([t["r2"] for t in trends])

            ends = [s + window_size - 1 for s in starts]
            fwd_returns = [r for r in (forward_return(close_values, e, forward_k) for e in ends) if r is not None]
            fwd_arr = np.array(fwd_returns)

            periodicity = analyze_periodicity(starts, timestamps)

            catalog.append(
                {
                    "pattern_code": code,
                    "window_size": window_size,
                    "count": len(starts),
                    "start_indices": starts,
                    "occurrence_times": [str(timestamps.iloc[s]) for s in starts],
                    "mean_angle_degrees": float(angles.mean()),
                    "std_angle_degrees": float(angles.std()),
                    "mean_fit_r2": float(r2s.mean()),
                    "forward_k": forward_k,
                    "mean_forward_return": float(fwd_arr.mean()) if fwd_arr.size else None,
                    "forward_win_rate": float((fwd_arr > 0).mean()) if fwd_arr.size else None,
                    "periodicity": periodicity,
                }
            )

    catalog.sort(key=lambda r: r["count"], reverse=True)
    for i, record in enumerate(catalog, start=1):
        record["name"] = f"Frequency {i}"

    return catalog


def save_catalog(catalog, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False, default=str)


def catalog_to_summary_df(catalog):
    rows = []
    for r in catalog:
        rows.append(
            {
                "name": r["name"],
                "window_size": r["window_size"],
                "pattern_code": r["pattern_code"],
                "count": r["count"],
                "mean_angle_degrees": round(r["mean_angle_degrees"], 2),
                "mean_gap_candles": r["periodicity"]["mean_gap_candles"],
                "cv_gap": r["periodicity"]["cv_gap"],
                "mean_forward_return_pct": (
                    None if r["mean_forward_return"] is None else round(r["mean_forward_return"] * 100, 4)
                ),
                "forward_win_rate": r["forward_win_rate"],
            }
        )
    return pd.DataFrame(rows)
