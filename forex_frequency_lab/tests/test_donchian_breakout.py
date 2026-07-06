import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from forex_frequency_lab.backtest import backtest_entries, summarize_trades
from forex_frequency_lab.donchian_breakout import generate_signals


def _make_ohlc(close, freq="4h"):
    n = len(close)
    times = pd.date_range("2015-01-01", periods=n, freq=freq)
    open_ = np.concatenate([[close[0]], close[:-1]])
    return pd.DataFrame(
        {
            "Time": times,
            "Open": open_,
            "High": np.maximum(open_, close) + 0.0002,
            "Low": np.minimum(open_, close) - 0.0002,
            "Close": close,
            "Volume": 100.0,
        }
    )


def _generate_range_then_breakout_series(n_cycles, seed, range_bars=30, breakout_bars=40, channel_period=20):
    rng = np.random.default_rng(seed)
    step = 0.0006
    price = 1.10
    returns = []

    for c in range(n_cycles):
        direction = 1 if c % 2 == 0 else -1
        for _ in range(range_bars):
            returns.append(rng.normal(0, step * 0.3))
        breakout_return = direction * 0.0012
        for _ in range(breakout_bars):
            returns.append(breakout_return + rng.normal(0, step * 0.3))

    returns = np.array(returns)
    close = price + np.cumsum(returns)
    return _make_ohlc(close)


def test_donchian_breakout_recovers_injected_trend_continuation():
    df = _generate_range_then_breakout_series(n_cycles=10, seed=30)
    split = int(len(df) * 0.7)
    df_in, df_out = df.iloc[:split].reset_index(drop=True), df.iloc[split:].reset_index(drop=True)

    ends_in, dirs_in = generate_signals(df_in, channel_period=20)
    ends_out, dirs_out = generate_signals(df_out, channel_period=20)
    assert len(ends_in) > 0
    assert len(ends_out) > 0

    trades = backtest_entries(
        df_out, ends_out, lambda i: dirs_out[i], name="donchian",
        stop_atr_mult=1.5, reward_risk_ratio=2.0, max_hold_bars=30, spread_pips=0.0,
    )
    summary = summarize_trades(trades)
    assert summary["trade_count"] > 0
    assert summary["avg_r"] > 0


def test_donchian_no_signal_before_channel_warms_up():
    df = _generate_range_then_breakout_series(n_cycles=2, seed=31)
    ends, _dirs = generate_signals(df, channel_period=20)
    assert all(e >= 20 for e in ends)
