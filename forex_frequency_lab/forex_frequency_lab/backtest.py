import numpy as np

from .candle_features import atr as compute_atr
from .motif_discovery import build_windows


def infer_pip_size(close_values):
    return 0.01 if np.median(close_values) > 20 else 0.0001


def _simulate_trade(close, high, low, open_, times, n, entry_index, direction, a, stop_atr_mult, reward_risk_ratio, max_hold_bars, spread_price, pip_size, name):
    entry_price = open_[entry_index]
    stop_distance = stop_atr_mult * a
    if direction == "long":
        stop_price = entry_price - stop_distance
        target_price = entry_price + stop_distance * reward_risk_ratio
    else:
        stop_price = entry_price + stop_distance
        target_price = entry_price - stop_distance * reward_risk_ratio

    exit_index = min(entry_index + max_hold_bars - 1, n - 1)
    exit_price = None
    exit_reason = "timeout"

    for j in range(entry_index, exit_index + 1):
        if direction == "long":
            hit_stop = low[j] <= stop_price
            hit_target = high[j] >= target_price
        else:
            hit_stop = high[j] >= stop_price
            hit_target = low[j] <= target_price

        if hit_stop:
            exit_price, exit_reason, exit_index = stop_price, "stop", j
            break
        if hit_target:
            exit_price, exit_reason, exit_index = target_price, "target", j
            break

    if exit_price is None:
        exit_price = close[exit_index]

    pnl_price = (exit_price - entry_price) if direction == "long" else (entry_price - exit_price)
    pnl_price -= spread_price
    r_multiple = pnl_price / stop_distance

    return {
        "strategy": name,
        "direction": direction,
        "entry_time": str(times.iloc[entry_index]),
        "exit_time": str(times.iloc[exit_index]),
        "entry_index": int(entry_index),
        "exit_index": int(exit_index),
        "exit_reason": exit_reason,
        "r_multiple": float(r_multiple),
        "pnl_pips": float(pnl_price / pip_size),
    }


def backtest_entries(
    df,
    signal_end_indices,
    direction,
    name="signal",
    atr_period=14,
    stop_atr_mult=1.5,
    reward_risk_ratio=1.5,
    max_hold_bars=5,
    spread_pips=1.5,
    pip_size=None,
):
    """Core no-look-ahead simulator: given the bar index each signal
    *completes* on, enters at the *next* bar's open, sets stop/target from
    ATR at the signal bar, and exits on whichever of stop/target/timeout
    comes first (stop wins if both trigger on the same bar). A flat
    round-trip spread cost is deducted from every trade's PnL.

    `direction` is either a fixed "long"/"short", or a callable mapping a
    signal-end index to "long"/"short" (e.g. for rules whose direction
    depends on the bar itself, not just the trigger).
    """
    close = df["Close"].values
    high = df["High"].values
    low = df["Low"].values
    open_ = df["Open"].values
    times = df["Time"]
    n = len(df)

    atr_values = compute_atr(df, atr_period).values
    pip_size = pip_size or infer_pip_size(close)
    spread_price = spread_pips * pip_size

    trades = []
    blocked_until = -1

    for signal_end in sorted(signal_end_indices):
        entry_index = signal_end + 1
        if entry_index <= blocked_until or entry_index >= n:
            continue

        a = atr_values[signal_end]
        if a is None or np.isnan(a) or a == 0:
            continue

        trade_direction = direction(signal_end) if callable(direction) else direction
        trade = _simulate_trade(
            close, high, low, open_, times, n, entry_index, trade_direction, a,
            stop_atr_mult, reward_risk_ratio, max_hold_bars, spread_price, pip_size, name,
        )
        trades.append(trade)
        blocked_until = trade["exit_index"]

    return trades


def backtest_strategy(
    df,
    symbols,
    strategy,
    atr_period=14,
    stop_atr_mult=1.5,
    reward_risk_ratio=1.5,
    max_hold_bars=5,
    spread_pips=1.5,
    pip_size=None,
):
    """Backtest a pattern-based strategy (from strategy.py) against one
    price series: finds every window matching the strategy's pattern code
    and simulates a trade after each one.
    """
    window_size = strategy["window_size"]
    pattern_code = strategy["pattern_code"]
    signal_ends = [
        start + window_size - 1 for start, code in build_windows(symbols, window_size) if code == pattern_code
    ]
    return backtest_entries(
        df,
        signal_ends,
        strategy["direction"],
        name=strategy["name"],
        atr_period=atr_period,
        stop_atr_mult=stop_atr_mult,
        reward_risk_ratio=reward_risk_ratio,
        max_hold_bars=max_hold_bars,
        spread_pips=spread_pips,
        pip_size=pip_size,
    )


def summarize_trades(trades):
    if not trades:
        return {
            "trade_count": 0,
            "win_rate": None,
            "avg_r": None,
            "profit_factor": None,
            "total_r": None,
            "max_drawdown_r": None,
            "best_trade_r": None,
            "worst_trade_r": None,
        }

    r_values = np.array([t["r_multiple"] for t in trades])
    wins = r_values[r_values > 0]
    losses = r_values[r_values <= 0]
    equity = np.cumsum(r_values)
    running_max = np.maximum.accumulate(equity)
    drawdown = equity - running_max

    gross_loss = abs(losses.sum())
    return {
        "trade_count": len(trades),
        "win_rate": float((r_values > 0).mean()),
        "avg_r": float(r_values.mean()),
        "profit_factor": float(wins.sum() / gross_loss) if gross_loss > 0 else None,
        "total_r": float(r_values.sum()),
        "max_drawdown_r": float(drawdown.min()),
        "best_trade_r": float(r_values.max()),
        "worst_trade_r": float(r_values.min()),
    }
