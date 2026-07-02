import numpy as np
import pandas as pd

DEFAULT_INJECTED_PATTERNS = [
    [(1, 0.7, 0.2), (1, 0.5, 0.3), (-1, 0.3, 0.2), (1, 0.8, 0.1), (1, 0.6, 0.2)],
    [(-1, 0.6, 0.2), (-1, 0.7, 0.1), (1, 0.2, 0.3), (-1, 0.5, 0.2), (-1, 0.8, 0.1)],
]


def _make_candle(open_price, direction, body_frac, wick_frac, step_size):
    close = open_price + direction * body_frac * step_size
    wick = wick_frac * step_size
    high = max(open_price, close) + wick
    low = min(open_price, close) - wick
    return open_price, high, low, close


def generate_synthetic_ohlc(
    n_bars=6000,
    start_price=1.10,
    step_size=0.0010,
    freq="h",
    seed=42,
    injected_patterns=None,
    injection_period=250,
    injection_jitter=15,
):
    """Generate a random-walk OHLC series with a few candle-shape patterns
    deliberately re-inserted at semi-regular intervals, so the discovery
    pipeline can be validated against a known ground truth.
    """
    rng = np.random.default_rng(seed)
    injected_patterns = injected_patterns or DEFAULT_INJECTED_PATTERNS

    opens = np.empty(n_bars)
    highs = np.empty(n_bars)
    lows = np.empty(n_bars)
    closes = np.empty(n_bars)

    price = start_price
    injection_log = []
    pattern_cycle = 0
    i = 0
    next_injection = rng.integers(injection_period, injection_period + injection_jitter)

    while i < n_bars:
        pattern_len = len(injected_patterns[pattern_cycle % len(injected_patterns)])
        if i >= next_injection and i + pattern_len <= n_bars:
            pattern = injected_patterns[pattern_cycle % len(injected_patterns)]
            pattern_cycle += 1
            for direction, body_frac, wick_frac in pattern:
                o, h, l, c = _make_candle(price, direction, body_frac, wick_frac, step_size)
                opens[i], highs[i], lows[i], closes[i] = o, h, l, c
                price = c
                i += 1
            injection_log.append(i - pattern_len)
            next_injection = i + rng.integers(injection_period, injection_period + injection_jitter)
            continue

        direction = rng.choice([-1, 1])
        body_frac = rng.uniform(0.05, 0.9)
        wick_frac = rng.uniform(0.0, 0.4)
        o, h, l, c = _make_candle(price, direction, body_frac, wick_frac, step_size)
        opens[i], highs[i], lows[i], closes[i] = o, h, l, c
        price = c
        i += 1

    times = pd.date_range("2015-01-01", periods=n_bars, freq=freq)
    df = pd.DataFrame(
        {
            "Time": times,
            "Open": opens,
            "High": highs,
            "Low": lows,
            "Close": closes,
            "Volume": rng.integers(50, 500, size=n_bars),
        }
    )
    return df, injection_log
