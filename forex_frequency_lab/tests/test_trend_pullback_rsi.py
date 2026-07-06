import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from forex_frequency_lab.backtest import backtest_entries, summarize_trades
from forex_frequency_lab.trend_pullback_rsi import compute_daily_trend, generate_signals


def _make_ohlc(close, start_time="2015-01-01", freq="4h"):
    n = len(close)
    times = pd.date_range(start_time, periods=n, freq=freq)
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


def _generate_trend_pullback_series(n_days, seed, direction=1, base_drift=0.00035, pullback_period_days=25):
    rng = np.random.default_rng(seed)
    bars_per_day = 6
    n = n_days * bars_per_day
    step = 0.0006

    returns = np.full(n, direction * base_drift) + rng.normal(0, step * 0.5, n)

    pullback_period_bars = pullback_period_days * bars_per_day
    for start in range(300, n - 20, pullback_period_bars):
        for j in range(start, start + 4):
            returns[j] = -direction * 0.0022 + rng.normal(0, step * 0.2)
        for j in range(start + 4, start + 7):
            returns[j] = direction * 0.0022 + rng.normal(0, step * 0.2)

    close = 1.10 + np.cumsum(returns)
    return _make_ohlc(close)


def _generate_choppy_series(n_days, seed):
    # Pure iid noise around a fixed level - no drift, no smooth cycle, so
    # there is no real directional persistence for ADX to pick up (a smooth
    # sine wave, by contrast, is genuinely locally trending on each half
    # cycle, which is why that was tried and rejected here).
    rng = np.random.default_rng(seed)
    bars_per_day = 6
    n = n_days * bars_per_day
    close = 1.10 + rng.normal(0, 0.0015, n)
    return _make_ohlc(close)


def test_compute_daily_trend_identifies_up_and_down():
    df_up = _generate_trend_pullback_series(n_days=500, seed=10, direction=1)
    df_down = _generate_trend_pullback_series(n_days=500, seed=11, direction=-1)

    trend_up = compute_daily_trend(df_up)
    trend_down = compute_daily_trend(df_down)

    late_up_labels = list(trend_up.values())[-30:]
    late_down_labels = list(trend_down.values())[-30:]

    assert late_up_labels.count("up") > len(late_up_labels) * 0.7
    assert late_down_labels.count("down") > len(late_down_labels) * 0.7


def test_generate_signals_only_fires_long_in_uptrend_and_profits_out_of_sample():
    df = _generate_trend_pullback_series(n_days=600, seed=20, direction=1)
    split = int(len(df) * 0.7)
    df_in, df_out = df.iloc[:split].reset_index(drop=True), df.iloc[split:].reset_index(drop=True)

    ends_in, dirs_in = generate_signals(df_in)
    assert len(ends_in) > 0
    assert all(d == "long" for d in dirs_in.values())

    ends_out, dirs_out = generate_signals(df_out)
    assert len(ends_out) > 0
    assert all(d == "long" for d in dirs_out.values())

    trades = backtest_entries(
        df_out, ends_out, lambda i: dirs_out[i], name="trend_pullback_rsi",
        stop_atr_mult=1.5, reward_risk_ratio=3.0, max_hold_bars=20, spread_pips=0.0,
    )
    summary = summarize_trades(trades)
    assert summary["trade_count"] > 0
    assert summary["avg_r"] > 0


def test_generate_signals_fires_short_in_downtrend():
    df = _generate_trend_pullback_series(n_days=600, seed=21, direction=-1)
    ends, dirs = generate_signals(df)
    assert len(ends) > 0
    assert all(d == "short" for d in dirs.values())


def test_generate_signals_mostly_quiet_in_choppy_market():
    trending_df = _generate_trend_pullback_series(n_days=600, seed=22, direction=1)
    choppy_df = _generate_choppy_series(n_days=600, seed=23)

    ends_trend, _ = generate_signals(trending_df)
    ends_chop, _ = generate_signals(choppy_df)

    trend_rate = len(ends_trend) / len(trending_df)
    chop_rate = len(ends_chop) / len(choppy_df)
    assert chop_rate < trend_rate
