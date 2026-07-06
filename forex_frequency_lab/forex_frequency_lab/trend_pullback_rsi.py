import numpy as np
import pandas as pd

from .indicators import adx, ema, rsi
from .resample import resample_ohlc


def compute_daily_trend(df_h4, fast_ema=50, slow_ema=200, adx_period=14, adx_threshold=20):
    """Multi-timeframe trend filter: resample the real H4 data up to daily
    bars, and label each day "up" / "down" / "neutral" from an EMA50 vs
    EMA200 crossover, gated by ADX(14) so only bars with real trending
    strength (not a choppy range) count as trending at all.

    Returns a dict of {date -> "up"/"down"/"neutral"}.
    """
    df_d1 = resample_ohlc(df_h4, "1D")
    close = df_d1["Close"].values
    ema_fast = ema(close, fast_ema)
    ema_slow = ema(close, slow_ema)
    adx_vals, _plus_di, _minus_di = adx(df_d1, adx_period)

    trend = np.full(len(df_d1), "neutral", dtype=object)
    trending = ~np.isnan(adx_vals) & (adx_vals >= adx_threshold) & ~np.isnan(ema_slow)
    trend[trending & (ema_fast > ema_slow)] = "up"
    trend[trending & (ema_fast < ema_slow)] = "down"

    dates = df_d1["Time"].dt.date.values
    return dict(zip(dates, trend))


def generate_signals(
    df_h4,
    fast_ema=50,
    slow_ema=200,
    adx_period=14,
    adx_threshold=20,
    rsi_period=14,
    oversold=30,
    overbought=70,
):
    """Entry rule: in an "up" daily trend, go long the moment H4 RSI(14)
    crosses back above `oversold` (the pullback just got exhausted); in a
    "down" trend, go short the moment RSI crosses back below `overbought`.
    No signal in a "neutral" (non-trending / low-ADX) regime.

    Returns (signal_end_indices, directions) in the same convention as
    every other idea in this package: the signal completes at that bar's
    close, so backtest_entries enters at the next bar's open.
    """
    trend_by_date = compute_daily_trend(df_h4, fast_ema, slow_ema, adx_period, adx_threshold)
    bar_dates = df_h4["Time"].dt.date.values
    trend = np.array([trend_by_date.get(d, "neutral") for d in bar_dates], dtype=object)

    close = df_h4["Close"].values
    rsi_vals = rsi(close, rsi_period)
    n = len(df_h4)

    signal_ends = []
    directions = {}
    for i in range(1, n):
        if np.isnan(rsi_vals[i]) or np.isnan(rsi_vals[i - 1]):
            continue
        if trend[i] == "up" and rsi_vals[i - 1] <= oversold < rsi_vals[i]:
            signal_ends.append(i)
            directions[i] = "long"
        elif trend[i] == "down" and rsi_vals[i - 1] >= overbought > rsi_vals[i]:
            signal_ends.append(i)
            directions[i] = "short"

    return signal_ends, directions
