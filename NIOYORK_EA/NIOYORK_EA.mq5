//+------------------------------------------------------------------+
//|                                                    NIOYORK_EA.mq5 |
//|                     Owner : Pedram Kamangar                       |
//|      Strategy : One Candle / New York Opening Range Scalper       |
//+------------------------------------------------------------------+
#property copyright "Pedram Kamangar"
#property link      ""
#property version   "1.00"
#property description "NIOYORK EA - New York Opening Range liquidity-reversal scalper"

#include <Trade\Trade.mqh>

//======================================================================
// ENUMERATIONS
//======================================================================
enum ENUM_ENTRY_MODE
  {
   MARKET_CLOSE = 0,      // Enter at market on reversal candle close
   BREAK_CONFIRMATION = 1 // Enter on break of reversal candle high/low
  };

enum ENUM_TP_MODE
  {
   FIXED_RR = 0,               // Fixed Reward:Risk target
   OPPOSITE_OPENING_RANGE = 1, // Target opposite side of Opening Range
   PARTIALS = 2                // Scale out at 1R / 2R / 3R
  };

enum ENUM_SESSION_STATE
  {
   STATE_WAITING_NY_OPEN,
   STATE_BUILDING_RANGE,
   STATE_WAITING_LIQUIDITY,
   STATE_WAITING_REVERSAL,
   STATE_TRADE_ACTIVE,
   STATE_EXPIRED
  };

//======================================================================
// INPUTS - REQUIRED
//======================================================================
input string            Owner_Name               = "Pedram Kamangar";
input string             Robot_Name               = "NIOYORK EA";
input double             Risk_Per_Trade_Percent   = 1.0;
input double             Reward_Risk_Ratio        = 3.0;
input int                Max_Trades_Per_Day       = 1;
input int                ATR_Period               = 14;
input double             Min_ATR_Percent          = 25.0;
input ENUM_TIMEFRAMES    Main_Timeframe           = PERIOD_M15;
input ENUM_TIMEFRAMES    Entry_Timeframe          = PERIOD_M5;
input bool               Use_FVG_Filter           = true;
input bool               Use_Partial_TP           = true;
input bool               Move_BE_After_TP1        = true;
input int                SL_Buffer_Points         = 50;
input int                Max_Spread_Points        = 30;
input int                Magic_Number             = 93015;
input bool               Use_News_Filter          = false;
input int                News_Block_Minutes_Before= 30;
input int                News_Block_Minutes_After = 30;
input int                NY_Open_Hour             = 9;
input int                NY_Open_Minute           = 30;
input int                Broker_Time_Offset_From_NY = 0;
input int                Setup_Expiry_Minutes     = 90;
input bool               Enable_Auto_Trading      = true;

//======================================================================
// INPUTS - ADDITIONAL SETTINGS
//======================================================================
input group "Entry / Exit Behaviour"
input ENUM_ENTRY_MODE    Entry_Mode               = MARKET_CLOSE;
input ENUM_TP_MODE       TP_Mode                  = FIXED_RR;
input double             Max_Daily_Loss_Percent   = 5.0;
input int                Opening_Range_Minutes    = 15;

input group "Candle Pattern Tolerances"
input double             Hammer_Wick_Body_Ratio       = 2.0;
input double             Hammer_Opposite_Wick_MaxRatio= 1.0;

input group "Dashboard Colors"
input color              Color_RobotName   = clrGold;
input color              Color_Active      = clrLime;
input color              Color_Off         = clrRed;
input color              Color_OpeningRange= clrAqua;
input color              Color_FVG         = clrMagenta;

//======================================================================
// STRUCTS
//======================================================================
struct OpeningRangeInfo
  {
   double   high;
   double   low;
   datetime candleTime;
   bool     valid;
  };

struct LiquidityCandleInfo
  {
   double   high;
   double   low;
   double   open;
   double   close;
   datetime time;
   bool     isBullishBreak; // true = broke above range (expect SHORT)
   bool     valid;
  };

struct FVGZoneInfo
  {
   double   top;
   double   bottom;
   bool     isBullish;
   bool     valid;
   datetime time;
  };

struct ActiveTradeInfo
  {
   ulong    ticket;
   double   entryPrice;
   double   slPrice;
   double   rDistance;
   bool     isLong;
   double   initialVolume;
   bool     tp1Done;
   bool     tp2Done;
   bool     beMoved;
   bool     active;
  };

//======================================================================
// GLOBALS
//======================================================================
#define OBJ_PREFIX "NIOYORK_"

CTrade               trade;
int                  g_DailyATR_Handle = INVALID_HANDLE;

ENUM_SESSION_STATE   g_State = STATE_WAITING_NY_OPEN;

datetime             g_CurrentDayStart = 0;
datetime             g_NYOpenTime      = 0;
datetime             g_RangeCloseTime  = 0;
datetime             g_ExpiryTime      = 0;

