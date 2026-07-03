import numpy as np

from .backtest import backtest_entries, summarize_trades
from .gap_fill import discover_gap_fill_bias
from .gap_fill import signal_end_indices_and_directions as gap_fill_signal


def rolling_walk_forward_gap_fill(
    df,
    n_folds=5,
    min_in_sample_frac=0.3,
    forward_k=10,
    gap_multiplier=1.5,
    min_samples=10,
    atr_period=14,
    stop_atr_mult=1.5,
    reward_risk_ratio=1.5,
    spread_pips=1.5,
):
    """Anchored (expanding-window) walk-forward: fold 1 discovers on the
    first `min_in_sample_frac` of history and tests on the next chunk; fold
    2 discovers on everything up to there (more history now available) and
    tests on the chunk after that; and so on. This checks whether the
    gap-fade edge holds up across several different out-of-sample periods
    strung across the whole series, not just one arbitrarily-placed split.
    """
    n = len(df)
    start_idx = int(n * min_in_sample_frac)
    fold_edges = np.linspace(start_idx, n, n_folds + 1).astype(int)

    fold_results = []
    for i in range(len(fold_edges) - 1):
        train_end = fold_edges[i]
        test_start = fold_edges[i]
        test_end = fold_edges[i + 1]

        df_train = df.iloc[:train_end].reset_index(drop=True)
        df_test = df.iloc[test_start:test_end].reset_index(drop=True)

        rule = discover_gap_fill_bias(df_train, forward_k=forward_k, gap_multiplier=gap_multiplier, min_samples=min_samples)
        if rule is None or len(df_test) == 0:
            fold_results.append({"fold": i + 1, "rule_found": rule is not None, "mode": rule["mode"] if rule else None})
            continue

        ends, directions = gap_fill_signal(df_test, rule)
        trades = backtest_entries(
            df_test, ends, lambda idx: directions[idx], name="gap_fill",
            atr_period=atr_period, stop_atr_mult=stop_atr_mult, reward_risk_ratio=reward_risk_ratio,
            max_hold_bars=forward_k, spread_pips=spread_pips,
        )
        summary = summarize_trades(trades)
        fold_results.append(
            {
                "fold": i + 1,
                "rule_found": True,
                "mode": rule["mode"],
                "test_start_time": str(df_test["Time"].iloc[0]),
                "test_end_time": str(df_test["Time"].iloc[-1]),
                "out_trade_count": summary["trade_count"],
                "out_win_rate": summary["win_rate"],
                "out_avg_r": summary["avg_r"],
                "out_total_r": summary["total_r"],
            }
        )

    return fold_results
