import argparse
import json
from pathlib import Path

import pandas as pd

from .backtest import backtest_entries, summarize_trades
from .cross_pair import align_pairs, compute_residuals, discover_lead_lag_strategy
from .cross_pair import signal_end_indices_and_directions as cross_pair_signal
from .data_loader import load_ohlc_csv
from .seasonality import discover_seasonal_bias
from .seasonality import signal_end_indices as seasonality_signal
from .volatility_regime import discover_volatility_regime_bias
from .volatility_regime import signal_end_indices_and_directions as vol_regime_signal
from .volume_divergence import discover_volume_divergence_bias
from .volume_divergence import signal_end_indices_and_directions as vol_divergence_signal


def _split(df, in_sample_frac):
    split_idx = int(len(df) * in_sample_frac)
    return df.iloc[:split_idx].reset_index(drop=True), df.iloc[split_idx:].reset_index(drop=True)


def _backtest(df_slice, signal_ends, direction, name, args):
    return backtest_entries(
        df_slice, signal_ends, direction, name=name,
        atr_period=args.atr_period, stop_atr_mult=args.stop_atr_mult, reward_risk_ratio=args.reward_risk_ratio,
        max_hold_bars=args.forward_k, spread_pips=args.spread_pips,
    )


def run_single_pair_ideas(df, args):
    df_in, df_out = _split(df, args.in_sample_frac)
    results = []

    rule = discover_seasonal_bias(df_in, forward_k=args.forward_k, group_by="hour", min_samples=args.min_samples)
    if rule:
        in_trades = _backtest(df_in, seasonality_signal(df_in, rule), rule["direction"], "seasonality_hour", args)
        out_trades = _backtest(df_out, seasonality_signal(df_out, rule), rule["direction"], "seasonality_hour", args)
        results.append(("seasonality_hour", rule, in_trades, out_trades))

    rule = discover_seasonal_bias(df_in, forward_k=args.forward_k, group_by="dayofweek", min_samples=args.min_samples)
    if rule:
        in_trades = _backtest(df_in, seasonality_signal(df_in, rule), rule["direction"], "seasonality_dow", args)
        out_trades = _backtest(df_out, seasonality_signal(df_out, rule), rule["direction"], "seasonality_dow", args)
        results.append(("seasonality_dow", rule, in_trades, out_trades))

    rule = discover_volatility_regime_bias(df_in, atr_period=args.atr_period, forward_k=args.forward_k, min_samples=args.min_samples)
    if rule:
        ends_in, dirs_in = vol_regime_signal(df_in, rule)
        ends_out, dirs_out = vol_regime_signal(df_out, rule)
        in_trades = _backtest(df_in, ends_in, lambda i: dirs_in[i], "volatility_regime", args)
        out_trades = _backtest(df_out, ends_out, lambda i: dirs_out[i], "volatility_regime", args)
        results.append(("volatility_regime", rule, in_trades, out_trades))

    rule = discover_volume_divergence_bias(df_in, forward_k=args.forward_k, min_samples=args.min_samples)
    if rule:
        ends_in, dirs_in = vol_divergence_signal(df_in, rule)
        ends_out, dirs_out = vol_divergence_signal(df_out, rule)
        in_trades = _backtest(df_in, ends_in, lambda i: dirs_in[i], "volume_divergence", args)
        out_trades = _backtest(df_out, ends_out, lambda i: dirs_out[i], "volume_divergence", args)
        results.append(("volume_divergence", rule, in_trades, out_trades))

    return results


def run_cross_pair_idea(dfs_by_pair, args):
    aligned_closes, aligned_ohlc = align_pairs(dfs_by_pair)
    split_idx = int(len(aligned_closes) * args.in_sample_frac)
    split_time = aligned_closes.index[split_idx]

    residuals, betas = compute_residuals(aligned_closes, split_time)
    relationship = discover_lead_lag_strategy(residuals, split_time, max_lag=args.max_lag, min_abs_corr=args.min_abs_corr)
    if relationship is None:
        return None, betas

    residuals_in = residuals.loc[residuals.index <= split_time].reset_index(drop=True)
    residuals_out = residuals.loc[residuals.index > split_time].reset_index(drop=True)
    ends_in, dirs_in = cross_pair_signal(residuals_in, relationship)
    ends_out, dirs_out = cross_pair_signal(residuals_out, relationship)

    follower = relationship["follower"]
    follower_df_in = aligned_ohlc[follower].loc[aligned_ohlc[follower]["Time"] <= split_time].reset_index(drop=True)
    follower_df_out = aligned_ohlc[follower].loc[aligned_ohlc[follower]["Time"] > split_time].reset_index(drop=True)

    in_trades = _backtest(follower_df_in, ends_in, lambda i: dirs_in[i], f"cross_pair_{relationship['leader']}->{follower}", args)
    out_trades = _backtest(follower_df_out, ends_out, lambda i: dirs_out[i], f"cross_pair_{relationship['leader']}->{follower}", args)

    return (relationship, in_trades, out_trades), betas