OpeningRangeInfo     g_OR;
LiquidityCandleInfo  g_Liquidity;
FVGZoneInfo          g_FVG;
ActiveTradeInfo      g_ActiveTrade;

datetime             g_LastMainBarTime  = 0;
datetime             g_LastEntryBarTime = 0;

int                  g_TradesToday        = 0;
double               g_DailyStartBalance  = 0;

int                  g_ClosedDeals   = 0;
int                  g_WinningDeals  = 0;
double               g_TotalProfit   = 0;

bool                 g_PendingBreakActive = false;
bool                 g_PendingIsLong      = false;
double               g_PendingTrigger     = 0;
double               g_PendingSL          = 0;

//======================================================================
// INIT / DEINIT
//======================================================================
int OnInit()
  {
   trade.SetExpertMagicNumber(Magic_Number);
   trade.SetDeviationInPoints(10);
   trade.SetTypeFillingBySymbol(_Symbol);

   g_DailyATR_Handle = iATR(_Symbol, PERIOD_D1, ATR_Period);
   if(g_DailyATR_Handle == INVALID_HANDLE)
     {
      Print(Robot_Name+": Failed to create Daily ATR handle. Error=", GetLastError());
      return(INIT_FAILED);
     }

   g_State             = STATE_WAITING_NY_OPEN;
   g_CurrentDayStart    = 0;
   g_DailyStartBalance  = AccountInfoDouble(ACCOUNT_BALANCE);

   EventSetTimer(1);

   Print(Robot_Name+" initialized. Owner: "+Owner_Name);
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   if(g_DailyATR_Handle != INVALID_HANDLE)
      IndicatorRelease(g_DailyATR_Handle);
   ObjectsDeleteAll(0, OBJ_PREFIX);
  }

//======================================================================
// MAIN TICK / TIMER
//======================================================================
void OnTick()
  {
   ResetDailyStateIfNewDay();
   UpdateSessionStateMachine();
   ManageOpenTrade();
   UpdateDashboard();
  }

void OnTimer()
  {
   UpdateDashboard();
  }

void OnTradeTransaction(const MqlTradeTransaction &trans,
                         const MqlTradeRequest &request,
                         const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD)
      return;

   ulong dealTicket = trans.deal;
   if(!HistoryDealSelect(dealTicket))
      return;
   if(HistoryDealGetInteger(dealTicket, DEAL_MAGIC) != Magic_Number)
      return;

   long entryType = HistoryDealGetInteger(dealTicket, DEAL_ENTRY);
   if(entryType != DEAL_ENTRY_OUT && entryType != DEAL_ENTRY_OUT_BY)
      return;

   double profit = HistoryDealGetDouble(dealTicket, DEAL_PROFIT)
                  + HistoryDealGetDouble(dealTicket, DEAL_SWAP)
                  + HistoryDealGetDouble(dealTicket, DEAL_COMMISSION);

   g_TotalProfit += profit;
   g_ClosedDeals++;
   if(profit > 0)
      g_WinningDeals++;
  }

//======================================================================
// DAILY RESET
//======================================================================
void ResetDailyStateIfNewDay()
  {
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   datetime dayStart = StructToTime(dt);

   if(dayStart == g_CurrentDayStart)
      return;

   g_CurrentDayStart   = dayStart;
   g_TradesToday       = 0;
   g_DailyStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);

   g_OR.valid              = false;
   g_Liquidity.valid       = false;
   g_FVG.valid             = false;
   g_PendingBreakActive    = false;
   g_ActiveTrade.active    = false;
   g_LastMainBarTime       = 0;
   g_LastEntryBarTime      = 0;
   g_State                 = STATE_WAITING_NY_OPEN;

   g_NYOpenTime     = dayStart + (NY_Open_Hour + Broker_Time_Offset_From_NY) * 3600 + NY_Open_Minute * 60;
   g_RangeCloseTime = g_NYOpenTime + Opening_Range_Minutes * 60;
   g_ExpiryTime     = g_NYOpenTime + Setup_Expiry_Minutes * 60;

   ObjectsDeleteAll(0, OBJ_PREFIX);

   Print(Robot_Name+": New trading day detected. State reset. NY Open (broker time)=", TimeToString(g_NYOpenTime));
  }

