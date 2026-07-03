//+------------------------------------------------------------------+
//|                                                   GapStrike.mq5  |
//|                        Weekend Gap-Fade Expert Advisor for MT5   |
//|                                     Owner: Pedram Kamangar       |
//+------------------------------------------------------------------+
#property copyright "Pedram Kamangar"
#property link      ""
#property version   "1.00"
#property description "GapStrike - fades the weekly forex open gap (short if the "
#property description "week opened higher, long if it opened lower). Backtested "
#property description "walk-forward on AUDUSD, GBPUSD, USDCHF, USDJPY on H4."

#include <Trade\Trade.mqh>

//--- Recommended pairs from the walk-forward research (see forex_frequency_lab repo)
#define RECOMMENDED_SYMBOLS "AUDUSD,GBPUSD,USDCHF,USDJPY"

input group "=== Strategy Settings (from backtest) ==="
input double InpStopATRMultiplier = 1.5;    // Stop-loss = X * ATR(14) at the last pre-gap bar
input double InpRewardRiskRatio   = 1.5;    // Take-profit = X * stop distance
input int    InpMaxHoldBars       = 10;     // Force-close after N bars if neither SL/TP hit
input double InpGapMultiplier     = 1.5;    // Bar gap > X * typical spacing counts as a weekend gap
input int    InpATRPeriod         = 14;     // ATR period

input group "=== Risk Management ==="
input double InpRiskPercent       = 1.0;    // % of account equity risked per trade
input double InpSpreadGuardPips   = 8.0;    // Skip the trade if current spread (pips) exceeds this

input group "=== Safety ==="
input bool   InpWarnOffList       = true;   // Warn (and pause trading) on a non-recommended symbol/timeframe
input ulong  InpMagicNumber       = 20260703; // Unique ID for this EA's orders

input group "=== Dashboard ==="
input bool   InpShowPanel         = true;
input color  InpAccentColor       = clrDeepSkyBlue;
input color  InpPosColor          = clrLime;
input color  InpNegColor          = clrTomato;

CTrade trade;

//--- state
datetime g_lastBarTime      = 0;
ulong    g_activeTicket     = 0;
double   g_activeRiskAmount = 0;     // account-currency risk on the open trade, for R-multiple stats
int      g_atrHandle        = INVALID_HANDLE;

int      g_totalTrades = 0;
int      g_wins        = 0;
int      g_losses      = 0;
double   g_sumR         = 0;
bool     g_symbolOk     = true;

#define PANEL_PREFIX "GapStrike_"

//+------------------------------------------------------------------+
int OnInit()
  {
   g_atrHandle = iATR(_Symbol, _Period, InpATRPeriod);
   if(g_atrHandle == INVALID_HANDLE)
     {
      Print("GapStrike: failed to create ATR handle");
      return(INIT_FAILED);
     }

   g_symbolOk = (_Period == PERIOD_H4) && (StringFind(RECOMMENDED_SYMBOLS, _Symbol) >= 0);
   if(!g_symbolOk && InpWarnOffList)
      Print("GapStrike WARNING: ", _Symbol, " / ", EnumToString(_Period),
            " is not one of the pairs/timeframe this strategy was validated on (",
            RECOMMENDED_SYMBOLS, ", H4). Trading will be paused. Attach to a recommended "
            "symbol on H4, or set InpWarnOffList=false to run anyway at your own risk.");

   trade.SetExpertMagicNumber(InpMagicNumber);

   if(InpShowPanel)
      CreatePanel();

   EventSetTimer(30);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
   DeletePanel();
   if(g_atrHandle != INVALID_HANDLE)
      IndicatorRelease(g_atrHandle);
  }

//+------------------------------------------------------------------+
void OnTimer()
  {
   if(InpShowPanel)
      UpdatePanel();
  }

//+------------------------------------------------------------------+
bool IsNewBar()
  {
   datetime t = iTime(_Symbol, _Period, 0);
   if(t != g_lastBarTime)
     {
      g_lastBarTime = t;
      return(true);
     }
   return(false);
  }

//+------------------------------------------------------------------+
double GetATR(int shift)
  {
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(g_atrHandle, 0, shift, 1, buf) <= 0)
      return(0.0);
   return(buf[0]);
  }

