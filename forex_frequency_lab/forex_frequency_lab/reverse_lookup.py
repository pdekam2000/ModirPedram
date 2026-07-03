from collections import Counter

from .motif_discovery import build_windows


def reverse_engineer_precursors(
    df,
    symbols,
    window_size,
    forward_k=5,
    outcome_quantile=0.1,
    min_occurrences=3,
):
    """Work backward from known outcomes to the pattern that likely caused
    them, instead of forward-discovering patterns and checking what follows.

    Takes the most extreme `outcome_quantile` fraction of forward returns
    (biggest up-moves and biggest down-moves over `forward_k` bars), looks at
    the pattern immediately preceding each one, and compares how often each
    pattern shows up before an extreme move against its baseline rate across
    the whole series. `lift` > 1 means the pattern is over-represented right
    before that kind of move; `lift` < 1 means it is under-represented.
    """
    close_values = df["Close"].values
    n = len(close_values)

    baseline_counts = Counter()
    window_end_to_code = {}
    for start, code in build_windows(symbols, window_size):
        end = start + window_size - 1
        baseline_counts[code] += 1
        window_end_to_code[end] = code

    total_windows = sum(baseline_counts.values())
    if total_windows == 0:
        return None

    returns = {}
    for end in window_end_to_code:
        if end + forward_k >= n:
            continue
        returns[end] = (close_values[end + forward_k] - close_values[end]) / close_values[end]

    if not returns:
        return None

    sorted_ends = sorted(returns, key=lambda e: returns[e])
    k = max(1, int(len(sorted_ends) * outcome_quantile))
    big_down_ends = sorted_ends[:k]
    big_up_ends = sorted_ends[-k:]

    def build_side(ends_subset):
        counts = Counter(window_end_to_code[e] for e in ends_subset)
        records = []
        for code, occ_count in counts.items():
            if occ_count < min_occurrences:
                continue
            baseline_rate = baseline_counts[code] / total_windows
            conditional_rate = occ_count / len(ends_subset)
            lift = conditional_rate / baseline_rate if baseline_rate > 0 else None
            records.append(
                {
                    "pattern_code": code,
                    "occurrences_before_outcome": occ_count,
                    "sample_size": len(ends_subset),
                    "total_occurrences_overall": baseline_counts[code],
                    "baseline_rate": baseline_rate,
                    "conditional_rate": conditional_rate,
                    "lift": lift,
                }
            )
        records.sort(key=lambda r: (r["lift"] or 0), reverse=True)
        return records

    return {
        "window_size": window_size,
        "forward_k": forward_k,
        "outcome_quantile": outcome_quantile,
        "num_extreme_windows_each_side": k,
        "precursors_before_big_up_moves": build_side(big_up_ends),
        "precursors_before_big_down_moves": build_side(big_down_ends),
    }
