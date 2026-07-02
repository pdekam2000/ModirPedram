import argparse
from pathlib import Path

from .data_loader import load_ohlc_csv
from .frequency_catalog import build_frequency_catalog, catalog_to_summary_df, save_catalog


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Discover recurring candlestick 'frequency' patterns in OHLC forex data."
    )
    parser.add_argument("--csv", required=True, help="Path to an OHLC CSV file (Time/Date, Open, High, Low, Close[, Volume])")
    parser.add_argument("--window-sizes", type=int, nargs="+", default=[3, 4, 5], help="Candle-count(s) per pattern to search for")
    parser.add_argument("--min-occurrences", type=int, default=5, help="Minimum recurrences to count as a frequency")
    parser.add_argument("--forward-k", type=int, default=5, help="Candles to look ahead when measuring outcome after a pattern")
    parser.add_argument("--atr-period", type=int, default=14, help="Lookback for the ATR used to bucket candle size")
    parser.add_argument("--top", type=int, default=20, help="How many top frequencies to print")
    parser.add_argument("--output-dir", default="output", help="Where to write frequency_catalog.json / frequency_summary.csv")
    args = parser.parse_args(argv)

    df = load_ohlc_csv(args.csv)
    catalog = build_frequency_catalog(
        df,
        window_sizes=args.window_sizes,
        min_occurrences=args.min_occurrences,
        forward_k=args.forward_k,
        atr_period=args.atr_period,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    save_catalog(catalog, output_dir / "frequency_catalog.json")
    summary_df = catalog_to_summary_df(catalog)
    summary_df.to_csv(output_dir / "frequency_summary.csv", index=False)

    print(f"Loaded {len(df)} candles from {args.csv}")
    print(f"Discovered {len(catalog)} distinct frequencies across window sizes {args.window_sizes}")
    print()
    print(summary_df.head(args.top).to_string(index=False))
    print()
    print(f"Full catalog saved to: {output_dir / 'frequency_catalog.json'}")
    print(f"Summary table saved to: {output_dir / 'frequency_summary.csv'}")


if __name__ == "__main__":
    main()
