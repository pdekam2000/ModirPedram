# Forex Frequency Lab

Pattern-mining tool that treats candlestick price action as a signal: it scans
historical OHLC data for N-candle sequences that recur many times, labels each
distinct recurring sequence as a "Frequency" (Frequency 1, Frequency 2, ...),
and reports, for each one:

- how many candles make up the pattern and how many times it occurred
- the average trend angle/slope inside the pattern (the "soodi/nozooli" slope)
- how regularly it recurs in time (mean gap between occurrences, and a
  coefficient-of-variation score — low = near-periodic, high = irregular)
- what tends to happen afterwards (mean forward return and win-rate over the
  next K candles)

This is the same idea as **motif discovery** in time-series analysis, applied
to candlestick shapes instead of raw waveforms.

## How it works

There are two independent encoding schemes — pick one or run both:

- **Body scheme**: direction (up/down/doji) + size vs. ATR (small/medium/large)
  + body strength (weak/medium/strong). Example: `UM2` = bullish candle,
  medium range, medium body strength.
- **Shadow/wick scheme**: upper-wick bucket + lower-wick bucket (short/medium/
  long each), independent of the body. Example: `U2L0` = long upper wick, no
  lower wick (shooting-star shape); `U0L2` = hammer/pin-bar shape.

Discovery pipeline for either scheme:

1. **Encode** each candle into a discrete symbol under the chosen scheme.
2. **Slide a window** of N candles across the whole series and group windows
   that produce the *identical* symbol sequence — those are candidate
   recurring patterns.
3. **Keep** only sequences that occur at least `--min-occurrences` times.
4. **Score** each kept pattern: trend angle (via z-scored linear regression),
   occurrence periodicity, and forward outcome.
5. **Rank** patterns by occurrence count and save the full catalog + a
   summary table.

There is also a **reverse-engineering** pass, which runs the discovery
direction backward: instead of finding a pattern first and then checking what
happens after it, it starts from the known biggest price moves (top/bottom
`--reverse-quantile` of forward returns) and looks at which single pattern
sat immediately before each one. Each pattern gets a `lift` score — its rate
right before a big move divided by its baseline rate across the whole
series. `lift` well above 1 means that pattern is a disproportionate
precursor to that kind of move.

## Setup

```bash
cd forex_frequency_lab
pip install -r requirements.txt
```

## Usage

Drop your OHLC CSV into `data/` (any of these column names are recognized,
case-insensitive, including MT4/MT5-style `<OPEN>`, `<TICKVOL>`, etc.):

- Time column: `Time` / `DateTime` / `Timestamp`, or separate `Date` + `Time`
- `Open`, `High`, `Low`, `Close`, and optionally `Volume`

Then run:

```bash
python -m forex_frequency_lab.cli --csv data/EURUSD_H1.csv \
    --scheme both \
    --window-sizes 3 4 5 6 \
    --min-occurrences 10 \
    --forward-k 5 \
    --output-dir output
```

`--scheme` is `body`, `shadow`, or `both` (default `both`). This prints a
summary table per scheme plus a reverse-engineered precursor table, and
writes, per scheme (body files have no suffix, shadow files are `_shadow`):

- `output/frequency_catalog[_shadow].json` — full detail per frequency (all
  occurrence timestamps, angle stats, periodicity, forward return/win-rate)
- `output/frequency_summary[_shadow].csv` — one row per frequency for quick
  scanning
- `output/reverse_engineering[_shadow].json` — patterns ranked by `lift`
  before big up-moves and big down-moves

Tune `--window-sizes` to test different candle-counts per pattern, and
`--min-occurrences` to control how strict "recurring" means (too low = noise,
too high = nothing survives). Reverse engineering has its own knobs:
`--reverse-window` (pattern length, defaults to the smallest `--window-sizes`
value), `--reverse-quantile` (how extreme a move counts as "big", default
10%), and `--reverse-min-occurrences`. Pass `--skip-reverse-engineer` to turn
it off.

## Turning findings into a strategy and backtesting it out-of-sample

`strategy_cli.py` closes the loop: it derives concrete long/short trade rules
from the frequencies and precursors above, then backtests them the only way
that means anything — discover on one slice of history, test on a slice it
never saw.

