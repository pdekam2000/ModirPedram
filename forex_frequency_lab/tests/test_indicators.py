import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from forex_frequency_lab.indicators import adx, ema, rsi


def _reference_rsi(values, period=14):
    """Plain-loop Wilder RSI, independent of the vectorized implementation,
    used only to cross-check correctness."""
    n = len(values)
    gains = [0.0] * n
    losses = [0.0] * n
    for i in range(1, n):
        delta = values[i] - values[i - 1]
        gains[i] = max(delta, 0.0)
        losses[i] = max(-delta, 0.0)

    avg_gain = [0.0] * n
    avg_loss = [0.0] * n
    avg_gain[0] = gains[0]
    avg_loss[0] = losses[0]
    for i in range(1, n):
        avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gains[i]) / period
        avg_loss[i] = (avg_loss[i - 1] * (period - 1) + losses[i]) / period

    out = [0.0] * n
    for i in range(n):
        if avg_loss[i] == 0:
            out[i] = 50.0 if avg_gain[i] == 0 else 100.0
        else:
            rs = avg_gain[i] / avg_loss[i]
            out[i] = 100 - 100 / (1 + rs)
    return np.array(out)


def test_rsi_matches_independent_reference():
    rng = np.random.default_rng(1)
    values = 1.10 + np.cumsum(rng.normal(0, 0.001, 300))

    mine = rsi(values, period=14)
    ref = _reference_rsi(values, period=14)

    # skip the first few bars where EWM warm-up vs simple-average warm-up differ most
    assert np.allclose(mine[30:], ref[30:], atol=1.5)


def test_rsi_bounds_and_known_direction():
    # A strictly rising series should show RSI pinned near 100; a strictly
    # falling one near 0.
    up = np.linspace(1.00, 1.50, 60)
    down = np.linspace(1.50, 1.00, 60)

    rsi_up = rsi(up, period=14)
    rsi_down = rsi(down, period=14)

    assert rsi_up[-1] > 95
    assert rsi_down[-1] < 5
    assert np.all(rsi_up[np.isfinite(rsi_up)] >= 0) and np.all(rsi_up[np.isfinite(rsi_up)] <= 100)


def test_ema_matches_pandas_ewm():
    rng = np.random.default_rng(2)
    values = 1.10 + np.cumsum(rng.normal(0, 0.001, 200))
    mine = ema(values, period=20)
    ref = pd.Series(values).ewm(span=20, adjust=False).mean().values
    assert np.allclose(mine, ref)


def test_adx_high_for_strong_trend_low_for_choppy():
    n = 200
    rng = np.random.default_rng(3)

    # Strong uptrend: steady climb with small noise.
    trend_close = 1.10 + np.cumsum(np.full(n, 0.0015) + rng.normal(0, 0.0002, n))
    trend_high = trend_close + 0.0005
    trend_low = trend_close - 0.0005
    df_trend = pd.DataFrame({"High": trend_high, "Low": trend_low, "Close": trend_close})

    # Choppy/range-bound: oscillates with no directional drift.
    chop_close = 1.10 + 0.01 * np.sin(np.linspace(0, 40 * np.pi, n)) + rng.normal(0, 0.0003, n)
    chop_high = chop_close + 0.0005
    chop_low = chop_close - 0.0005
    df_chop = pd.DataFrame({"High": chop_high, "Low": chop_low, "Close": chop_close})

    adx_trend, _, _ = adx(df_trend, period=14)
    adx_chop, _, _ = adx(df_chop, period=14)

    assert np.nanmean(adx_trend[-50:]) > 25
    assert np.nanmean(adx_chop[-50:]) < np.nanmean(adx_trend[-50:])


def test_adx_directional_indicators_match_trend_direction():
    n = 150
    up_close = 1.10 + np.cumsum(np.full(n, 0.0012))
    df_up = pd.DataFrame({"High": up_close + 0.0004, "Low": up_close - 0.0004, "Close": up_close})
    _adx, plus_di, minus_di = adx(df_up, period=14)
    assert plus_di[-1] > minus_di[-1]

    down_close = 1.10 - np.cumsum(np.full(n, 0.0012))
    df_down = pd.DataFrame({"High": down_close + 0.0004, "Low": down_close - 0.0004, "Close": down_close})
    _adx2, plus_di2, minus_di2 = adx(df_down, period=14)
    assert minus_di2[-1] > plus_di2[-1]
