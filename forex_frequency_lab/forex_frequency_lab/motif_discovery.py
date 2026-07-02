from collections import defaultdict


def build_windows(symbols, window_size):
    n = len(symbols)
    for start in range(n - window_size + 1):
        chunk = symbols[start : start + window_size]
        if any(s is None for s in chunk):
            continue
        yield start, "|".join(chunk)


def discover_patterns(symbols, window_size, min_occurrences=5):
    """Group all candle windows of `window_size` by identical symbol sequence.

    Returns {pattern_code: [start_index, ...]} for patterns that recur at
    least `min_occurrences` times across the whole series.
    """
    groups = defaultdict(list)
    for start, code in build_windows(symbols, window_size):
        groups[code].append(start)
    return {code: starts for code, starts in groups.items() if len(starts) >= min_occurrences}