//======================================================================
// SESSION STATE MACHINE
//======================================================================
void UpdateSessionStateMachine()
  {
   datetime now = TimeCurrent();

   if(g_State == STATE_TRADE_ACTIVE)
     {
      if(!HasOpenPosition())
        {
         if(g_TradesToday < Max_Trades_Per_Day && now < g_ExpiryTime && !DailyLossLimitHit())
           {
            g_State           = STATE_WAITING_LIQUIDITY;
            g_Liquidity.valid  = false;
            g_FVG.valid        = false;
            g_PendingBreakActive = false;
           }
         else
            g_State = STATE_EXPIRED;
        }
      return;
     }

   if(g_State == STATE_EXPIRED)
      return;

   if(now < g_NYOpenTime)
     {
      g_State = STATE_WAITING_NY_OPEN;
      return;
     }

   if(now < g_RangeCloseTime)
     {
      g_State = STATE_BUILDING_RANGE;
      return;
     }

   if(!g_OR.valid)
     {
      CaptureOpeningRange();
      if(g_OR.valid)
        {
         DrawOpeningRangeBox();
         g_State = STATE_WAITING_LIQUIDITY;
        }
      return;
     }

   if(now >= g_ExpiryTime)
     {
      if(g_State != STATE_EXPIRED)
        {
         DrawExpiryLine();
         Print(Robot_Name+": Setup expired for today.");
        }
      g_State = STATE_EXPIRED;
      return;
     }

   if(g_TradesToday >= Max_Trades_Per_Day || DailyLossLimitHit())
     {
      g_State = STATE_EXPIRED;
      return;
     }

   if(g_State == STATE_WAITING_LIQUIDITY)
      CheckLiquidityBreakout();
   else if(g_State == STATE_WAITING_REVERSAL)
      CheckReversalAndEnter();
  }

//======================================================================
// OPENING RANGE
//======================================================================
void CaptureOpeningRange()
  {
   int shift = iBarShift(_Symbol, Main_Timeframe, g_NYOpenTime, false);
   if(shift < 0)
      return;

   datetime barTime      = iTime(_Symbol, Main_Timeframe, shift);
   datetime barCloseTime = barTime + PeriodSeconds(Main_Timeframe);
   if(barCloseTime > TimeCurrent())
      return; // candle not fully closed yet

   g_OR.high       = iHigh(_Symbol, Main_Timeframe, shift);
   g_OR.low        = iLow(_Symbol, Main_Timeframe, shift);
   g_OR.candleTime = barTime;
   g_OR.valid      = true;

   Print(Robot_Name+": Opening Range captured. High=", g_OR.high, " Low=", g_OR.low);
  }

//======================================================================
// LIQUIDITY / MANIPULATION CANDLE
//======================================================================
void CheckLiquidityBreakout()
  {
   if(!IsNewBar(Main_Timeframe, g_LastMainBarTime))
      return;

   int shift = 1;
   datetime barTime = iTime(_Symbol, Main_Timeframe, shift);
   if(barTime <= g_OR.candleTime)
      return;

   double h = iHigh(_Symbol, Main_Timeframe, shift);
   double l = iLow(_Symbol, Main_Timeframe, shift);
   double c = iClose(_Symbol, Main_Timeframe, shift);
   double range = h - l;

   double dailyATR = GetDailyATR();
   if(dailyATR <= 0)
      return;

   double minRange = dailyATR * (Min_ATR_Percent / 100.0);
   if(range < minRange)
     {
      Print(Robot_Name+": Breakout candle range too small vs Daily ATR. Ignored.");
      return;
     }

   bool brokeAbove = c > g_OR.high;
   bool brokeBelow = c < g_OR.low;
   if(!brokeAbove && !brokeBelow)
      return;

   g_Liquidity.high           = h;
   g_Liquidity.low            = l;
   g_Liquidity.open           = iOpen(_Symbol, Main_Timeframe, shift);
   g_Liquidity.close          = c;
   g_Liquidity.time           = barTime;
   g_Liquidity.isBullishBreak = brokeAbove;
   g_Liquidity.valid          = true;

   DrawLiquidityMarker();

   g_State            = STATE_WAITING_REVERSAL;
   g_LastEntryBarTime = 0;

   Print(Robot_Name+": Liquidity candle detected. Direction=", (brokeAbove ? "Bullish break -> expect SHORT" : "Bearish break -> expect LONG"));
  }

