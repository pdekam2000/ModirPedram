import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from forex_frequency_lab.backtest import backtest_entries, summarize_trades
from forex_frequency_lab.cross_pair import (
    align_pairs,
    compute_residuals,
    discover_lead_lag_strategy,
    signal_end_indices_and_directions as cross_pair_signal,
)
from forex_frequency_lab.seasonality import discover_seasonal_bias, signal_end_indices as seasonality_signal
from forex_frequency_lab.volatility_regime import (
    discover_volatility_regime_bias,
    signal_end_indices_and_directions as vol_regime_signal,
)
from forex_frequency_lab.volume_divergence import (
    discover_volume_divergence_bias,
    signal_end_indices_and_directions as vol_divergence_signal,
)


def _random_walk_df(n_bars, seed, freq="h", step=0.0008, start_price=1.10, start="2015-01-01"):
    rng = np.random.default_rng(seed)
    returns = rng.normal(0, step, n_bars)
    closes = start_price + np.cumsum(returns)
    opens = np.concatenate([[start_price], closes[:-1]])
    highs = np.maximum(opens, closes) + rng.uniform(0, step * 0.3, n_bars)
    lows = np.minimum(opens, closes) - rng.uniform(0, step * 0.3, n_bars)
    times = pd.date_range(start, periods=n_bars, freq=freq)
    volume = rng.uniform(50, 500, n_bars)
    return pd.DataFrame({"Time": times, "Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": volume})


def test_seasonality_recovers_injected_hour_bias():
    n = 6000
    rng = np.random.default_rng(1)
    step = 0.0008
    times = pd.date_range("2015-01-01", periods=n, freq="h")
    hours = times.hour.values
    returns = rng.normal(0, step, n)
    # The single bar right after each hour==9 bar gets a fixed extra positive
    # return; nothing else is touched, so there is no compounding artifact.
    for i in range(n - 1):
        if hours[i] == 9:
            returns[i + 1] += 0.0025

    close = 1.10 + np.cumsum(returns)
    open_ = np.concatenate([[1.10], close[:-1]])
    df = pd.DataFrame(
        {
            "Time": times,
            "Open": open_,
            "High": np.maximum(open_, close) + 0.0002,
            "Low": np.minimum(open_, close) - 0.0002,
            "Close": close,
            "Volume": 100.0,
        }
    )

    split = int(len(df) * 0.7)
    df_in, df_out = df.iloc[:split].reset_index(drop=True), df.iloc[split:].reset_index(drop=True)

    # forward_k=1 so the window can't blur into neighboring hours - the
    # injected bump sits on exactly one bar, so only the hour right before
    # it should show an edge.
    rule = discover_seasonal_bias(df_in, forward_k=1, group_by="hour", min_samples=20, min_edge=0.0003)
    assert rule is not None
    assert rule["key"] == 9
    assert rule["direction"] == "long"

    signal_ends = seasonality_signal(df_out, rule)
    trades = backtest_entries(df_out, signal_ends, rule["direction"], "seasonal", stop_atr_mult=1.0, reward_risk_ratio=1.5, max_hold_bars=3, spread_pips=0.0)
    summary = summarize_trades(trades)
    assert summary["trade_count"] > 0
    assert summary["avg_r"] > 0


