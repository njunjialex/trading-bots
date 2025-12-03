# gold_daily_breakout_2025.py
import MetaTrader5 as mt5
import pandas as pd
import time
from datetime import datetime

# ================= CONFIG =================
LOGIN = 5043219485
PASSWORD = "AtVd*7Jz"
SERVER = "MetaQuotes-Demo"
SYMBOL = "XAUUSD.m"
RISK_PERCENT = 0.01          # 1% per trade max
MAGIC = 20251225
COMMENT = "Gold_Daily_Breakout_2025"
# =========================================

mt5.initialize()
mt5.login(LOGIN, PASSWORD, SERVER)

def get_daily_data():
    rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_D1, 0, 50)
    df = pd.DataFrame(rates)
    df['date'] = pd.to_datetime(df['time'], unit='s').dt.date
    return df

def already_in_trade():
    pos = mt5.positions_get(symbol=SYMBOL)
    return pos and len(pos) > 0

while True:
    try:
        df = get_daily_data()
        if len(df) < 21:
            time.sleep(3600)
            continue

        high_20 = df['high'].rolling(20).max().iloc[-2]   # yesterday's 20-day high
        close_yesterday = df['close'].iloc[-2]
        low_yesterday = df['low'].iloc[-2]

        # New 20-day high breakout?
        if close_yesterday > high_20 and not already_in_trade():
            entry = mt5.symbol_info_tick(SYMBOL).ask
            sl = low_yesterday
            tp = entry + 3 * (entry - sl)
            
            risk_amount = mt5.account_info().equity * RISK_PERCENT
            tick_value = mt5.symbol_info(SYMBOL).trade_tick_value
            point = mt5.symbol_info(SYMBOL).point
            lots = risk_amount / ((entry - sl) / point * tick_value)
            lots = round(max(0.01, min(5.0, lots)), 2)

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": SYMBOL,
                "volume": lots,
                "type": mt5.ORDER_TYPE_BUY,
                "price": entry,
                "sl": sl,
                "tp": tp,
                "deviation": 30,
                "magic": MAGIC,
                "comment": COMMENT,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            result = mt5.order_send(request)
            print(f"{datetime.now()} → BREAKOUT BUY {lots} lots | Entry {entry:.2f} | SL {sl:.2f} | TP {tp:.2f}")

        time.sleep(3600)  # Check every hour

    except Exception as e:
        print(e)
        time.sleep(60)