//======================================================================
// REVERSAL DETECTION / ENTRY
//======================================================================
void CheckReversalAndEnter()
  {
   if(g_PendingBreakActive)
     {
      CheckPendingBreakTrigger();
      return;
     }

   if(!IsNewBar(Entry_Timeframe, g_LastEntryBarTime))
      return;

   int shift = 1;
   datetime barTime = iTime(_Symbol, Entry_Timeframe, shift);
   datetime liqCloseTime = g_Liquidity.time + PeriodSeconds(Main_Timeframe);
   if(barTime < liqCloseTime)
      return;

   bool expectShort = g_Liquidity.isBullishBreak;
   bool expectLong  = !g_Liquidity.isBullishBreak;

   double o  = iOpen(_Symbol, Entry_Timeframe, shift);
   double h  = iHigh(_Symbol, Entry_Timeframe, shift);
   double l  = iLow(_Symbol, Entry_Timeframe, shift);
   double c  = iClose(_Symbol, Entry_Timeframe, shift);
   double po = iOpen(_Symbol, Entry_Timeframe, shift + 1);
   double pc = iClose(_Symbol, Entry_Timeframe, shift + 1);

   bool patternFound = false;
   bool isLongSignal = false;

   if(expectLong)
     {
      if(IsHammer(o, h, l, c, shift) || IsBullishEngulfing(o, c, po, pc))
        {
         patternFound = true;
         isLongSignal = true;
        }
     }
   else if(expectShort)
     {
      if(IsInvertedHammer(o, h, l, c, shift) || IsBearishEngulfing(o, c, po, pc))
        {
         patternFound = true;
         isLongSignal = false;
        }
     }

   if(!patternFound)
      return;

   if(Use_FVG_Filter && !CheckFVGRetest(isLongSignal, shift))
     {
      Print(Robot_Name+": Reversal candle found but FVG/OR retest condition not met yet. Waiting.");
      return;
     }

   double slPrice, entryTriggerPrice;
   if(isLongSignal)
     {
      slPrice           = l - SL_Buffer_Points * _Point;
      entryTriggerPrice = h;
     }
   else
     {
      slPrice           = h + SL_Buffer_Points * _Point;
      entryTriggerPrice = l;
     }

   if(Entry_Mode == MARKET_CLOSE)
     {
      ExecuteEntry(isLongSignal, slPrice);
     }
   else
     {
      g_PendingBreakActive = true;
      g_PendingIsLong       = isLongSignal;
      g_PendingTrigger      = entryTriggerPrice;
      g_PendingSL           = slPrice;
      Print(Robot_Name+": Waiting for break confirmation at ", entryTriggerPrice);
     }
  }

void CheckPendingBreakTrigger()
  {
   if(TimeCurrent() >= g_ExpiryTime)
     {
      g_PendingBreakActive = false;
      return;
     }

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   bool triggered = false;
   if(g_PendingIsLong && ask > g_PendingTrigger)
      triggered = true;
   if(!g_PendingIsLong && bid < g_PendingTrigger)
      triggered = true;

   if(triggered)
     {
      ExecuteEntry(g_PendingIsLong, g_PendingSL);
      g_PendingBreakActive = false;
     }
  }

//======================================================================
// CANDLE PATTERNS
//======================================================================
bool IsPriorBearishMove(int shift)
  {
   double c1 = iClose(_Symbol, Entry_Timeframe, shift + 3);
   double c2 = iClose(_Symbol, Entry_Timeframe, shift + 1);
   return(c2 < c1);
  }

bool IsPriorBullishMove(int shift)
  {
   double c1 = iClose(_Symbol, Entry_Timeframe, shift + 3);
   double c2 = iClose(_Symbol, Entry_Timeframe, shift + 1);
   return(c2 > c1);
  }

bool IsHammer(double o, double h, double l, double c, int shift)
  {
   double body = MathAbs(c - o);
   if(body <= 0)
      body = _Point;

   double lowerWick = MathMin(o, c) - l;
   double upperWick = h - MathMax(o, c);

   if(lowerWick < body * Hammer_Wick_Body_Ratio)
      return(false);
   if(upperWick > body * Hammer_Opposite_Wick_MaxRatio)
      return(false);
   if(!IsPriorBearishMove(shift))
      return(false);

   return(true);
  }

bool IsInvertedHammer(double o, double h, double l, double c, int shift)
  {
   double body = MathAbs(c - o);
   if(body <= 0)
      body = _Point;

   double upperWick = h - MathMax(o, c);
   double lowerWick = MathMin(o, c) - l;

   if(upperWick < body * Hammer_Wick_Body_Ratio)
      return(false);
   if(lowerWick > body * Hammer_Opposite_Wick_MaxRatio)
      return(false);
   if(!IsPriorBullishMove(shift))
      return(false);

   return(true);
  }

bool IsBullishEngulfing(double o, double c, double po, double pc)
  {
   bool curBull  = c > o;
   bool prevBear = pc < po;
   if(!curBull || !prevBear)
      return(false);
   return(o <= pc && c >= po);
  }

bool IsBearishEngulfing(double o, double c, double po, double pc)
  {
   bool curBear  = c < o;
   bool prevBull = pc > po;
   if(!curBear || !prevBull)
      return(false);
   return(o >= pc && c <= po);
  }