```bash
python -m forex_frequency_lab.strategy_cli --csv data/EURUSD_H1.csv \
    --in-sample-frac 0.7 \
    --stop-atr-mult 1.5 \
    --reward-risk-ratio 1.5 \
    --spread-pips 1.5 \
    --output-dir output
```

What it does:

1. Splits the series at `--in-sample-frac` (default 70/30) — everything
   before the split is "in-sample", everything after is an untouched
   "out-of-sample" holdout.
2. Runs frequency discovery and reverse-engineering **on the in-sample slice
   only**, and turns the strongest results into trade rules: `derive_strategies_from_catalog`
   goes long/short based on which way a pattern's forward win-rate leans;
   `derive_strategies_from_reverse` goes long/short based on which kind of
   big move a precursor pattern showed up before.
3. Backtests every rule on both slices with `backtest_strategy`: entry at the
   next bar's open after the pattern completes (no look-ahead), stop/target
   set from ATR at the signal bar, exit on whichever of stop/target/timeout
   comes first, a flat round-trip spread cost deducted from every trade.
4. Reports **both** in-sample and out-of-sample results side by side, per
   strategy and pooled, in R-multiples (PnL ÷ initial risk, so it doesn't
   depend on position-sizing assumptions).

**What we found running this on the real data**: every one of the 7 pairs
looked strong in-sample (63–79% win rate, +0.18 to +0.46 average R per
trade) — and in 6 of 7, that edge collapsed to roughly breakeven or negative
out-of-sample (pooled across all pairs: +0.38R/trade in-sample vs.
&minus;0.06R/trade out-of-sample). That is the signature of overfitting, not
a real edge: with hundreds of candidate patterns tested per pair, some will
look great in-sample by chance alone. Treat any single pattern's in-sample
stats as a hypothesis, never as a result — the out-of-sample number is the
only one that matters, and so far it says "no edge survives."
`output/walk_forward_verdict.csv` has the full pair-by-pair breakdown.

## Testing genuinely different ideas (not more candle-shape variants)

Candle-shape pattern mining has one structural problem: it tests hundreds of
candidate shapes per pair, so some look great in-sample by chance alone
(exactly what the section above caught). `idea_lab_cli.py` instead tests a
small number of ideas that are actually different from each other and from
candle-shape mining, each through the same honest in-sample/out-of-sample
split:

- **`seasonality.py`** — is there an hour-of-day or day-of-week with a
  persistent directional bias (session-open effects, "day of the week"
  seasonality)?
- **`volatility_regime.py`** — after an unusually large-range bar, does price
  tend to keep going (continuation) or snap back (mean reversion)?
- **`volume_divergence.py`** — a big move on unusually *low* tick volume
  (weak participation relative to the size of the move) — does that predict
  a fade or a continuation? (This surfaced a real bug: the loader had been
  picking the `<VOL>` column, which MT5 always reports as 0 for OTC forex,
  instead of `<TICKVOL>`, the actual usable proxy — fixed in `data_loader.py`.)
- **`cross_pair.py`** — the most structurally different idea: every pair here
  shares a USD leg, so strip out that common factor (regress each pair
  against an equal-weight basket, in-sample only) and test whether one
  pair's *residual* move leads another's by 1–3 bars — inter-market
  structure instead of re-slicing one series' own noise.
