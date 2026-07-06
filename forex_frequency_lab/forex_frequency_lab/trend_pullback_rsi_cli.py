import argparse
import json
from pathlib import Path

import pandas as pd

from .backtest import backtest_entries, summarize_trades
from .data_loader import load_ohlc_csv
from .trend_pullback_rsi import generate_signals


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Backtest the trend + pullback + RSI-reversal strategy: multi-timeframe "
        "trend filter (daily EMA50/EMA200 + ADX), enter on H4 with the trend when RSI(14) "
        "crosses back out of oversold/overbought."
    )
    parser.add_argument("--csvs", nargs="+", required=True)
    parser.add_argument("--in-sample-frac", type=float, default=0.7)
    parser.add_argument("--fast-ema", type=int, default=50)
    parser.add_argument("--slow-ema", type=int, default=200)
    parser.add_argument("--adx-period", type=int, default=14)
    parser.add_argument("--adx-threshold", type=float, default=20)
    parser.add_argument("--rsi-period", type=int, default=14)
    parser.add_argument("--oversold", type=float, default=30)
    parser.add_argument("--overbought", type=float, default=70)
    parser.add_argument("--atr-period", type=int, default=14)
    parser.add_argument("--stop-atr-mult", type=float, default=1.5)
    parser.add_argument("--reward-risk-ratio", type=float, default=3.0)
    parser.add_argument("--max-hold-bars", type=int, default=20)
    parser.add_argument("--spread-pips", type=float, default=1.5)
    parser.add_argument("--output-dir", default="output/trend_pullback_rsi")
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    all_in_trades, all_out_trades = [], []

    for csv_path in args.csvs:
        pair = Path(csv_path).stem.split("_")[0]
        df = load_ohlc_csv(csv_path)
        split = int(len(df) * args.in_sample_frac)
        df_in, df_out = df.iloc[:split].reset_index(drop=True), df.iloc[split:].reset_index(drop=True)

        ends_in, dirs_in = generate_signals(
            df_in, args.fast_ema, args.slow_ema, args.adx_period, args.adx_threshold,
            args.rsi_period, args.oversold, args.overbought,
        )
        ends_out, dirs_out = generate_signals(
            df_out, args.fast_ema, args.slow_ema, args.adx_period, args.adx_threshold,
            args.rsi_period, args.oversold, args.overbought,
        )

        in_trades = backtest_entries(
            df_in, ends_in, lambda i: dirs_in[i], name="trend_pullback_rsi",
            atr_period=args.atr_period, stop_atr_mult=args.stop_atr_mult,
            reward_risk_ratio=args.reward_risk_ratio, max_hold_bars=args.max_hold_bars,
            spread_pips=args.spread_pips,
        )
        out_trades = backtest_entries(
            df_out, ends_out, lambda i: dirs_out[i], name="trend_pullback_rsi",
            atr_period=args.atr_period, stop_atr_mult=args.stop_atr_mult,
            reward_risk_ratio=args.reward_risk_ratio, max_hold_bars=args.max_hold_bars,
            spread_pips=args.spread_pips,
        )

        in_summary = summarize_trades(in_trades)
        out_summary = summarize_trades(out_trades)
        all_in_trades += in_trades
        all_out_trades += out_trades

        rows.append(
            {
                "pair": pair,
                "in_trades": in_summary["trade_count"], "in_win_rate": in_summary["win_rate"],
                "in_avg_r": in_summary["avg_r"], "in_total_r": in_summary["total_r"],
                "out_trades": out_summary["trade_count"], "out_win_rate": out_summary["win_rate"],
                "out_avg_r": out_summary["avg_r"], "out_total_r": out_summary["total_r"],
            }
        )
        print(
            f"[{pair}] in={in_summary['trade_count']} trades avgR={in_summary['avg_r']}  "
            f"out={out_summary['trade_count']} trades avgR={out_summary['avg_r']}"
        )

        pd.DataFrame(in_trades).to_csv(output_dir / f"{pair}_trades_in_sample.csv", index=False)
        pd.DataFrame(out_trades).to_csv(output_dir / f"{pair}_trades_out_of_sample.csv", index=False)

    df_summary = pd.DataFrame(rows)
    df_summary.to_csv(output_dir / "summary_per_pair.csv", index=False)

    pooled_in = summarize_trades(all_in_trades)
    pooled_out = summarize_trades(all_out_trades)
    print()
    print(
        f"Pooled in-sample:     {pooled_in['trade_count']} trades | avg R {pooled_in['avg_r']} | "
        f"win rate {pooled_in['win_rate']} | total R {pooled_in['total_r']}"
    )
    print(
        f"Pooled out-of-sample: {pooled_out['trade_count']} trades | avg R {pooled_out['avg_r']} | "
        f"win rate {pooled_out['win_rate']} | total R {pooled_out['total_r']}"
    )
    with open(output_dir / "pooled_summary.json", "w", encoding="utf-8") as f:
        json.dump({"in_sample": pooled_in, "out_of_sample": pooled_out}, f, indent=2, default=str)

    print(f"\nSaved results under: {output_dir}")


if __name__ == "__main__":
    main()
