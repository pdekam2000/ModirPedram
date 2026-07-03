import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from forex_frequency_lab.backtest import backtest_strategy, summarize_trades
from forex_frequency_lab.candle_features import encode_candles
from forex_frequency_lab.data_loader import load_ohlc_csv
from forex_frequency_lab.frequency_catalog import (
    build_frequency_catalog,
    build_shadow_frequency_catalog,
    catalog_from_symbols,
)
from forex_frequency_lab.reverse_lookup import reverse_engineer_precursors
from forex_frequency_lab.shadow_features import encode_shadows
from forex_frequency_lab.strategy import derive_strategies_from_catalog
from forex_frequency_lab.synthetic_data import generate_synthetic_ohlc
from forex_frequency_lab.walk_forward import split_in_out_sample


def test_pipeline_recovers_injected_patterns():
    df, injection_log = generate_synthetic_ohlc(n_bars=6000, injection_period=250, injection_jitter=10, seed=7)
    catalog = build_frequency_catalog(df, window_sizes=[5], min_occurrences=3, forward_k=5)

    assert len(catalog) > 0

    # The two deliberately injected shapes should surface as the two
    # most-frequent patterns, and their occurrences should line up with the
    # true injection points recorded by the generator.
    injected_starts = set(injection_log)
    top_two = catalog[:2]
    for record in top_two:
        assert record["count"] >= 5
        overlap = len(set(record["start_indices"]) & injected_starts)
        assert overlap / record["count"] >= 0.9

        periodicity = record["periodicity"]
        assert periodicity["mean_gap_candles"] is not None
        assert periodicity["mean_gap_candles"] > 0


def test_data_loader_flexible_columns(tmp_path):
    csv_path = tmp_path / "sample.csv"
    pd.DataFrame(
        {
            "<DATE>": ["2024.01.01", "2024.01.01"],
            "<TIME>": ["00:00:00", "01:00:00"],
            "<OPEN>": [1.10, 1.11],
            "<HIGH>": [1.12, 1.13],
            "<LOW>": [1.09, 1.10],
            "<CLOSE>": [1.11, 1.12],
            "<TICKVOL>": [100, 120],
        }
    ).to_csv(csv_path, index=False)

    df = load_ohlc_csv(csv_path)
    assert list(df.columns) == ["Time", "Open", "High", "Low", "Close", "Volume"]
    assert len(df) == 2


def test_data_loader_missing_columns_raises(tmp_path):
    csv_path = tmp_path / "bad.csv"
    pd.DataFrame({"Time": ["2024-01-01"], "Open": [1.1]}).to_csv(csv_path, index=False)

    try:
        load_ohlc_csv(csv_path)
        assert False, "expected ValueError for missing columns"
    except ValueError:
        pass


def test_encode_shadows_classifies_known_shapes():
    df = pd.DataFrame(
        {
            "Open": [1.00, 1.00, 1.00],
            "High": [1.00, 1.00, 1.10],
            "Low": [1.00, 0.90, 1.00],
            "Close": [1.00, 0.99, 1.02],
        }
    )
    symbols, shapes = encode_shadows(df)
    assert symbols[0] == "U0L0" and shapes[0] == "marubozu"
    assert symbols[1] == "U0L2" and shapes[1] == "hammer"
    assert symbols[2] == "U2L0" and shapes[2] == "shooting_star"


def _make_ohlc_bar(open_price, close_price, upper_wick, lower_wick):
    high = max(open_price, close_price) + upper_wick
    low = min(open_price, close_price) - lower_wick
    return open_price, high, low, close_price


def _generate_hammer_precursor_series(n_bars=3000, seed=3, injection_period=60, rally_size=0.02):
    """Random-walk series where a hammer-shaped candle (long lower wick, no
    upper wick, small body) is planted every `injection_period` bars,
    immediately followed by a sharp rally. Used to check that the reverse
    lookup can recover a known cause -> effect relationship.
    """
    rng = np.random.default_rng(seed)
    step = 0.0008
    opens, highs, lows, closes = [], [], [], []
    price = 1.10
    hammer_starts = []

    for i in range(n_bars):
        if i > 0 and i % injection_period == 0:
            o, h, l, c = _make_ohlc_bar(price, price + step * 0.2, upper_wick=0.0002, lower_wick=step * 3)
            opens.append(o); highs.append(h); lows.append(l); closes.append(c)
            price = c
            hammer_starts.append(i)
            # sharp rally in the bars right after the hammer
            for _ in range(3):
                o, h, l, c = _make_ohlc_bar(price, price + rally_size / 3, upper_wick=step * 0.3, lower_wick=step * 0.1)
                opens.append(o); highs.append(h); lows.append(l); closes.append(c)
                price = c
            continue

        direction = rng.choice([-1, 1])
        body = rng.uniform(0.05, 0.9) * step
        o = price
        c = o + direction * body
        h = max(o, c) + rng.uniform(0.0, 0.3) * step
        l = min(o, c) - rng.uniform(0.0, 0.3) * step
        opens.append(o); highs.append(h); lows.append(l); closes.append(c)
        price = c

    times = pd.date_range("2015-01-01", periods=len(opens), freq="h")
    df = pd.DataFrame({"Time": times, "Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": 0.0})
    return df, hammer_starts


