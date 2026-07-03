import pandas as pd

_COLUMN_ALIASES = {
    "time": ["time", "datetime", "date_time", "timestamp"],
    "date": ["date"],
    "open": ["open", "o"],
    "high": ["high", "h"],
    "low": ["low", "l"],
    "close": ["close", "c"],
    # tick volume first: real traded volume doesn't exist for OTC forex, so
    # MT4/MT5 exports report it as 0 in <VOL> and put the usable proxy
    # (number of price updates) in <TICKVOL> instead.
    "volume": ["tick_volume", "tickvol", "volume", "vol"],
}


def _find_column(columns, aliases):
    lower_map = {c.lower().strip().strip("<>"): c for c in columns}
    for alias in aliases:
        if alias in lower_map:
            return lower_map[alias]
    return None


def load_ohlc_csv(path):
    df = pd.read_csv(path, sep=None, engine="python")
    df.columns = [str(c).strip() for c in df.columns]

    time_col = _find_column(df.columns, _COLUMN_ALIASES["time"])
    date_col = _find_column(df.columns, _COLUMN_ALIASES["date"])
    open_col = _find_column(df.columns, _COLUMN_ALIASES["open"])
    high_col = _find_column(df.columns, _COLUMN_ALIASES["high"])
    low_col = _find_column(df.columns, _COLUMN_ALIASES["low"])
    close_col = _find_column(df.columns, _COLUMN_ALIASES["close"])
    volume_col = _find_column(df.columns, _COLUMN_ALIASES["volume"])

    missing = [
        name
        for name, col in [("Open", open_col), ("High", high_col), ("Low", low_col), ("Close", close_col)]
        if col is None
    ]
    if missing:
        raise ValueError(f"CSV is missing required column(s): {missing}. Found columns: {list(df.columns)}")

    if time_col is not None and date_col is not None:
        timestamps = pd.to_datetime(df[date_col].astype(str) + " " + df[time_col].astype(str))
    elif time_col is not None:
        timestamps = pd.to_datetime(df[time_col])
    elif date_col is not None:
        timestamps = pd.to_datetime(df[date_col])
    else:
        raise ValueError(f"CSV is missing a Time/Date column. Found columns: {list(df.columns)}")

    out = pd.DataFrame(
        {
            "Time": timestamps,
            "Open": df[open_col].astype(float),
            "High": df[high_col].astype(float),
            "Low": df[low_col].astype(float),
            "Close": df[close_col].astype(float),
            "Volume": df[volume_col].astype(float) if volume_col else 0.0,
        }
    )
    out = out.sort_values("Time").drop_duplicates(subset="Time").reset_index(drop=True)
    return out