//======================================================================
// FAIR VALUE GAP
//======================================================================
bool CheckFVGRetest(bool isLong, int shift)
  {
   for(int i = shift; i <= shift + 4; i++)
     {
      double h1 = iHigh(_Symbol, Entry_Timeframe, i + 2);
      double l1 = iLow(_Symbol, Entry_Timeframe, i + 2);
      double h3 = iHigh(_Symbol, Entry_Timeframe, i);
      double l3 = iLow(_Symbol, Entry_Timeframe, i);

      if(isLong)
        {
         if(h1 < l3)
           {
            g_FVG.top      = l3;
            g_FVG.bottom   = h1;
            g_FVG.isBullish= true;
            g_FVG.valid    = true;
            g_FVG.time     = iTime(_Symbol, Entry_Timeframe, i);
            DrawFVGZone();

            double curLow = iLow(_Symbol, Entry_Timeframe, shift);
            bool retestFVG = (curLow <= g_FVG.top && curLow >= g_FVG.bottom);
            bool retestOR  = (curLow <= g_OR.low);
            if(retestFVG || retestOR)
               return(true);
           }
        }
      else
        {
         if(l1 > h3)
           {
            g_FVG.top      = l1;
            g_FVG.bottom   = h3;
            g_FVG.isBullish= false;
            g_FVG.valid    = true;
            g_FVG.time     = iTime(_Symbol, Entry_Timeframe, i);
            DrawFVGZone();

            double curHigh = iHigh(_Symbol, Entry_Timeframe, shift);
            bool retestFVG = (curHigh >= g_FVG.bottom && curHigh <= g_FVG.top);
            bool retestOR  = (curHigh >= g_OR.high);
            if(retestFVG || retestOR)
               return(true);
           }
        }
     }
   return(false);
  }

//======================================================================
// ORDER EXECUTION
//======================================================================
void ExecuteEntry(bool isLong, double slPrice)
  {
   if(!Enable_Auto_Trading)
     {
      Print(Robot_Name+": Auto trading disabled. Signal skipped.");
      return;
     }
   if(HasOpenPosition())
      return;
   if(g_TradesToday >= Max_Trades_Per_Day)
      return;
   if(DailyLossLimitHit())
     {
      g_State = STATE_EXPIRED;
      return;
     }
   if(!SpreadOK())
     {
      Print(Robot_Name+": Spread too high, entry skipped.");
      return;
     }
   if(Use_News_Filter && IsHighImpactNewsTime())
     {
      Print(Robot_Name+": Inside news blackout window, entry skipped.");
      return;
     }

   double price = isLong ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double slDistance = MathAbs(price - slPrice);
   if(slDistance <= 0)
     {
      Print(Robot_Name+": Invalid SL distance, entry skipped.");
      return;
     }

   double lot = CalcLotSize(slDistance);
   if(lot <= 0)
     {
      Print(Robot_Name+": Lot size calculation failed, entry skipped.");
      return;
     }
   if(!MarginOK(isLong, lot, price))
     {
      Print(Robot_Name+": Insufficient free margin, entry skipped.");
      return;
     }

   double rDistance = slDistance;
   double tp;
   if(TP_Mode == OPPOSITE_OPENING_RANGE)
      tp = isLong ? g_OR.high : g_OR.low;
   else
      tp = isLong ? price + rDistance * Reward_Risk_Ratio : price - rDistance * Reward_Risk_Ratio;

   slPrice = NormalizeDouble(slPrice, _Digits);
   tp      = NormalizeDouble(tp, _Digits);

   bool ok;
   if(isLong)
      ok = trade.Buy(lot, _Symbol, 0, slPrice, tp, Robot_Name);
   else
      ok = trade.Sell(lot, _Symbol, 0, slPrice, tp, Robot_Name);

   if(ok)
     {
      g_TradesToday++;
      g_State = STATE_TRADE_ACTIVE;

      g_ActiveTrade.ticket        = trade.ResultOrder();
      g_ActiveTrade.entryPrice    = price;
      g_ActiveTrade.slPrice       = slPrice;
      g_ActiveTrade.rDistance     = rDistance;
      g_ActiveTrade.isLong        = isLong;
      g_ActiveTrade.initialVolume = lot;
      g_ActiveTrade.tp1Done       = false;
      g_ActiveTrade.tp2Done       = false;
      g_ActiveTrade.beMoved       = false;
      g_ActiveTrade.active        = true;

      DrawEntryArrow(isLong, price);
      DrawSLTPLines(price, slPrice, rDistance, isLong);

      Print(Robot_Name+": Entry executed. Long=", isLong, " Lot=", lot, " Entry=", price, " SL=", slPrice, " TP=", tp);
     }
   else
     {
      Print(Robot_Name+": Order failed. Error=", GetLastError(), " Retcode=", trade.ResultRetcode());
     }
  }

