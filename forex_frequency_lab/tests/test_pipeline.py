import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from forex_frequency_lab.data_loader import load_ohlc_csv
from forex_frequency_lab.frequency_catalog import build_frequency_catalog
from forex_frequency_lab.synthetic_data import generate_synthetic_ohlc


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
