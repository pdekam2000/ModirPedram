import numpy as np


def zscore(values):
    values = np.asarray(values, dtype=float)
    std = values.std()
    if std == 0:
        return np.zeros_like(values)
    return (values - values.mean()) / std


def window_trend(close_values):
    """Fit a line through the (z-normalized) closes of one pattern occurrence.

    Returns slope, angle in degrees, and R^2 fit quality. Using z-scored
    values makes the angle comparable across occurrences and instruments,
    independent of absolute price level.
    """
    z = zscore(close_values)
    x = np.arange(len(z))
    slope, intercept = np.polyfit(x, z, 1)
    fitted = slope * x + intercept
    ss_res = np.sum((z - fitted) ** 2)
    ss_tot = np.sum((z - z.mean()) ** 2)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    angle_degrees = float(np.degrees(np.arctan(slope)))
    return {"slope": float(slope), "angle_degrees": angle_degrees, "r2": float(r2)}
