import numpy as np


def analyze_periodicity(start_indices, timestamps):
    """Characterize how regularly a pattern's occurrences repeat.

    `cv_gap` (coefficient of variation of the candle-gap between
    consecutive occurrences) is the closest match to the user's notion of
    "frequency": low cv_gap means the pattern repeats at a near-constant
    interval; high cv_gap means it recurs but irregularly.
    """
    starts = sorted(start_indices)
    gaps = np.diff(starts)
    times = [timestamps.iloc[i] for i in starts]

    mean_gap = float(gaps.mean()) if len(gaps) else None
    std_gap = float(gaps.std()) if len(gaps) else None
    cv_gap = float(std_gap / mean_gap) if mean_gap else None

    hour_distribution = {}
    dayofweek_distribution = {}
    for t in times:
        hour_distribution[int(t.hour)] = hour_distribution.get(int(t.hour), 0) + 1
        dow = int(t.dayofweek)
        dayofweek_distribution[dow] = dayofweek_distribution.get(dow, 0) + 1

    return {
        "occurrences": len(starts),
        "mean_gap_candles": mean_gap,
        "std_gap_candles": std_gap,
        "cv_gap": cv_gap,
        "hour_distribution": hour_distribution,
        "dayofweek_distribution": dayofweek_distribution,
    }
