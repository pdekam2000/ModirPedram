import numpy as np

DEFAULT_WICK_THRESHOLDS = (0.15, 0.40)
DEFAULT_SYMMETRY_EPSILON = 0.12

_SHAPE_NAMES = {
    (0, 0): "marubozu",
    (2, 0): "shooting_star",
    (0, 2): "hammer",
    (2, 2): "long_legged",
}


def classify_shape(upper_bucket, lower_bucket, symmetry_epsilon=DEFAULT_SYMMETRY_EPSILON, upper_ratio=0.0, lower_ratio=0.0):
    name = _SHAPE_NAMES.get((upper_bucket, lower_bucket))
    if name is not None:
        return name
    if abs(upper_ratio - lower_ratio) < symmetry_epsilon:
        return "symmetric"
    return "upper_heavy" if upper_ratio > lower_ratio else "lower_heavy"


def encode_shadows(df, wick_thresholds=DEFAULT_WICK_THRESHOLDS, symmetry_epsilon=DEFAULT_SYMMETRY_EPSILON):
    """Encode each candle by its wick/shadow shape, independent of the body.

    Symbol format "U{bucket}L{bucket}": upper-wick bucket + lower-wick bucket,
    each 0 (short) / 1 (medium) / 2 (long) relative to the candle's own
    high-low range. e.g. "U2L0" = long upper wick, no lower wick
    (shooting-star shape); "U0L2" = hammer/pin-bar shape.

    Returns (symbols, shapes): parallel lists, `shapes` giving the
    human-readable shape name for each candle (None where range is 0).
    """
    small_t, large_t = wick_thresholds
    open_ = df["Open"].values
    high = df["High"].values
    low = df["Low"].values
    close = df["Close"].values
    n = len(df)

    symbols = [None] * n
    shapes = [None] * n

    for i in range(n):
        rng = high[i] - low[i]
        if rng == 0:
            symbols[i] = "U0L0"
            shapes[i] = "marubozu"
            continue

        upper_wick = high[i] - max(open_[i], close[i])
        lower_wick = min(open_[i], close[i]) - low[i]
        upper_ratio = upper_wick / rng
        lower_ratio = lower_wick / rng

        upper_bucket = 0 if upper_ratio < small_t else (1 if upper_ratio < large_t else 2)
        lower_bucket = 0 if lower_ratio < small_t else (1 if lower_ratio < large_t else 2)

        symbols[i] = f"U{upper_bucket}L{lower_bucket}"
        shapes[i] = classify_shape(
            upper_bucket, lower_bucket, symmetry_epsilon, upper_ratio=upper_ratio, lower_ratio=lower_ratio
        )

    return symbols, shapes