//+------------------------------------------------------------------+
//| One position at a time for this EA - mirrors the backtest's       |
//| "no overlapping trades" assumption.                                |
//+------------------------------------------------------------------+
bool HasOpenPosition()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;
      if(PositionGetInteger(POSITION_MAGIC) == (long)InpMagicNumber && PositionGetString(POSITION_SYMBOL) == _Symbol)
        {
         g_activeTicket = ticket;
         return(true);
        }
     }
   return(false);
  }

//+------------------------------------------------------------------+
//| Close the active position if it has been open for InpMaxHoldBars  |
//| completed bars (a timeout exit, same as the Python backtest).     |
//+------------------------------------------------------------------+
void ManageTimeExit()
  {
   if(!HasOpenPosition())
      return;

   if(!PositionSelectByTicket(g_activeTicket))
      return;

   datetime openTime = (datetime)PositionGetInteger(POSITION_TIME);
   int barsHeld = Bars(_Symbol, _Period, openTime, TimeCurrent()) - 1;
   if(barsHeld >= InpMaxHoldBars)
     {
      trade.PositionClose(g_activeTicket);
      Print("GapStrike: timeout exit after ", barsHeld, " bars on ticket ", g_activeTicket);
     }
  }

//+------------------------------------------------------------------+
//| Detects a weekend/holiday gap between the last two closed bars    |
//| and returns the fade direction (true = long, false = short).      |
//+------------------------------------------------------------------+
bool DetectGap(bool &isLong, double &gapPriceSize)
  {
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, _Period, 0, 3, rates) < 3)
      return(false);

   long typicalSpacing = PeriodSeconds(_Period);
   long actualSpacing   = (long)(rates[0].time - rates[1].time);

   if(actualSpacing <= (long)(typicalSpacing * InpGapMultiplier))
      return(false);

   double gap = rates[0].open - rates[1].close;
   if(gap == 0.0)
      return(false);

   gapPriceSize = gap;
   isLong = (gap < 0);   // gapped down -> fade by going long; gapped up -> fade by going short
   return(true);
  }

//+------------------------------------------------------------------+
double CurrentSpreadPips()
  {
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   int digits   = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double pip   = (digits == 3 || digits == 5) ? point * 10 : point;
   double spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) * point;
   return(spread / pip);
  }

//+------------------------------------------------------------------+
double CalculateLots(double riskAmount, double stopDistance)
  {
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickSize <= 0 || tickValue <= 0)
      return(0.0);

   double lossPerLot = (stopDistance / tickSize) * tickValue;
   if(lossPerLot <= 0)
      return(0.0);

   double lots = riskAmount / lossPerLot;

   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   lots = MathFloor(lots / lotStep) * lotStep;
   lots = MathMax(minLot, MathMin(maxLot, lots));
   return(NormalizeDouble(lots, 2));
  }

//+------------------------------------------------------------------+
void TryOpenGapTrade()
  {
   if(!g_symbolOk)
      return;
   if(HasOpenPosition())
      return;

   bool isLong;
   double gapSize;
   if(!DetectGap(isLong, gapSize))
      return;

   if(CurrentSpreadPips() > InpSpreadGuardPips)
     {
      Print("GapStrike: skipping gap trade, spread too wide (", DoubleToString(CurrentSpreadPips(), 1),
            " pips > ", InpSpreadGuardPips, ")");
      return;
     }

   double atr = GetATR(1); // ATR at the last CLOSED pre-gap bar - no look-ahead
   if(atr <= 0)
      return;

   double stopDistance = InpStopATRMultiplier * atr;
   double targetDistance = stopDistance * InpRewardRiskRatio;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double entry, sl, tp;

   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskAmount = equity * InpRiskPercent / 100.0;
   double lots = CalculateLots(riskAmount, stopDistance);
   if(lots <= 0)
     {
      Print("GapStrike: computed lot size is 0, skipping trade");
      return;
     }

   bool ok;
   if(isLong)
     {
      entry = ask;
      sl = entry - stopDistance;
      tp = entry + targetDistance;
      ok = trade.Buy(lots, _Symbol, entry, sl, tp, "GapStrike fade");
     }
   else
     {
      entry = bid;
      sl = entry + stopDistance;
      tp = entry - targetDistance;
      ok = trade.Sell(lots, _Symbol, entry, sl, tp, "GapStrike fade");
     }

   if(ok)
     {
      g_activeRiskAmount = riskAmount;
      Print("GapStrike: opened ", (isLong ? "LONG" : "SHORT"), " ", DoubleToString(lots, 2),
            " lots on gap of ", DoubleToString(gapSize, _Digits));
     }
   else
      Print("GapStrike: order failed, error ", GetLastError());
  }

