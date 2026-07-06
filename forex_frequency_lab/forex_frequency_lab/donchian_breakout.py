import numpy as np
import pandas as pd


def generate_signals(df, channel_period=20):
    """Classic breakout entry: go long the moment price closes above its
    own trailing N-bar high (the current bar excluded, so no look-ahead),
    short the moment it closes below its trailing N-bar low. Mechanically
    different from every other idea in this package - it follows momentum
    breaking out of a range rather than a reversal or a gap.
    """
    high = df["High"].values
    low = df["Low"].values
    close = df["Close"].values
    n = len(df)

    rolling_high = pd.Series(high).rolling(channel_period).max().shift(1).values
    rolling_low = pd.Series(low).rolling(channel_period).min().shift(1).values

    signal_ends = []
    directions = {}
    for i in range(n):
        if np.isnan(rolling_high[i]) or np.isnan(rolling_low[i]):
            continue
        if close[i] > rolling_high[i]:
            signal_ends.append(i)
            directions[i] = "long"
        elif close[i] < rolling_low[i]:
            signal_ends.append(i)
            directions[i] = "short"

    return signal_ends, directions
