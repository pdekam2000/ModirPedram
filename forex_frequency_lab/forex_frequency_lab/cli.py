import argparse
import json
from pathlib import Path

import pandas as pd

from .data_loader import load_ohlc_csv
from .frequency_catalog import catalog_from_symbols, catalog_to_summary_df, save_catalog
from .candle_features import encode_candles
from .reverse_lookup import reverse_engineer_precursors
from .shadow_features import encode_shadows


def _precursors_to_df(records):
    if not records:
        return pd.DataFrame(
            columns=["pattern_code", "occurrences_before_outcome", "sample_size", "baseline_rate", "conditional_rate", "lift"]
        )
    df = pd.DataFrame(records)
    df["baseline_rate"] = df["baseline_rate"].round(4)
    df["conditional_rate"] = df["conditional_rate"].round(4)
    df["lift"] = df["lift"].round(2)
    return df[["pattern_code", "occurrences_before_outcome", "sample_size", "baseline_rate", "conditional_rate", "lift"]]


def _run_scheme(df, symbols, scheme_name, args, output_dir, top):
    catalog = catalog_from_symbols(
        df, symbols, window_sizes=args.window_sizes, min_occurrences=args.min_occurrences, forward_k=args.forward_k
    )

    suffix = "" if scheme_name == "body" else "_shadow"
    save_catalog(catalog, output_dir / f"frequency_catalog{suffix}.json")
    summary_df = catalog_to_summary_df(catalog)
    summary_df.to_csv(output_dir / f"frequency_summary{suffix}.csv", index=False)

    print(f"--- {scheme_name} shape frequencies ---")
    print(f"Discovered {len(catalog)} distinct frequencies across window sizes {args.window_sizes}")
    print(summary_df.head(top).to_string(index=False))
    print()

    if not args.skip_reverse_engineer:
        reverse_window = args.reverse_window or min(args.window_sizes)
        result = reverse_engineer_precursors(
            df,
            symbols,
            window_size=reverse_window,
            forward_k=args.forward_k,
            outcome_quantile=args.reverse_quantile,
            min_occurrences=args.reverse_min_occurrences,
        )
        if result is not None:
            with open(output_dir / f"reverse_engineering{suffix}.json", "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, default=str)

            print(f"--- {scheme_name} reverse-engineered precursors (window={reverse_window}) ---")
            print(f"Comparing top/bottom {args.reverse_quantile:.0%} of {args.forward_k}-bar forward returns"
                  f" ({result['num_extreme_windows_each_side']} windows each side) against baseline rate.")
            print("Patterns most over-represented before big UP moves:")
            print(_precursors_to_df(result["precursors_before_big_up_moves"][:top]).to_string(index=False))
            print("Patterns most over-represented before big DOWN moves:")
            print(_precursors_to_df(result["precursors_before_big_down_moves"][:top]).to_string(index=False))
            print()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Discover recurring candlestick 'frequency' patterns (body shape and/or shadow/wick shape) "
        "in OHLC forex data, and reverse-engineer which patterns precede big moves."
    )
    parser.add_argument("--csv", required=True, help="Path to an OHLC CSV file (Time/Date, Open, High, Low, Close[, Volume])")
    parser.add_argument("--scheme", choices=["body", "shadow", "both"], default="both", help="Encode by candle body shape, shadow/wick shape, or both")
    parser.add_argument("--window-sizes", type=int, nargs="+", default=[3, 4, 5], help="Candle-count(s) per pattern to search for")
    parser.add_argument("--min-occurrences", type=int, default=5, help="Minimum recurrences to count as a frequency")
    parser.add_argument("--forward-k", type=int, default=5, help="Candles to look ahead when measuring outcome after a pattern")
    parser.add_argument("--atr-period", type=int, default=14, help="Lookback for the ATR used to bucket candle size (body scheme only)")
    parser.add_argument("--top", type=int, default=20, help="How many top rows to print per table")
    parser.add_argument("--output-dir", default="output", help="Where to write catalogs / summaries")
    parser.add_argument("--skip-reverse-engineer", action="store_true", help="Skip the reverse-engineered precursor analysis")
    parser.add_argument("--reverse-window", type=int, default=None, help="Pattern length used for reverse engineering (default: smallest of --window-sizes)")
    parser.add_argument("--reverse-quantile", type=float, default=0.1, help="Fraction of most extreme forward returns to treat as 'big moves'")
    parser.add_argument("--reverse-min-occurrences", type=int, default=3, help="Minimum occurrences before a pattern is reported as a precursor")
    args = parser.parse_args(argv)

    df = load_ohlc_csv(args.csv)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loaded {len(df)} candles from {args.csv}")
    print()

    if args.scheme in ("body", "both"):
        body_symbols = encode_candles(df, atr_period=args.atr_period)
        _run_scheme(df, body_symbols, "body", args, output_dir, args.top)

    if args.scheme in ("shadow", "both"):
        shadow_symbols, _shapes = encode_shadows(df)
        _run_scheme(df, shadow_symbols, "shadow", args, output_dir, args.top)

    print(f"All output saved under: {output_dir}")


if __name__ == "__main__":
    main()