- **`gap_fill.py`** — forex is closed Friday night to Sunday night, so every
  week opens with a price gap. Does that gap tend to keep going
  (continuation) or retrace back toward the pre-gap level (fill)? Detected
  generically (any time gap well above the series' typical bar spacing),
  not by hardcoding specific weekday boundaries.
- **`mean_reversion.py`** — when price is unusually far (top decile of
  z-score) from its own rolling moving average, does it keep extending or
  snap back?

```bash
python -m forex_frequency_lab.idea_lab_cli \
    --csvs data/AUDUSD_H4.csv data/GBPUSD_H4.csv data/USDCHF_H4.csv data/USDJPY_H4.csv \
    --in-sample-frac 0.7 \
    --output-dir output
```

Pass one CSV to test only the single-pair ideas; pass 2+ (with overlapping
timestamps) and it also runs the cross-pair lead-lag search across all of
them.

**What we found**: smaller and more honest than the candle-pattern results —
in-sample edges here were modest, which makes sense since there are far
fewer candidate rules being searched. Out-of-sample, four of six ideas
still averaged negative or negligible across every pair tested
(seasonality-by-day-of-week &minus;0.073R, volatility-regime &minus;0.064R,
volume-divergence &minus;0.028R, mean-reversion &minus;0.058R,
trade-weighted; hour-of-day seasonality was +0.024R but only tested on one
pair with enough hourly samples). The cross-pair lead-lag search found no
relationship above a 0.05 correlation threshold among
AUDUSD/GBPUSD/USDCHF/USDJPY at H4.

**Gap-fill was the exception.** Fading the weekly open gap (short if it
gapped up, long if it gapped down) came out positive **in-sample and
out-of-sample, on all six pairs individually** — pooled +0.143R in-sample /
**+0.20R out-of-sample** across 367 out-of-sample trades. It held up under
a sensitivity check across gap-detection thresholds (1.3&times;&ndash;2.5&times;
typical spacing — all identical, since real weekend gaps are unambiguously
larger than that whole range), holding periods (5/10/15 bars — all
positive, 0.19&ndash;0.22R), and four different train/test split points
(50/50 through 80/20 — all positive, 0.18&ndash;0.24R). That consistency
across pairs, parameters, and splits is what the other ideas above lacked,
and it lines up with a real, structurally sensible cause: FX liquidity is
thin right at the weekend reopen, which is exactly the kind of overreaction
that would partially retrace once normal liquidity resumes.
`output/idea_lab/all_ideas_combined.csv` and `idea_type_summary.csv` have
the full breakdown.

## Stress-testing the gap-fade finding further

A single 70/30 split and a flat 1.5-pip spread aren't enough to actually
trust a result — two follow-up checks, both in `walk_forward_validate.py`:

**1. Rolling (anchored) walk-forward, 5 sequential out-of-sample folds per
pair**, instead of one static split — each fold discovers the rule only on
history up to that point and tests on the next chunk, so the "edge" gets
checked against 5 different, non-overlapping time periods per pair rather
than one:

```bash
python3 -c "
from forex_frequency_lab.data_loader import load_ohlc_csv
from forex_frequency_lab.walk_forward_validate import rolling_walk_forward_gap_fill
df = load_ohlc_csv('data/AUDUSD_H4.csv')
for f in rolling_walk_forward_gap_fill(df, n_folds=5, min_in_sample_frac=0.3, forward_k=10):
    print(f)
"
```

Result: on the four pairs with a full ~5-year history (AUDUSD, GBPUSD,
USDCHF, USDJPY), 19 of 20 folds correctly re-discovered "fill" mode and 16
of 20 (80%) came out with positive average R; pooled trade-weighted average
across all 716 of those folds' trades was **+0.183R**, in line with the
single-split result. On the two pairs with shorter history (EURUSD: 2.5
years; USDCAD: ~1 year), the picture is weaker — EURUSD's discovery flipped
between "fill" and "continuation" across folds (only 2 of 5 landed on
"fill") and came out slightly negative overall (&minus;0.055R), most likely
because a shorter history means too few weekly-gap events per fold to
reliably tell the two modes apart. **The gap-fade edge looks real and
consistent specifically where there's enough history to test it properly;
it is not yet established on the newer/shorter series.**
`output/idea_lab/gap_fill_rolling_walk_forward.csv` has every fold.

**2. Spread stress test** — the earlier result used a flat 1.5-pip
round-trip cost, but real spreads can widen sharply right at the illiquid
Sunday/Monday reopen, which is exactly when this strategy enters:

| Spread (pips) | 1.5 | 3 | 5 | 8 | 12 | 18 | 25 |
|---|---|---|---|---|---|---|---|
| Avg R (367 trades) | +0.201 | +0.165 | +0.118 | +0.046 | &minus;0.049 | &minus;0.192 | &minus;0.358 |

The edge survives realistic widening up to roughly 8 pips and breaks even
somewhere between 8 and 12. **Before trading this, check your broker's
actual spread in the first hour after the Sunday/Monday reopen** — if it
routinely exceeds ~10 pips on the pairs you'd trade, this edge is likely
gone in practice even though it looks solid at typical mid-week spreads.
`output/idea_lab/gap_fill_spread_stress_test.csv` has the full sweep.

**3. Wider reward:risk ratio — tested, doesn't help.** A natural next
question: since each win is capped at 1.5&times; the stop distance, what if
the target were pushed out to 2&times;, 3&times;, or 4&times;? Swept
`reward_risk_ratio` in {1.5, 2, 2.5, 3, 4} crossed with `max_hold_bars` in
{10, 15, 20}, on both the single 70/30 split and the 5-fold rolling
walk-forward:

| reward:risk | 1.5 | 2.0 | 3.0 | 4.0 |
|---|---|---|---|---|
| Avg R (hold=10, 70/30 split) | +0.192 | +0.203 | +0.193 | +0.203 |
| Avg R (hold=10, rolling walk-forward) | +0.183 | &mdash; | +0.169 | &mdash; |

A wider target does **not** meaningfully improve things — win rate drops
almost exactly enough to cancel out the bigger payout per win (e.g. at
3&times;, win rate falls from ~55% to ~53%), so average R stays roughly
flat around +0.19&ndash;0.20R regardless. Extending the holding period to
give a wider target more room to be hit (`max_hold_bars` 15 or 20) actively
*hurts* — average R drops to +0.15&ndash;0.18R because more trades time out
before reaching the farther target. The original 1.5&times; stop / 1.5R
target / 10-bar hold remains the best setting found, and under the more
rigorous rolling walk-forward, 3:1 is very slightly worse (+0.169R vs.
+0.183R), not better. `output/idea_lab/gap_fill_reward_risk_sweep.csv` has
the full grid.

**4. Three more attempts to improve it — none did, and one is an important
warning.** `resample.py` aggregates real H4 bars into real daily bars (no
synthetic data) to test other timeframes; a custom exit variant targets a
fraction of the actual gap size instead of a generic ATR multiple; entry
timing was shifted by 1-2 bars. All results in
`output/idea_lab/gap_fill_refinement_experiments.csv`:

| Experiment | Variant | Avg R (out-of-sample) |
|---|---|---|
| Timeframe | H4 (original) | +0.192 |
| Timeframe | D1 (real resampled daily bars) | +0.065 |
| Target sizing | ATR-based (original) | +0.192 |
| Target sizing | 50% of actual gap size | +0.096 |
| Target sizing | 100% of actual gap size | +0.151 |
| Entry timing | Right at gap-open bar (original) | +0.192 |
| Entry timing | Delayed 1 bar (4h later) | &minus;0.012 |
| Entry timing | Delayed 2 bars (8h later) | &minus;0.034 |

Daily bars capture roughly a third of the edge H4 does — the effect is
sharpest at H4 granularity. Sizing the target to the actual gap (instead of
a generic ATR multiple) raises the win rate a lot (up to ~86%) but lowers
average R, because the reward per win shrinks along with it — net worse.
**Most importantly: delaying entry by even one bar doesn't just weaken the
edge, it erases it entirely.** The whole effect is concentrated in the
first few hours right after the gap opens — which means the earlier
spread-widening risk can't be dodged by waiting for the market to calm
down; the trade has to be taken right at the volatile reopen or not at all,
which is exactly when execution is least certain.

## Validating the pipeline with synthetic data

`forex_frequency_lab/synthetic_data.py` generates a random-walk price series
with a couple of known candle-shape patterns re-inserted at semi-regular
intervals, so you can confirm the pipeline actually recovers a known ground
truth before trusting it on real data. The test suite also builds a series
with a genuine cause-and-effect pattern (a shape that is reliably followed by
a rally) and checks that discovering on one half and backtesting on the other
actually recovers a positive edge — proof the walk-forward harness itself
has no look-ahead bugs, independent of whether real market data has an edge
to find:

```bash
pytest tests/
```

## Notes / next steps

- Candle encoding thresholds (`--atr-period`, body/size buckets, wick
  buckets) control how fine-grained the symbols are — finer buckets find more
  "precise" patterns but fewer of them will repeat over N years of data;
  coarser buckets find more repeats but the patterns are less specific. The
  shadow scheme's alphabet is smaller than the body scheme's (9 symbols vs.
  27 per candle), so it naturally surfaces more — and less specific —
  recurring sequences at the same window size.
- This first version requires an *exact* symbol match per window. A natural
  next step is fuzzy matching (allow 1-symbol tolerance) or shape-distance
  clustering (e.g. DTW / matrix profile) to catch near-identical variants.
- Forward return/win-rate and the reverse-engineered `lift` score are a first
  pass at "is this pattern actually predictive" — both come from small
  sample counts on a handful of years of data, so treat them as hypotheses
  to validate out-of-sample, not signals to trade on directly.