//======================================================================
// TRADE MANAGEMENT (Partial TP / Breakeven)
//======================================================================
void ManageOpenTrade()
  {
   if(!g_ActiveTrade.active)
      return;

   if(!PositionSelect(_Symbol))
     {
      g_ActiveTrade.active = false;
      return;
     }
   if(PositionGetInteger(POSITION_MAGIC) != Magic_Number)
      return;

   if(!Use_Partial_TP)
      return;

   double price  = g_ActiveTrade.isLong ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double r      = g_ActiveTrade.rDistance;
   double entry  = g_ActiveTrade.entryPrice;
   double tp1    = g_ActiveTrade.isLong ? entry + r : entry - r;
   double tp2    = g_ActiveTrade.isLong ? entry + 2 * r : entry - 2 * r;

   if(!g_ActiveTrade.tp1Done)
     {
      bool hit = g_ActiveTrade.isLong ? (price >= tp1) : (price <= tp1);
      if(hit)
        {
         double curVolume = PositionGetDouble(POSITION_VOLUME);
         double closeVol  = NormalizeVolume(g_ActiveTrade.initialVolume * 0.33);
         closeVol = MathMin(closeVol, curVolume);
         if(closeVol >= SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN) && closeVol < curVolume)
           {
            trade.PositionClosePartial(_Symbol, closeVol);
            Print(Robot_Name+": TP1 (1R) hit, closed 33% of position.");
           }
         g_ActiveTrade.tp1Done = true;

         if(Move_BE_After_TP1 && !g_ActiveTrade.beMoved && PositionSelect(_Symbol))
           {
            trade.PositionModify(_Symbol, entry, PositionGetDouble(POSITION_TP));
            g_ActiveTrade.beMoved = true;
            Print(Robot_Name+": Stop Loss moved to breakeven.");
           }
        }
      return;
     }

   if(!g_ActiveTrade.tp2Done)
     {
      bool hit = g_ActiveTrade.isLong ? (price >= tp2) : (price <= tp2);
      if(hit)
        {
         double curVolume = PositionGetDouble(POSITION_VOLUME);
         double closeVol  = NormalizeVolume(g_ActiveTrade.initialVolume * 0.33);
         closeVol = MathMin(closeVol, curVolume);
         if(closeVol >= SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN) && closeVol < curVolume)
           {
            trade.PositionClosePartial(_Symbol, closeVol);
            Print(Robot_Name+": TP2 (2R) hit, closed additional 33% of position.");
           }
         g_ActiveTrade.tp2Done = true;
        }
      return;
     }
   // Remaining volume runs to the original 3R TP order already attached at entry.
  }

//======================================================================
// RISK / SAFETY HELPERS
//======================================================================
bool HasOpenPosition()
  {
   if(PositionSelect(_Symbol))
     {
      if(PositionGetInteger(POSITION_MAGIC) == Magic_Number)
         return(true);
     }
   return(false);
  }

double CalcLotSize(double slDistance)
  {
   double balance    = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskAmount = balance * (Risk_Per_Trade_Percent / 100.0);

   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickSize <= 0 || tickValue <= 0)
      return(0);

   double lossPerLot = (slDistance / tickSize) * tickValue;
   if(lossPerLot <= 0)
      return(0);

   double lot = riskAmount / lossPerLot;
   return(NormalizeVolume(lot));
  }

double NormalizeVolume(double vol)
  {
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(step <= 0)
      step = 0.01;

   vol = MathFloor(vol / step) * step;
   if(vol < minLot)
      vol = minLot;
   if(vol > maxLot)
      vol = maxLot;

   return(NormalizeDouble(vol, 2));
  }

bool MarginOK(bool isLong, double lot, double price)
  {
   double marginRequired = 0;
   ENUM_ORDER_TYPE type = isLong ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   if(!OrderCalcMargin(type, _Symbol, lot, price, marginRequired))
      return(false);
   double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   return(freeMargin >= marginRequired);
  }

bool SpreadOK()
  {
   long spreadPoints = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   return(spreadPoints <= Max_Spread_Points);
  }

bool DailyLossLimitHit()
  {
   if(Max_Daily_Loss_Percent <= 0 || g_DailyStartBalance <= 0)
      return(false);
   double currentEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   double lossPercent = (g_DailyStartBalance - currentEquity) / g_DailyStartBalance * 100.0;
   return(lossPercent >= Max_Daily_Loss_Percent);
  }

double GetDailyATR()
  {
   double buf[];
   ArraySetAsSeries(buf, true);
   if(CopyBuffer(g_DailyATR_Handle, 0, 1, 1, buf) <= 0)
      return(-1);
   return(buf[0]);
  }

//======================================================================
// NEWS FILTER (structured for future economic calendar integration)
//======================================================================
bool IsHighImpactNewsTime()
  {
   if(!Use_News_Filter)
      return(false);

   MqlCalendarValue values[];
   datetime from = TimeCurrent() - News_Block_Minutes_Before * 60;
   datetime to   = TimeCurrent() + News_Block_Minutes_After * 60;

   int count = CalendarValueHistory(values, from, to, NULL, NULL);
   if(count <= 0)
      return(false);

   string baseCcy   = SymbolInfoString(_Symbol, SYMBOL_CURRENCY_BASE);
   string profitCcy = SymbolInfoString(_Symbol, SYMBOL_CURRENCY_PROFIT);

   for(int i = 0; i < count; i++)
     {
      MqlCalendarEvent event;
      if(!CalendarEventById(values[i].event_id, event))
         continue;
      if(event.importance != CALENDAR_IMPORTANCE_HIGH)
         continue;

      MqlCalendarCountry country;
      if(!CalendarCountryById(event.country_id, country))
         continue;

      if(country.currency == baseCcy || country.currency == profitCcy)
         return(true);
     }
   return(false);
  }

