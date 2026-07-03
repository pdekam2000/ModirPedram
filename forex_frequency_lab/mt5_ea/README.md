# GapStrike PRO — MT5 Expert Advisor

Owner: **Pedram Kamangar**

Live implementation of the weekend gap-fade strategy researched in
`forex_frequency_lab/`: short if the week's open gapped up, long if it
gapped down, with an ATR-based stop/target and a colored on-chart dashboard
showing trade count, wins, losses, win rate, and average R.

## ⚠️ Before you use this

- **This file has not been compiled or run in MetaEditor/MT5** — there's no
  MT5 installation in the environment this was written in. Compile it in
  MetaEditor first and fix any errors it flags before using it anywhere
  real.
- **Test on a demo account first**, ideally for at least a few weeks, so
  you see real gap events fire before risking money.
- The backtest this is based on found the edge only on **AUDUSD, GBPUSD,
  USDCHF, USDJPY, on H4** — with enough history to test properly. The EA
  warns (and pauses trading) if attached to a different symbol or
  timeframe; don't turn that check off without understanding why.
- The backtest also found the edge **disappears if the real spread exceeds
  roughly 8 pips**, and **evaporates entirely if entry is delayed even one
  bar** — both concentrated risks around the volatile Sunday/Monday
  reopen, which `InpSpreadGuardPips` only partially protects against (it
  skips the trade if the spread is already too wide at the moment of
  detection, but can't fix a bad fill on a wide-spread broker in general).
- Default risk is 1% of equity per trade. Raising it changes the growth
  curve non-linearly — see the R-multiple/drawdown analysis in the main
  README before touching `InpRiskPercent`.

## Installation

1. Copy `GapStrike.mq5` into your MT5 `MQL5/Experts/` folder (in MT5:
   File → Open Data Folder → `MQL5/Experts/`).
2. Open it in MetaEditor and compile (F7). Fix any compiler messages —
   MetaTrader builds/broker setups can vary slightly.
3. In MT5, open a chart for one of the recommended pairs and set the
   timeframe to **H4**.
4. Drag `GapStrike` from the Navigator onto the chart.
5. On the Common tab, make sure **Algo Trading** is allowed for this EA
   and for the terminal (top toolbar).
6. Since one EA instance trades one chart's symbol, attach it separately
   to AUDUSD H4, GBPUSD H4, USDCHF H4, and USDJPY H4 if you want all four.

## Inputs

| Input | Default | What it does |
|---|---|---|
| `InpStopATRMultiplier` | 1.5 | Stop-loss distance = X × ATR(14) at the last pre-gap bar |
| `InpRewardRiskRatio` | 1.5 | Take-profit distance = X × stop distance |
| `InpMaxHoldBars` | 10 | Force-close if neither SL/TP hit after N H4 bars |
| `InpGapMultiplier` | 1.5 | A bar gap bigger than X × the timeframe's normal spacing counts as a weekend/holiday gap |
| `InpATRPeriod` | 14 | ATR lookback |
| `InpRiskPercent` | 1.0 | % of account equity risked per trade |
| `InpSpreadGuardPips` | 8.0 | Skip the trade if the spread is already wider than this when the gap is detected |
| `InpWarnOffList` | true | Pause trading (with a log warning) off the researched symbols/H4 |
| `InpMagicNumber` | 20260703 | Order tag, change if you run other EAs too |
| `InpShowPanel` | true | Show/hide the on-chart dashboard |
| `InpAccentColor` / `InpPosColor` / `InpNegColor` | blue / green / red | Dashboard colors |

## The dashboard

A small always-on-top panel in the chart's top-left corner: a colorful
striped header (the "logo" — MT5 EAs need a compiled `.bmp` resource file
for a raster image, so this is a native vector look built from chart
objects instead, no external files needed), owner name, symbol/timeframe,
live status (WATCHING / IN TRADE / PAUSED), and running totals for trades,
wins, losses, win rate, and average R since the EA was attached.

## What it does under the hood

On every new H4 bar: if there's no open GapStrike position, it checks
whether the gap between this bar's open and the previous bar's close is
bigger than `InpGapMultiplier` × the normal 4-hour spacing (i.e. a weekend
or holiday gap). If so, it fades it — short if price gapped up, long if it
gapped down — sized so the stop-loss risks exactly `InpRiskPercent` of
equity, with the take-profit and max holding period from the backtest. If
the position is still open after `InpMaxHoldBars` bars, it's closed at
market (a timeout exit, matching the Python backtest exactly).
