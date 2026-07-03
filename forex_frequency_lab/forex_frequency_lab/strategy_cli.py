import argparse
import json
from pathlib import Path

import pandas as pd

from .backtest import backtest_strategy, summarize_trades
from .candle_features import encode_candles
from .data_loader import load_ohlc_csv
from .frequency_catalog import catalog_from_symbols
from .reverse_lookup import reverse_engineer_precursors
from .shadow_features import encode_shadows
from .strategy import derive_strategies_from_catalog, derive_strategies_from_reverse
from .walk_forward import split_in_out_sample


def _derive_all_strategies(df_slice, symbols_slice, args):
    strategies = []
    for scheme in ("body", "shadow"):
        symbols = symbols_slice[scheme]
        catalog = catalog_from_symbols(
            df_slice, symbols, window_sizes=args.window_sizes, min_occurrences=args.min_occurrences, forward_k=args.forward_k
        )
        strategies += derive_strategies_from_catalog(
            catalog, scheme=scheme, top_n=args.top_n_per_source, min_count=args.min_occurrences, min_edge=args.min_edge
        )

        reverse_window = args.reverse_window or min(args.window_sizes)
        reverse_result = reverse_engineer_precursors(
            df_slice,
            symbols,
            window_size=reverse_window,
            forward_k=args.forward_k,
            outcome_quantile=args.reverse_quantile,
            min_occurrences=args.reverse_min_occurrences,
        )
        strategies += derive_strategies_from_reverse(
            reverse_result, scheme=scheme, top_n=args.top_n_per_source, min_lift=args.min_lift, min_occurrences=args.reverse_min_occurrences
        )
    return strategies


def _backtest_all(df_slice, symbols_slice, strategies, args):
    all_trades = []
    per_strategy = []
    for strat in strategies:
        trades = backtest_strategy(
            df_slice,
            symbols_slice[strat["scheme"]],
            strat,
            atr_period=args.atr_period,
            stop_atr_mult=args.stop_atr_mult,
            reward_risk_ratio=args.reward_risk_ratio,
            max_hold_bars=args.forward_k,
            spread_pips=args.spread_pips,
        )
        all_trades += trades
        summary = summarize_trades(trades)
        summary["strategy"] = strat["name"]
        summary["direction"] = strat["direction"]
        summary["source"] = strat["source"]
        per_strategy.append(summary)
    return all_trades, per_strategy


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Derive trading rules from discovered frequencies/precursors, then backtest them "
        "out-of-sample: discover on the first --in-sample-frac of history, test on the untouched rest."
    )
    parser.add_argument("--csv", required=True)
    parser.add_argument("--in-sample-frac", type=float, default=0.7)
    parser.add_argument("--window-sizes", type=int, nargs="+", default=[3, 4, 5])
    parser.add_argument("--min-occurrences", type=int, default=6)
    parser.add_argument("--forward-k", type=int, default=5, help="Also used as max holding period for backtested trades")
    parser.add_argument("--atr-period", type=int, default=14)
    parser.add_argument("--min-edge", type=float, default=0.15, help="Minimum |win_rate - 0.5| for a catalog pattern to become a strategy")
    parser.add_argument("--min-lift", type=float, default=3.0, help="Minimum lift for a reverse-engineered precursor to become a strategy")
    parser.add_argument("--reverse-window", type=int, default=None)
    parser.add_argument("--reverse-quantile", type=float, default=0.1)
    parser.add_argument("--reverse-min-occurrences", type=int, default=4)
    parser.add_argument("--top-n-per-source", type=int, default=5)
    parser.add_argument("--stop-atr-mult", type=float, default=1.5)
    parser.add_argument("--reward-risk-ratio", type=float, default=1.5)
    parser.add_argument("--spread-pips", type=float, default=1.5)
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args(argv)

    df = load_ohlc_csv(args.csv)
    body_symbols = encode_candles(df, atr_period=args.atr_period)
    shadow_symbols, _shapes = encode_shadows(df)

    _split_idx, (df_in, symbols_in), (df_out, symbols_out) = split_in_out_sample(
        df, {"body": body_symbols, "shadow": shadow_symbols}, in_sample_frac=args.in_sample_frac
    )

    print(f"Loaded {len(df)} candles from {args.csv}")
    print(f"In-sample: {len(df_in)} candles ({df_in['Time'].iloc[0]} .. {df_in['Time'].iloc[-1]})")
    print(f"Out-of-sample: {len(df_out)} candles ({df_out['Time'].iloc[0]} .. {df_out['Time'].iloc[-1]})")
    print()

    strategies = _derive_all_strategies(df_in, symbols_in, args)
    print(f"Derived {len(strategies)} candidate strategies from in-sample data")
    if not strategies:
        print("No strategy cleared the thresholds - try lowering --min-edge / --min-lift or --min-occurrences.")
        return

    in_trades, in_per_strategy = _backtest_all(df_in, symbols_in, strategies, args)
    out_trades, out_per_strategy = _backtest_all(df_out, symbols_out, strategies, args)

    in_summary = summarize_trades(in_trades)
    out_summary = summarize_trades(out_trades)

    print("--- Per-strategy: in-sample vs out-of-sample ---")
    in_df = pd.DataFrame(in_per_strategy).set_index("strategy").add_prefix("in_")
    out_df = pd.DataFrame(out_per_strategy).set_index("strategy").add_prefix("out_")
    combined = in_df.join(out_df, how="outer")
    cols = [
        "in_trade_count", "in_win_rate", "in_avg_r", "in_profit_factor",
        "out_trade_count", "out_win_rate", "out_avg_r", "out_profit_factor",
    ]
    print(combined[cols].round(3).to_string())
    print()

    print("--- Pooled portfolio (every strategy's trades combined) ---")
    print(f"In-sample:     {in_summary['trade_count']:4d} trades | win rate {in_summary['win_rate']} | avg R {in_summary['avg_r']} | total R {in_summary['total_r']} | max DD (R) {in_summary['max_drawdown_r']}")
    print(f"Out-of-sample: {out_summary['trade_count']:4d} trades | win rate {out_summary['win_rate']} | avg R {out_summary['avg_r']} | total R {out_summary['total_r']} | max DD (R) {out_summary['max_drawdown_r']}")
    print()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "strategies.json", "w", encoding="utf-8") as f:
        json.dump(strategies, f, indent=2, default=str)
    combined.reset_index().to_csv(output_dir / "strategy_backtest_per_strategy.csv", index=False)
    pd.DataFrame(in_trades).to_csv(output_dir / "backtest_trades_in_sample.csv", index=False)
    pd.DataFrame(out_trades).to_csv(output_dir / "backtest_trades_out_of_sample.csv", index=False)
    with open(output_dir / "backtest_pooled_summary.json", "w", encoding="utf-8") as f:
        json.dump({"in_sample": in_summary, "out_of_sample": out_summary}, f, indent=2, default=str)

    print(f"Saved strategies, trades, and summaries under: {output_dir}")


if __name__ == "__main__":
    main()