//======================================================================
// GENERIC HELPERS
//======================================================================
bool IsNewBar(ENUM_TIMEFRAMES tf, datetime &lastBarTime)
  {
   datetime t = iTime(_Symbol, tf, 0);
   if(t != lastBarTime)
     {
      lastBarTime = t;
      return(true);
     }
   return(false);
  }

string StateToString(ENUM_SESSION_STATE s)
  {
   switch(s)
     {
      case STATE_WAITING_NY_OPEN:    return("Waiting for NY Open");
      case STATE_BUILDING_RANGE:     return("Building Opening Range");
      case STATE_WAITING_LIQUIDITY:  return("Waiting for Liquidity Candle");
      case STATE_WAITING_REVERSAL:   return("Waiting for Reversal Entry");
      case STATE_TRADE_ACTIVE:       return("Trade Active");
      case STATE_EXPIRED:            return("Session Expired");
     }
   return("Unknown");
  }

//======================================================================
// CHART OBJECT DRAWING
//======================================================================
void CreateHLine(string name, datetime t1, datetime t2, double price, color clr)
  {
   ObjectDelete(0, name);
   ObjectCreate(0, name, OBJ_TREND, 0, t1, price, t2, price);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DASH);
   ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, name, OBJPROP_BACK, true);
  }

void DrawOpeningRangeBox()
  {
   string name = OBJ_PREFIX + "ORBox";
   ObjectDelete(0, name);
   ObjectCreate(0, name, OBJ_RECTANGLE, 0, g_OR.candleTime, g_OR.high, g_ExpiryTime, g_OR.low);
   ObjectSetInteger(0, name, OBJPROP_COLOR, Color_OpeningRange);
   ObjectSetInteger(0, name, OBJPROP_FILL, true);
   ObjectSetInteger(0, name, OBJPROP_BACK, true);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);

   CreateHLine(OBJ_PREFIX + "ORHigh", g_OR.candleTime, g_ExpiryTime, g_OR.high, Color_OpeningRange);
   CreateHLine(OBJ_PREFIX + "ORLow",  g_OR.candleTime, g_ExpiryTime, g_OR.low,  Color_OpeningRange);
  }

void DrawLiquidityMarker()
  {
   string name = OBJ_PREFIX + "LiqCandle";
   ObjectDelete(0, name);
   double price = g_Liquidity.isBullishBreak ? g_Liquidity.high : g_Liquidity.low;
   ObjectCreate(0, name, OBJ_ARROW, 0, g_Liquidity.time, price);
   ObjectSetInteger(0, name, OBJPROP_ARROWCODE, g_Liquidity.isBullishBreak ? 242 : 241);
   ObjectSetInteger(0, name, OBJPROP_COLOR, g_Liquidity.isBullishBreak ? clrRed : clrLime);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 3);
  }

void DrawFVGZone()
  {
   string name = OBJ_PREFIX + "FVG";
   ObjectDelete(0, name);
   datetime t2 = g_FVG.time + PeriodSeconds(Entry_Timeframe) * 20;
   ObjectCreate(0, name, OBJ_RECTANGLE, 0, g_FVG.time, g_FVG.top, t2, g_FVG.bottom);
   ObjectSetInteger(0, name, OBJPROP_COLOR, Color_FVG);
   ObjectSetInteger(0, name, OBJPROP_FILL, true);
   ObjectSetInteger(0, name, OBJPROP_BACK, true);
  }

void DrawEntryArrow(bool isLong, double price)
  {
   string name = OBJ_PREFIX + "Entry_" + IntegerToString((int)TimeCurrent());
   ObjectCreate(0, name, OBJ_ARROW, 0, TimeCurrent(), price);
   ObjectSetInteger(0, name, OBJPROP_ARROWCODE, isLong ? 233 : 234);
   ObjectSetInteger(0, name, OBJPROP_COLOR, isLong ? clrLime : clrRed);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 3);
  }

void DrawSLTPLines(double entry, double sl, double r, bool isLong)
  {
   datetime t1 = TimeCurrent();
   datetime t2 = t1 + PeriodSeconds(Entry_Timeframe) * 50;

   CreateHLine(OBJ_PREFIX + "SL", t1, t2, sl, clrRed);

   double tp1 = isLong ? entry + r : entry - r;
   double tp2 = isLong ? entry + 2 * r : entry - 2 * r;
   double tp3 = isLong ? entry + Reward_Risk_Ratio * r : entry - Reward_Risk_Ratio * r;

   CreateHLine(OBJ_PREFIX + "TP1", t1, t2, tp1, clrGreen);
   CreateHLine(OBJ_PREFIX + "TP2", t1, t2, tp2, clrGreen);
   CreateHLine(OBJ_PREFIX + "TP3", t1, t2, tp3, clrGreen);
  }

