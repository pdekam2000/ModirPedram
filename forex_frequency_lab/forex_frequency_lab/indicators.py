import numpy as np
import pandas as pd


def ema(values, period):
    return pd.Series(values).ewm(span=period, adjust=False).mean().values


def rsi(values, period=14):
    """Wilder's RSI. Causal (each value only uses bars up to and including
    its own index), so it is safe to use directly in a backtest.
    """
    values = np.asarray(values, dtype=float)
    delta = np.diff(values, prepend=values[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)

    avg_gain = pd.Series(gain).ewm(alpha=1 / period, adjust=False).mean().values
    avg_loss = pd.Series(loss).ewm(alpha=1 / period, adjust=False).mean().values

    rs = np.divide(avg_gain, avg_loss, out=np.full_like(avg_gain, np.inf), where=avg_loss != 0)
    rsi_vals = 100 - (100 / (1 + rs))
    rsi_vals[(avg_gain == 0) & (avg_loss == 0)] = 50.0
    return rsi_vals


def _wilder_smooth(x, period):
    n = len(x)
    result = np.full(n, np.nan)
    if n < period:
        return result
    result[period - 1] = x[:period].sum()
    for i in range(period, n):
        result[i] = result[i - 1] - result[i - 1] / period + x[i]
    return result


def adx(df, period=14):
    """Wilder's ADX/+DI/-DI. Causal, no look-ahead."""
    high = df["High"].values
    low = df["Low"].values
    close = df["Close"].values
    n = len(df)

    up_move = np.diff(high, prepend=high[0])
    down_move = -np.diff(low, prepend=low[0])
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    plus_dm[0] = 0.0
    minus_dm[0] = 0.0

    prev_close = np.concatenate([[close[0]], close[:-1]])
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))

    tr_smooth = _wilder_smooth(tr, period)
    plus_dm_smooth = _wilder_smooth(plus_dm, period)
    minus_dm_smooth = _wilder_smooth(minus_dm, period)

    with np.errstate(divide="ignore", invalid="ignore"):
        plus_di = 100 * np.divide(plus_dm_smooth, tr_smooth, out=np.full(n, np.nan), where=tr_smooth > 0)
        minus_di = 100 * np.divide(minus_dm_smooth, tr_smooth, out=np.full(n, np.nan), where=tr_smooth > 0)
        di_sum = plus_di + minus_di
        dx = 100 * np.divide(np.abs(plus_di - minus_di), di_sum, out=np.full(n, np.nan), where=di_sum > 0)

    start = 2 * period - 1
    adx_vals = np.full(n, np.nan)
    if start < n:
        first_valid_dx = dx[period:start + 1]
        adx_vals[start] = np.nanmean(first_valid_dx)
        for i in range(start + 1, n):
            if np.isnan(dx[i]):
                adx_vals[i] = adx_vals[i - 1]
            else:
                adx_vals[i] = (adx_vals[i - 1] * (period - 1) + dx[i]) / period

    return adx_vals, plus_di, minus_di