//+------------------------------------------------------------------+
//| Picks up the EA's own closed deals to update the win/loss stats.  |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD)
      return;

   if(!HistoryDealSelect(trans.deal))
      return;

   if(HistoryDealGetInteger(trans.deal, DEAL_MAGIC) != (long)InpMagicNumber)
      return;
   if(HistoryDealGetString(trans.deal, DEAL_SYMBOL) != _Symbol)
      return;
   if(HistoryDealGetInteger(trans.deal, DEAL_ENTRY) != DEAL_ENTRY_OUT)
      return;

   double profit = HistoryDealGetDouble(trans.deal, DEAL_PROFIT)
                 + HistoryDealGetDouble(trans.deal, DEAL_SWAP)
                 + HistoryDealGetDouble(trans.deal, DEAL_COMMISSION);

   g_totalTrades++;
   if(profit > 0)
      g_wins++;
   else
      g_losses++;

   if(g_activeRiskAmount > 0)
      g_sumR += profit / g_activeRiskAmount;

   g_activeRiskAmount = 0;

   if(InpShowPanel)
      UpdatePanel();
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   if(IsNewBar())
     {
      ManageTimeExit();
      TryOpenGapTrade();
     }
  }

//+------------------------------------------------------------------+
//| DASHBOARD                                                          |
//| Native chart-object panel: a colored header/logo block plus a     |
//| live stats readout. (MT5 EAs need a compiled .bmp resource for a   |
//| raster image logo - this builds an equivalent look with vector    |
//| chart objects instead, so it works with zero external files.)     |
//+------------------------------------------------------------------+
void MakeRect(string name, int x, int y, int w, int h, color clr, int corner = CORNER_LEFT_UPPER)
  {
   ObjectCreate(0, name, OBJ_RECTANGLE_LABEL, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_CORNER, corner);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, name, OBJPROP_XSIZE, w);
   ObjectSetInteger(0, name, OBJPROP_YSIZE, h);
   ObjectSetInteger(0, name, OBJPROP_BGCOLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_BORDER_TYPE, BORDER_FLAT);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_BACK, false);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
  }

void MakeLabel(string name, int x, int y, string text, color clr, int fontSize, string font = "Segoe UI", int corner = CORNER_LEFT_UPPER)
  {
   ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_CORNER, corner);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, fontSize);
   ObjectSetString(0, name, OBJPROP_FONT, font);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
  }