void DrawExpiryLine()
  {
   string name = OBJ_PREFIX + "Expiry";
   ObjectDelete(0, name);
   ObjectCreate(0, name, OBJ_VLINE, 0, g_ExpiryTime, 0);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clrGray);
   ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DOT);
  }

//======================================================================
// DASHBOARD
//======================================================================
void CreateOrUpdateLabel(string name, string text, int x, int y, color clr, int fontSize = 9)
  {
   if(ObjectFind(0, name) < 0)
     {
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
      ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
      ObjectSetString(0, name, OBJPROP_FONT, "Arial");
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
     }
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, fontSize);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
  }

void UpdateDashboard()
  {
   int x = 10, y = 15, dy = 15;

   bool tradeAllowed = (bool)MQLInfoInteger(MQL_TRADE_ALLOWED) && (bool)TerminalInfoInteger(TERMINAL_TRADE_ALLOWED);

   CreateOrUpdateLabel(OBJ_PREFIX+"L0", Robot_Name, x, y, Color_RobotName, 13); y += 22;
   CreateOrUpdateLabel(OBJ_PREFIX+"L1", "Owner: " + Owner_Name, x, y, clrWhite); y += dy;
   CreateOrUpdateLabel(OBJ_PREFIX+"L2", "Robot Status: " + (tradeAllowed ? "ACTIVE" : "OFF"), x, y, tradeAllowed ? Color_Active : Color_Off); y += dy;
   CreateOrUpdateLabel(OBJ_PREFIX+"L3", "Auto Trading: " + (Enable_Auto_Trading ? "ON" : "OFF"), x, y, Enable_Auto_Trading ? Color_Active : Color_Off); y += dy;
   CreateOrUpdateLabel(OBJ_PREFIX+"L4", "Symbol: " + _Symbol, x, y, clrWhite); y += dy;
   CreateOrUpdateLabel(OBJ_PREFIX+"L5", "Main TF: " + EnumToString(Main_Timeframe), x, y, Color_OpeningRange); y += dy;
   CreateOrUpdateLabel(OBJ_PREFIX+"L6", "Entry TF: " + EnumToString(Entry_Timeframe), x, y, Color_OpeningRange); y += dy;

   double balance    = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity      = AccountInfoDouble(ACCOUNT_EQUITY);
   double freeMargin  = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   double spread      = (SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID)) / _Point;
   double dailyProfit = equity - g_DailyStartBalance;

   CreateOrUpdateLabel(OBJ_PREFIX+"L7",  "Balance: " + DoubleToString(balance, 2), x, y, clrWhite); y += dy;
   CreateOrUpdateLabel(OBJ_PREFIX+"L8",  "Equity: " + DoubleToString(equity, 2), x, y, clrWhite); y += dy;
   CreateOrUpdateLabel(OBJ_PREFIX+"L9",  "Free Margin: " + DoubleToString(freeMargin, 2), x, y, clrWhite); y += dy;
   CreateOrUpdateLabel(OBJ_PREFIX+"L10", "Spread: " + DoubleToString(spread, 1), x, y, spread > Max_Spread_Points ? Color_Off : Color_Active); y += dy;
   CreateOrUpdateLabel(OBJ_PREFIX+"L11", "Daily P/L: " + DoubleToString(dailyProfit, 2), x, y, dailyProfit >= 0 ? Color_Active : Color_Off); y += dy;
   CreateOrUpdateLabel(OBJ_PREFIX+"L12", "Total P/L: " + DoubleToString(g_TotalProfit, 2), x, y, g_TotalProfit >= 0 ? Color_Active : Color_Off); y += dy;

   int openPos = HasOpenPosition() ? 1 : 0;
   CreateOrUpdateLabel(OBJ_PREFIX+"L13", "Open Positions: " + IntegerToString(openPos), x, y, clrWhite); y += dy;
   CreateOrUpdateLabel(OBJ_PREFIX+"L14", "Trades Today: " + IntegerToString(g_TradesToday) + "/" + IntegerToString(Max_Trades_Per_Day), x, y, clrWhite); y += dy;

   double winRate = (g_ClosedDeals > 0) ? (g_WinningDeals * 100.0 / g_ClosedDeals) : 0;
   CreateOrUpdateLabel(OBJ_PREFIX+"L15", "Win Rate: " + DoubleToString(winRate, 1) + "%", x, y, clrWhite); y += dy;

   CreateOrUpdateLabel(OBJ_PREFIX+"L16", "Session: " + StateToString(g_State), x, y, clrYellow); y += dy;
  }
//+------------------------------------------------------------------+
