import numpy as np
import pandas as pd


def align_pairs(dfs_by_pair):
    """Inner-join multiple pairs' OHLC on Time so every row lines up across
    instruments. Returns (aligned_closes, aligned_ohlc_by_pair)."""
    merged_close = None
    for pair, df in dfs_by_pair.items():
        s = df.set_index("Time")["Close"].rename(pair)
        merged_close = s.to_frame() if merged_close is None else merged_close.join(s, how="inner")

    common_time = merged_close.index
    aligned_ohlc = {}
    for pair, df in dfs_by_pair.items():
        reindexed = df.set_index("Time").reindex(common_time)
        aligned_ohlc[pair] = reindexed.reset_index()

    return merged_close, aligned_ohlc


def compute_residuals(aligned_closes, in_sample_end_time):
    """Strip the shared USD-driven common factor (equal-weight average log
    return across the basket) out of each pair's return, using a beta
    estimated on in-sample data only. What's left (the residual) is the
    pair-specific move, which is what cross-pair lead-lag should be tested
    on rather than raw returns dominated by the common factor.
    """
    log_returns = np.log(aligned_closes).diff().dropna()
    common_factor = log_returns.mean(axis=1)
    in_sample_mask = log_returns.index <= in_sample_end_time

    betas = {}
    residuals = pd.DataFrame(index=log_returns.index)
    for pair in log_returns.columns:
        y_in = log_returns.loc[in_sample_mask, pair]
        x_in = common_factor.loc[in_sample_mask]
        beta = np.cov(y_in, x_in)[0, 1] / np.var(x_in)
        betas[pair] = float(beta)
        residuals[pair] = log_returns[pair] - beta * common_factor

    return residuals, betas


def discover_lead_lag(residuals, in_sample_end_time, max_lag=3, min_abs_corr=0.05, min_samples=200):
    """On in-sample residuals only: scan every (leader, follower, lag)
    triple and keep the strongest correlation between the leader's residual
    at t and the follower's residual at t+lag.
    """
    in_sample = residuals.loc[residuals.index <= in_sample_end_time]
    pairs = list(in_sample.columns)

    best = None
    for leader in pairs:
        for follower in pairs:
            if leader == follower:
                continue
            for lag in range(1, max_lag + 1):
                x = in_sample[leader].iloc[:-lag].values
                y = in_sample[follower].iloc[lag:].values
                if len(x) < min_samples:
                    continue
                corr = np.corrcoef(x, y)[0, 1]
                if np.isnan(corr):
                    continue
                if best is None or abs(corr) > abs(best["correlation"]):
                    best = {"leader": leader, "follower": follower, "lag": lag, "correlation": float(corr), "sample_size": len(x)}

    if best is None or abs(best["correlation"]) < min_abs_corr:
        return None
    return best


def discover_lead_lag_strategy(residuals, in_sample_end_time, max_lag=3, min_abs_corr=0.05, extreme_quantile=0.8):
    relationship = discover_lead_lag(residuals, in_sample_end_time, max_lag=max_lag, min_abs_corr=min_abs_corr)
    if relationship is None:
        return None

    in_sample_leader = residuals.loc[residuals.index <= in_sample_end_time, relationship["leader"]]
    relationship["extreme_threshold"] = float(in_sample_leader.abs().quantile(extreme_quantile))
    relationship["extreme_quantile"] = extreme_quantile
    return relationship


def signal_end_indices_and_directions(residuals, relationship):
    """Positions (0-based, matching the aligned index) where the leader's
    residual is "extreme" enough to fire a directional bet on the follower,
    using only the threshold/correlation-sign discovered in-sample.
    """
    leader_values = residuals[relationship["leader"]].values
    threshold = relationship["extreme_threshold"]
    corr_sign = 1 if relationship["correlation"] > 0 else -1

    signal_ends = []
    directions = {}
    for i, v in enumerate(leader_values):
        if np.isnan(v) or abs(v) < threshold:
            continue
        leader_dir = 1 if v > 0 else -1
        follower_dir = leader_dir * corr_sign
        signal_ends.append(i)
        directions[i] = "long" if follower_dir > 0 else "short"

    return signal_ends, directions
