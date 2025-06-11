
//+------------------------------------------------------------------+
//| Advanced XAUUSD Scalping Bot (MT5)                              |
//| Strategy: Smart Reversal Scalper                                |
//| Author: ChatGPT Custom Strategy                                 |
//+------------------------------------------------------------------+
#property strict

input double LotSize = 0.1;
input double RiskPercent = 1.0; // Dynamic lot sizing (% of balance)
input int RSI_Period = 14;
input int BB_Period = 20;
input double BB_Deviation = 2.0;
input double ATR_Multiplier_SL = 1.0;
input double ATR_Multiplier_TP = 1.5;
input double MaxSpreadPoints = 15;
input bool UseNewsFilter = true;
input bool UseTrailingStop = true;
input int MaxTradesPerHour = 10;
input int TradeCooldownMinutes = 3;
input int Slippage = 10;

#include <Trade\Trade.mqh>
CTrade trade;

int rsiHandle, bbHandle, atrHandle;
double rsi[], upperBB[], lowerBB[], atr[];
datetime lastTradeTime = 0;
int tradeCountHour = 0;
datetime lastTradeHour = 0;

//+------------------------------------------------------------------+
int OnInit()
{
   rsiHandle = iRSI(_Symbol, _Period, RSI_Period, PRICE_CLOSE);
   bbHandle = iBands(_Symbol, _Period, BB_Period, BB_Deviation, 0, PRICE_CLOSE);
   atrHandle = iATR(_Symbol, _Period, 14);

   if (rsiHandle == INVALID_HANDLE || bbHandle == INVALID_HANDLE || atrHandle == INVALID_HANDLE)
   {
      Print("Indicator handle error");
      return INIT_FAILED;
   }
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnTick()
{
   if (PositionsTotal() > 0) return;
   if ((TimeCurrent() - lastTradeTime) < TradeCooldownMinutes * 60) return;
   if (!SessionAllowed()) return;

   datetime now = TimeCurrent();
   if (TimeHour(now) != TimeHour(lastTradeHour))
   {
      tradeCountHour = 0;
      lastTradeHour = now;
   }
   if (tradeCountHour >= MaxTradesPerHour) return;

   if (MarketInfo(_Symbol, MODE_SPREAD) > MaxSpreadPoints) return;

   int bars = 3;
   if (CopyBuffer(rsiHandle, 0, 0, bars, rsi) <= 0 ||
       CopyBuffer(bbHandle, 1, 0, bars, upperBB) <= 0 ||
       CopyBuffer(bbHandle, 2, 0, bars, lowerBB) <= 0 ||
       CopyBuffer(atrHandle, 0, 0, bars, atr) <= 0)
   {
      Print("Buffer copy failed");
      return;
   }

   double close = Close[0];
   double vol = AccountFreeMarginCheck(_Symbol, ORDER_TYPE_BUY, LotSize);
   double riskLot = CalculateRiskLot(atr[0]);
   double sl, tp;

   if (close < lowerBB[0] && rsi[0] < 30 && HeikinAshiIsBullish())
   {
      sl = close - (ATR_Multiplier_SL * atr[0]);
      tp = close + (ATR_Multiplier_TP * atr[0]);
      if (trade.Buy(riskLot, _Symbol, 0, sl, tp))
      {
         lastTradeTime = now;
         tradeCountHour++;
      }
   }
   else if (close > upperBB[0] && rsi[0] > 70 && HeikinAshiIsBearish())
   {
      sl = close + (ATR_Multiplier_SL * atr[0]);
      tp = close - (ATR_Multiplier_TP * atr[0]);
      if (trade.Sell(riskLot, _Symbol, 0, sl, tp))
      {
         lastTradeTime = now;
         tradeCountHour++;
      }
   }
}

//+------------------------------------------------------------------+
bool HeikinAshiIsBullish()
{
   double haOpen = (Open[1] + Close[1]) / 2.0;
   double haClose = (Open[0] + High[0] + Low[0] + Close[0]) / 4.0;
   return haClose > haOpen;
}

bool HeikinAshiIsBearish()
{
   double haOpen = (Open[1] + Close[1]) / 2.0;
   double haClose = (Open[0] + High[0] + Low[0] + Close[0]) / 4.0;
   return haClose < haOpen;
}

//+------------------------------------------------------------------+
double CalculateRiskLot(double atrValue)
{
   double balance = AccountBalance();
   double riskAmount = balance * (RiskPercent / 100.0);
   double pipValue = atrValue * MathPow(10, _Digits);
   double lotSize = riskAmount / (pipValue * 10); // Approximate
   return NormalizeDouble(lotSize, 2);
}

bool SessionAllowed()
{
   datetime t = TimeCurrent();
   int hour = TimeHour(t);
   // Example: avoid trading from 22:00 to 00:00 server time
   if (hour >= 22 || hour < 0) return false;
   return true;
}
//+------------------------------------------------------------------+
