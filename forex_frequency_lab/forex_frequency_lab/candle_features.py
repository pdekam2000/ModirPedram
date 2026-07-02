import numpy as np
import pandas as pd

DEFAULT_ATR_PERIOD = 14
DEFAULT_BODY_THRESHOLDS = (0.33, 0.66)
DEFAULT_SIZE_THRESHOLDS = (0.7, 1.3)
DEFAULT_DOJI_EPSILON = 0.05


def true_range(df):
    prev_close = df["Close"].shift(1)
    high_low = df["High"] - df["Low"]
    high_prev_close = (df["High"] - prev_close).abs()
    low_prev_close = (df["Low"] - prev_close).abs()
    return pd.concat([high_low, high_prev_close, low_prev_close], axis=1).max(axis=1)


def atr(df, period=DEFAULT_ATR_PERIOD):
    return true_range(df).rolling(window=period, min_periods=period).mean()


def encode_candles(
    df,
    atr_period=DEFAULT_ATR_PERIOD,
    body_thresholds=DEFAULT_BODY_THRESHOLDS,
    size_thresholds=DEFAULT_SIZE_THRESHOLDS,
    doji_epsilon=DEFAULT_DOJI_EPSILON,
):
    """Encode each candle into a discrete symbol: direction + size-bucket + body-strength.

    e.g. "UM2" = bullish, medium range (vs ATR), medium body strength.
    Candles before `atr_period` bars (no ATR yet) are encoded as None.
    """
    atr_values = atr(df, atr_period).values
    open_ = df["Open"].values
    high = df["High"].values
    low = df["Low"].values
    close = df["Close"].values
    n = len(df)

    weak_t, strong_t = body_thresholds
    small_t, large_t = size_thresholds

    symbols = [None] * n
    for i in range(n):
        a = atr_values[i]
        if a is None or np.isnan(a) or a == 0:
            continue

        rng = high[i] - low[i]
        if rng == 0:
            symbols[i] = "N-S0"
            continue

        body_ratio = (close[i] - open_[i]) / rng
        abs_ratio = abs(body_ratio)

        if abs_ratio < doji_epsilon:
            direction = "N"
        elif body_ratio > 0:
            direction = "U"
        else:
            direction = "D"

        if abs_ratio < weak_t:
            strength = "1"
        elif abs_ratio < strong_t:
            strength = "2"
        else:
            strength = "3"

        size_ratio = rng / a
        if size_ratio < small_t:
            size_bucket = "S"
        elif size_ratio < large_t:
            size_bucket = "M"
        else:
            size_bucket = "L"

        symbols[i] = f"{direction}{size_bucket}{strength}"

    return symbols
