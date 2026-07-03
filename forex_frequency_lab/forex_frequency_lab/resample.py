import pandas as pd


def resample_ohlc(df, rule):
    """Aggregate a finer OHLC series into a coarser one (e.g. H4 -> D1) using
    real Open/High/Low/Close/Volume aggregation, not synthetic data.
    """
    indexed = df.set_index("Time")
    agg = indexed.resample(rule).agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    )
    return agg.dropna(subset=["Open", "High", "Low", "Close"]).reset_index()
