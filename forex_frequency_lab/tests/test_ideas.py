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
from forex_frequency_lab.gap_fill import discover_gap_fill_bias, signal_end_indices_and_directions as gap_fill_signal
from forex_frequency_lab.mean_reversion import (
    discover_mean_reversion_bias,
    signal_end_indices_and_directions as mean_reversion_signal,
)
from forex_frequency_lab.resample import resample_ohlc
from forex_frequency_lab.seasonality import discover_seasonal_bias, signal_end_indices as seasonality_signal
from forex_frequency_lab.walk_forward_validate import rolling_walk_forward_gap_fill
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


def _generate_gap_fill_series(n, seed, forward_k=10, freq_hours=4, gap_period=42):
    rng = np.random.default_rng(seed)
    step = 0.0008

    times = [pd.Timestamp("2015-01-01")]
    for i in range(1, n):
        if i % gap_period == 0:
            times.append(times[-1] + pd.Timedelta(hours=64))  # weekend-style gap
        else:
            times.append(times[-1] + pd.Timedelta(hours=freq_hours))
    times = pd.DatetimeIndex(times)

    opens = np.empty(n)
    closes = np.empty(n)
    price = 1.10
    gap_count = 0
    fill_schedule = {}

    for i in range(n):
        is_gap = i > 0 and (times[i] - times[i - 1]).total_seconds() / 3600 > freq_hours * 1.5
        if is_gap:
            direction = 1 if gap_count % 2 == 0 else -1
            gap_count += 1
            jump = direction * 0.006
            opens[i] = price + jump
            per_bar_fill = -jump / forward_k
            for j in range(i, min(i + forward_k, n)):
                fill_schedule[j] = fill_schedule.get(j, 0.0) + per_bar_fill
        else:
            opens[i] = price

        bar_return = fill_schedule.get(i, 0.0) + rng.normal(0, step * 0.3)
        closes[i] = opens[i] + bar_return
        price = closes[i]

    return pd.DataFrame(
        {
            "Time": times,
            "Open": opens,
            "High": np.maximum(opens, closes) + 0.0001,
            "Low": np.minimum(opens, closes) - 0.0001,
            "Close": closes,
            "Volume": 100.0,
        }
    )


def test_gap_fill_recovers_injected_fill_bias():
    forward_k = 10
    df = _generate_gap_fill_series(2500, seed=5, forward_k=forward_k)

    split = int(len(df) * 0.7)
    df_in, df_out = df.iloc[:split].reset_index(drop=True), df.iloc[split:].reset_index(drop=True)

    rule = discover_gap_fill_bias(df_in, forward_k=forward_k, gap_multiplier=1.5, min_samples=10)
    assert rule is not None
    assert rule["mode"] == "fill"

    signal_ends, directions = gap_fill_signal(df_out, rule)
    trades = backtest_entries(df_out, signal_ends, lambda i: directions[i], "gap_fill", stop_atr_mult=1.0, reward_risk_ratio=1.5, max_hold_bars=forward_k, spread_pips=0.0)
    summary = summarize_trades(trades)
    assert summary["trade_count"] > 0
    assert summary["avg_r"] > 0


def test_mean_reversion_recovers_injected_reversion():
    n = 4000
    rng = np.random.default_rng(6)
    step = 0.0008
    ma_window = 20
    forward_k = 5

    returns = rng.normal(0, step, n)
    # Periodically inject a strong directional extension, then a reliable
    # drift back over the next forward_k bars.
    for i in range(60, n - forward_k, 50):
        direction = 1 if (i // 50) % 2 == 0 else -1
        returns[i] = direction * 0.006
        for j in range(i + 1, i + 1 + forward_k):
            returns[j] = -direction * 0.0014 + rng.normal(0, step * 0.2)

    times = pd.date_range("2015-01-01", periods=n, freq="h")
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

    rule = discover_mean_reversion_bias(df_in, ma_window=ma_window, forward_k=forward_k, extreme_quantile=0.9, min_samples=10)
    assert rule is not None
    assert rule["mode"] == "reversion"

    signal_ends, directions = mean_reversion_signal(df_out, rule)
    trades = backtest_entries(df_out, signal_ends, lambda i: directions[i], "mean_reversion", stop_atr_mult=1.0, reward_risk_ratio=1.5, max_hold_bars=forward_k, spread_pips=0.0)
    summary = summarize_trades(trades)
    assert summary["trade_count"] > 0
    assert summary["avg_r"] > 0


def test_rolling_walk_forward_gap_fill_recovers_edge_across_folds():
    forward_k = 10
    df = _generate_gap_fill_series(6000, seed=7, forward_k=forward_k)

    fold_results = rolling_walk_forward_gap_fill(
        df, n_folds=5, min_in_sample_frac=0.3, forward_k=forward_k,
        gap_multiplier=1.5, min_samples=10, stop_atr_mult=1.0, reward_risk_ratio=1.5, spread_pips=0.0,
    )

    tested_folds = [f for f in fold_results if f.get("rule_found") and f.get("out_trade_count", 0) > 0]
    assert len(tested_folds) >= 3
    assert all(f["mode"] == "fill" for f in tested_folds)
    assert all(f["out_avg_r"] > 0 for f in tested_folds)


def test_resample_ohlc_aggregates_correctly():
    times = pd.date_range("2024-01-01 00:00", periods=8, freq="4h")
    df = pd.DataFrame(
        {
            "Time": times,
            "Open": [1.00, 1.02, 1.05, 1.01, 1.10, 1.11, 1.09, 1.12],
            "High": [1.03, 1.04, 1.06, 1.03, 1.12, 1.13, 1.10, 1.14],
            "Low": [0.99, 1.00, 1.00, 0.98, 1.09, 1.10, 1.07, 1.11],
            "Close": [1.02, 1.05, 1.01, 1.02, 1.11, 1.09, 1.12, 1.13],
            "Volume": [10, 20, 30, 40, 50, 60, 70, 80],
        }
    )

    # 4-hourly bars starting at 00:00 put 6 bars (00,04,08,12,16,20) on day 1
    # and only the remaining 2 (00,04) on day 2.
    daily = resample_ohlc(df, "1D")
    assert len(daily) == 2
    first_day = daily.iloc[0]
    assert first_day["Open"] == 1.00
    assert first_day["High"] == 1.13
    assert first_day["Low"] == 0.98
    assert first_day["Close"] == 1.09
    assert first_day["Volume"] == 210
    second_day = daily.iloc[1]
    assert second_day["Open"] == 1.09
    assert second_day["High"] == 1.14
    assert second_day["Low"] == 1.07
    assert second_day["Close"] == 1.13
    assert second_day["Volume"] == 150