void CreatePanel()
  {
   int px = 12, py = 12;
   int w  = 250;

   // --- outer card ---
   MakeRect(PANEL_PREFIX+"card", px, py, w, 208, C'18,20,26');
   ObjectSetInteger(0, PANEL_PREFIX+"card", OBJPROP_BORDER_TYPE, BORDER_FLAT);

   // --- colorful logo header strip ---
   MakeRect(PANEL_PREFIX+"logoStrip", px, py, w, 46, clrBlack);
   MakeRect(PANEL_PREFIX+"logoBar1", px, py, 6, 46, clrDeepSkyBlue);
   MakeRect(PANEL_PREFIX+"logoBar2", px+6, py, 6, 46, clrMediumSpringGreen);
   MakeRect(PANEL_PREFIX+"logoBar3", px+12, py, 6, 46, clrGold);
   MakeRect(PANEL_PREFIX+"logoBar4", px+18, py, 6, 46, clrOrangeRed);

   MakeLabel(PANEL_PREFIX+"title", px+34, py+6, "⚡ GapStrike PRO", clrWhite, 15, "Segoe UI Bold");
   MakeLabel(PANEL_PREFIX+"subtitle", px+34, py+27, "Weekend Gap-Fade EA", clrSilver, 8);

   MakeLabel(PANEL_PREFIX+"owner", px+14, py+54, "Owner: Pedram Kamangar", InpAccentColor, 9, "Segoe UI Semibold");
   MakeLabel(PANEL_PREFIX+"symtf", px+14, py+72, _Symbol+"  |  "+EnumToString(_Period), clrLightGray, 9);

   MakeRect(PANEL_PREFIX+"divider", px+14, py+92, w-28, 1, clrGray);

   MakeLabel(PANEL_PREFIX+"statusLbl",  px+14, py+100, "Status:", clrGray, 9);
   MakeLabel(PANEL_PREFIX+"statusVal",  px+90, py+100, "-", clrYellow, 9, "Segoe UI Semibold");

   MakeLabel(PANEL_PREFIX+"tradesLbl",  px+14, py+120, "Total trades:", clrGray, 9);
   MakeLabel(PANEL_PREFIX+"tradesVal",  px+120, py+120, "0", clrWhite, 9, "Segoe UI Semibold");

   MakeLabel(PANEL_PREFIX+"winsLbl",    px+14, py+138, "Wins:", clrGray, 9);
   MakeLabel(PANEL_PREFIX+"winsVal",    px+120, py+138, "0", InpPosColor, 9, "Segoe UI Semibold");

   MakeLabel(PANEL_PREFIX+"lossesLbl",  px+14, py+156, "Losses:", clrGray, 9);
   MakeLabel(PANEL_PREFIX+"lossesVal",  px+120, py+156, "0", InpNegColor, 9, "Segoe UI Semibold");

   MakeLabel(PANEL_PREFIX+"winrateLbl", px+14, py+174, "Win rate:", clrGray, 9);
   MakeLabel(PANEL_PREFIX+"winrateVal", px+120, py+174, "--", clrWhite, 9, "Segoe UI Semibold");

   MakeLabel(PANEL_PREFIX+"avgrLbl", px+14, py+192, "Avg R:", clrGray, 9);
   MakeLabel(PANEL_PREFIX+"avgrVal", px+120, py+192, "--", clrWhite, 9, "Segoe UI Semibold");

   UpdatePanel();
   ChartRedraw();
  }

void UpdatePanel()
  {
   if(ObjectFind(0, PANEL_PREFIX+"card") < 0)
      return;

   string status;
   color statusColor;
   if(!g_symbolOk)
     {
      status = "PAUSED (wrong symbol/TF)";
      statusColor = InpNegColor;
     }
   else if(HasOpenPosition())
     {
      status = "IN TRADE";
      statusColor = clrYellow;
     }
   else
     {
      status = "WATCHING";
      statusColor = InpPosColor;
     }

   ObjectSetString(0, PANEL_PREFIX+"statusVal", OBJPROP_TEXT, status);
   ObjectSetInteger(0, PANEL_PREFIX+"statusVal", OBJPROP_COLOR, statusColor);

   ObjectSetString(0, PANEL_PREFIX+"tradesVal", OBJPROP_TEXT, IntegerToString(g_totalTrades));
   ObjectSetString(0, PANEL_PREFIX+"winsVal", OBJPROP_TEXT, IntegerToString(g_wins));
   ObjectSetString(0, PANEL_PREFIX+"lossesVal", OBJPROP_TEXT, IntegerToString(g_losses));

   string wr = (g_totalTrades > 0) ? DoubleToString(100.0 * g_wins / g_totalTrades, 1) + "%" : "--";
   ObjectSetString(0, PANEL_PREFIX+"winrateVal", OBJPROP_TEXT, wr);

   string avgR = (g_totalTrades > 0) ? DoubleToString(g_sumR / g_totalTrades, 2) + "R" : "--";
   color avgRColor = (g_totalTrades > 0 && g_sumR >= 0) ? InpPosColor : InpNegColor;
   ObjectSetString(0, PANEL_PREFIX+"avgrVal", OBJPROP_TEXT, avgR);
   ObjectSetInteger(0, PANEL_PREFIX+"avgrVal", OBJPROP_COLOR, (g_totalTrades > 0) ? avgRColor : clrWhite);

   ChartRedraw();
  }

void DeletePanel()
  {
   ObjectsDeleteAll(0, PANEL_PREFIX);
   ChartRedraw();
  }
//+------------------------------------------------------------------+