def main(argv=None):
    parser = argparse.ArgumentParser(description="Test several genuinely different trading ideas, each with an honest in-sample/out-of-sample split.")
    parser.add_argument("--csvs", nargs="+", required=True, help="One or more OHLC CSV files. With 2+, also runs the cross-pair lead-lag idea.")
    parser.add_argument("--in-sample-frac", type=float, default=0.7)
    parser.add_argument("--forward-k", type=int, default=5)
    parser.add_argument("--atr-period", type=int, default=14)
    parser.add_argument("--min-samples", type=int, default=30)
    parser.add_argument("--stop-atr-mult", type=float, default=1.5)
    parser.add_argument("--reward-risk-ratio", type=float, default=1.5)
    parser.add_argument("--spread-pips", type=float, default=1.5)
    parser.add_argument("--max-lag", type=int, default=3)
    parser.add_argument("--min-abs-corr", type=float, default=0.05)
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    dfs_by_pair = {}
    single_pair_rows = []
    for csv_path in args.csvs:
        pair = Path(csv_path).stem.split("_")[0]
        df = load_ohlc_csv(csv_path)
        dfs_by_pair[pair] = df

        results = run_single_pair_ideas(df, args)
        for idea, rule, in_trades, out_trades in results:
            in_summary = summarize_trades(in_trades)
            out_summary = summarize_trades(out_trades)
            single_pair_rows.append(
                {
                    "pair": pair, "idea": idea, "rule": json.dumps(rule, default=str),
                    "in_trades": in_summary["trade_count"], "in_win_rate": in_summary["win_rate"], "in_avg_r": in_summary["avg_r"],
                    "out_trades": out_summary["trade_count"], "out_win_rate": out_summary["win_rate"], "out_avg_r": out_summary["avg_r"],
                }
            )
            print(f"[{pair}] {idea}: in={in_summary['trade_count']} trades avgR={in_summary['avg_r']}  "
                  f"out={out_summary['trade_count']} trades avgR={out_summary['avg_r']}")

    single_pair_df = pd.DataFrame(single_pair_rows)
    single_pair_df.to_csv(output_dir / "idea_lab_single_pair_results.csv", index=False)

    cross_pair_row = None
    if len(dfs_by_pair) >= 2:
        result, betas = run_cross_pair_idea(dfs_by_pair, args)
        if result is not None:
            relationship, in_trades, out_trades = result
            in_summary = summarize_trades(in_trades)
            out_summary = summarize_trades(out_trades)
            cross_pair_row = {
                "leader": relationship["leader"], "follower": relationship["follower"], "lag": relationship["lag"],
                "in_sample_correlation": relationship["correlation"],
                "in_trades": in_summary["trade_count"], "in_win_rate": in_summary["win_rate"], "in_avg_r": in_summary["avg_r"],
                "out_trades": out_summary["trade_count"], "out_win_rate": out_summary["win_rate"], "out_avg_r": out_summary["avg_r"],
            }
            print(f"[cross-pair] {relationship['leader']} -> {relationship['follower']} (lag={relationship['lag']}, "
                  f"corr={relationship['correlation']:.3f}): in={in_summary['trade_count']} avgR={in_summary['avg_r']}  "
                  f"out={out_summary['trade_count']} avgR={out_summary['avg_r']}")
            pd.DataFrame([cross_pair_row]).to_csv(output_dir / "idea_lab_cross_pair_result.csv", index=False)
        else:
            print("[cross-pair] no lead-lag relationship cleared --min-abs-corr on in-sample data")

    print(f"\nSaved results under: {output_dir}")


if __name__ == "__main__":
    main()