def test_reverse_engineer_precursors_recovers_known_cause():
    df, hammer_starts = _generate_hammer_precursor_series()
    symbols, _shapes = encode_shadows(df)

    result = reverse_engineer_precursors(
        df, symbols, window_size=1, forward_k=3, outcome_quantile=0.05, min_occurrences=3
    )
    assert result is not None

    up_precursors = result["precursors_before_big_up_moves"]
    assert len(up_precursors) > 0

    top = up_precursors[0]
    assert top["pattern_code"] == "U0L2"
    assert top["lift"] > 3


def test_shadow_frequency_catalog_runs():
    df, _ = generate_synthetic_ohlc(n_bars=4000, seed=11)
    catalog = build_shadow_frequency_catalog(df, window_sizes=[3], min_occurrences=5)
    assert isinstance(catalog, list)


def _generate_body_edge_series(n_bars=6000, seed=5, injection_period=40, rally_bars=3):
    """Random-walk series where a specific 3-candle bullish shape recurs
    regularly and is reliably followed by a further rally. Used to check
    that discovering a strategy on one slice of history and backtesting it
    on a later, untouched slice actually recovers the true edge.
    """
    rng = np.random.default_rng(seed)
    step = 0.0008
    pattern = [(1, 0.6, 0.2), (1, 0.6, 0.2), (1, 0.6, 0.2)]
    opens, highs, lows, closes = [], [], [], []
    price = 1.10
    i = 0

    while i < n_bars:
        if i > 0 and i % injection_period == 0 and i + len(pattern) + rally_bars <= n_bars:
            for direction, body_frac, wick_frac in pattern:
                o, h, l, c = _make_ohlc_bar(price, price + direction * body_frac * step, upper_wick=wick_frac * step, lower_wick=wick_frac * step)
                opens.append(o); highs.append(h); lows.append(l); closes.append(c)
                price = c
            for _ in range(rally_bars):
                o, h, l, c = _make_ohlc_bar(price, price + 0.8 * step, upper_wick=0.15 * step, lower_wick=0.15 * step)
                opens.append(o); highs.append(h); lows.append(l); closes.append(c)
                price = c
            i += len(pattern) + rally_bars
            continue

        direction = rng.choice([-1, 1])
        body = rng.uniform(0.05, 0.9) * step
        o = price
        c = o + direction * body
        h = max(o, c) + rng.uniform(0.0, 0.3) * step
        l = min(o, c) - rng.uniform(0.0, 0.3) * step
        opens.append(o); highs.append(h); lows.append(l); closes.append(c)
        price = c
        i += 1

    times = pd.date_range("2015-01-01", periods=len(opens), freq="h")
    return pd.DataFrame({"Time": times, "Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": 0.0})


def test_backtest_recovers_true_edge_out_of_sample():
    df = _generate_body_edge_series(n_bars=6000, seed=5, injection_period=40)
    body_symbols = encode_candles(df, atr_period=14)

    _split_idx, (df_in, symbols_in), (df_out, symbols_out) = split_in_out_sample(
        df, {"body": body_symbols}, in_sample_frac=0.7
    )

    catalog_in = catalog_from_symbols(df_in, symbols_in["body"], window_sizes=[3], min_occurrences=10, forward_k=3)
    strategies = derive_strategies_from_catalog(catalog_in, scheme="body", top_n=3, min_count=10, min_edge=0.15)
    assert len(strategies) > 0

    all_trades = []
    for strat in strategies:
        trades = backtest_strategy(
            df_out,
            symbols_out["body"],
            strat,
            atr_period=14,
            stop_atr_mult=1.0,
            reward_risk_ratio=1.5,
            max_hold_bars=3,
            spread_pips=0.0,
        )
        all_trades.extend(trades)

    assert len(all_trades) >= 3
    summary = summarize_trades(all_trades)
    assert summary["avg_r"] > 0
    assert summary["win_rate"] > 0.5
