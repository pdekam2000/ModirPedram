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

## Validating the pipeline with synthetic data

`forex_frequency_lab/synthetic_data.py` generates a random-walk price series
with a couple of known candle-shape patterns re-inserted at semi-regular
intervals, so you can confirm the pipeline actually recovers a known ground
truth before trusting it on real data:

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