def test_volatility_regime_recovers_continuation():
    n = 4000
    rng = np.random.default_rng(2)
    step = 0.0008
    times = pd.date_range("2015-01-01", periods=n, freq="h")
    returns = rng.normal(0, step, n)
    # Every 30 bars: one big-range trend bar, then 5 bars continuing the same direction.
    for i in range(0, n - 6, 30):
        direction = 1 if (i // 30) % 2 == 0 else -1
        returns[i] = direction * 0.006
        for j in range(i + 1, i + 6):
            returns[j] = direction * 0.0015 + rng.normal(0, step * 0.2)

    close = 1.10 + np.cumsum(returns)
    open_ = np.concatenate([[1.10], close[:-1]])
    df = pd.DataFrame(
        {
            "Time": times,
            "Open": open_,
            "High": np.maximum(open_, close) + 0.0001,
            "Low": np.minimum(open_, close) - 0.0001,
            "Close": close,
            "Volume": 100.0,
        }
    )

    split = int(len(df) * 0.7)
    df_in, df_out = df.iloc[:split].reset_index(drop=True), df.iloc[split:].reset_index(drop=True)

    rule = discover_volatility_regime_bias(df_in, atr_period=14, forward_k=5, regime_quantile=0.8, min_samples=10)
    assert rule is not None
    assert rule["mode"] == "continuation"

    signal_ends, directions = vol_regime_signal(df_out, rule)
    trades = backtest_entries(df_out, signal_ends, lambda i: directions[i], "vol_regime", stop_atr_mult=1.0, reward_risk_ratio=1.5, max_hold_bars=5, spread_pips=0.0)
    summary = summarize_trades(trades)
    assert summary["trade_count"] > 0
    assert summary["avg_r"] > 0


def test_volume_divergence_recovers_fade():
    n = 4000
    rng = np.random.default_rng(3)
    step = 0.0008
    times = pd.date_range("2015-01-01", periods=n, freq="h")
    returns = rng.normal(0, step, n)
    volume = rng.uniform(50, 500, n)
    # Every 25 bars: a big move on unusually low volume, reliably followed by a reversal.
    for i in range(20, n - 6, 25):
        direction = 1 if (i // 25) % 2 == 0 else -1
        returns[i] = direction * 0.006
        volume[i] = 5.0
        for j in range(i + 1, i + 6):
            returns[j] = -direction * 0.0012 + rng.normal(0, step * 0.2)

    close = 1.10 + np.cumsum(returns)
    open_ = np.concatenate([[1.10], close[:-1]])
    df = pd.DataFrame(
        {
            "Time": times,
            "Open": open_,
            "High": np.maximum(open_, close) + 0.0002,
            "Low": np.minimum(open_, close) - 0.0002,
            "Close": close,
            "Volume": volume,
        }
    )

    split = int(len(df) * 0.7)
    df_in, df_out = df.iloc[:split].reset_index(drop=True), df.iloc[split:].reset_index(drop=True)

    rule = discover_volume_divergence_bias(df_in, window=20, forward_k=5, extreme_quantile=0.8, min_samples=5)
    assert rule is not None
    assert rule["mode"] == "fade"

    signal_ends, directions = vol_divergence_signal(df_out, rule)
    trades = backtest_entries(df_out, signal_ends, lambda i: directions[i], "vol_divergence", stop_atr_mult=1.0, reward_risk_ratio=1.5, max_hold_bars=5, spread_pips=0.0)
    summary = summarize_trades(trades)
    assert summary["trade_count"] > 0
    assert summary["avg_r"] > 0


def test_cross_pair_lead_lag_recovers_known_relationship():
    # Tests discover_lead_lag_strategy + signal generation + backtest directly
    # on a hand-built "residuals" frame with a known causal relationship
    # (LEADER's move at t drives FOLLOWER's move at t+1). The common-factor
    # stripping in compute_residuals is a separate, real-data-only concern
    # (with only 2 series the equal-weight "common factor" degenerates into
    # half of each series' own noise) and is smoke-tested on its own below.
    n = 3000
    rng = np.random.default_rng(4)
    times = pd.date_range("2015-01-01", periods=n, freq="h")

    leader_vals = rng.normal(0, 0.0006, n)
    follower_vals = rng.normal(0, 0.0002, n)
    for t in range(n - 1):
        follower_vals[t + 1] += 0.6 * leader_vals[t]

    residuals = pd.DataFrame({"LEADER": leader_vals, "FOLLOWER": follower_vals}, index=times)
    split_time = times[int(n * 0.7)]

    relationship = discover_lead_lag_strategy(residuals, split_time, max_lag=3, min_abs_corr=0.05)
    assert relationship is not None
    assert relationship["leader"] == "LEADER"
    assert relationship["follower"] == "FOLLOWER"
    assert relationship["lag"] == 1
    assert relationship["correlation"] > 0

    out_of_sample_residuals = residuals.loc[residuals.index > split_time].reset_index(drop=True)
    signal_ends, directions = cross_pair_signal(out_of_sample_residuals, relationship)

    follower_close = 1.30 + np.cumsum(follower_vals)
    follower_open = np.concatenate([[1.30], follower_close[:-1]])
    follower_df = pd.DataFrame(
        {
            "Time": times,
            "Open": follower_open,
            "High": np.maximum(follower_open, follower_close) + 0.0001,
            "Low": np.minimum(follower_open, follower_close) - 0.0001,
            "Close": follower_close,
            "Volume": 100.0,
        }
    )
    follower_out = follower_df.loc[follower_df["Time"] > split_time].reset_index(drop=True)

    trades = backtest_entries(follower_out, signal_ends, lambda i: directions[i], "cross_pair", stop_atr_mult=1.0, reward_risk_ratio=1.5, max_hold_bars=3, spread_pips=0.0)
    summary = summarize_trades(trades)
    assert summary["trade_count"] > 0
    assert summary["avg_r"] > 0


def test_align_pairs_and_compute_residuals_smoke():
    # With enough series the common factor averages out each one's own idio
    # noise instead of being dominated by it; this just checks the plumbing
    # (alignment, shapes, no crash) rather than a specific discovered effect.
    n = 500
    times = pd.date_range("2015-01-01", periods=n, freq="h")
    rng = np.random.default_rng(9)
    dfs = {}
    for name in ["AAA", "BBB", "CCC", "DDD"]:
        close = 1.10 + np.cumsum(rng.normal(0, 0.0007, n))
        open_ = np.concatenate([[1.10], close[:-1]])
        dfs[name] = pd.DataFrame(
            {
                "Time": times,
                "Open": open_,
                "High": np.maximum(open_, close) + 0.0001,
                "Low": np.minimum(open_, close) - 0.0001,
                "Close": close,
                "Volume": 100.0,
            }
        )

    aligned_closes, aligned_ohlc = align_pairs(dfs)
    assert list(aligned_closes.columns) == ["AAA", "BBB", "CCC", "DDD"]
    assert len(aligned_closes) == n

    split_time = aligned_closes.index[int(n * 0.7)]
    residuals, betas = compute_residuals(aligned_closes, split_time)
    assert set(betas.keys()) == {"AAA", "BBB", "CCC", "DDD"}
    assert len(residuals) == n - 1
