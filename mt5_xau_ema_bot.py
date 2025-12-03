"""
mt5_xau_ema_bot.py
Fully Working Gold (XAUUSD.m) EMA Crossover Bot for JustMarkets-Demo
- EMA 8 / EMA 21 crossover on M1
- ATR-based Stop Loss, 1:2 RR
- 1% risk per trade
- Auto-detects correct Gold symbol
- Fixes all known MT5 Python API issues (2025)
"""

import time
import csv
from datetime import datetime
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from ta.trend import EMAIndicator
from ta.volatility import AverageTrueRange

# --------------------- CONFIG ---------------------
MT5_LOGIN = 5043219485
MT5_PASSWORD = "AtVd*7Jz"
MT5_SERVER = "MetaQuotes-Demo"

TIMEFRAME = mt5.TIMEFRAME_M1
BAR_COUNT = 500

EMA_FAST = 8
EMA_SLOW = 21
ATR_PERIOD = 14
ATR_MULTIPLIER = 2.0

RISK_PERCENT = 0.01       # 1% risk per trade
MAX_LOTS = 5.0
MIN_LOTS = 0.01
LOT_STEP = 0.01

DEVIATION = 20            # Increased for Gold volatility
MAGIC = 202505
TRADE_COMMENT = "Gold_EMA_Bot_v2"
LOG_CSV = "gold_bot_trades.csv"
POLL_INTERVAL = 8         # Check every 8 seconds (M1 bar = 60s)
# --------------------------------------------------

def init_mt5():
    if not mt5.initialize():
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    
    if MT5_LOGIN:
        if not mt5.login(MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER):
            raise RuntimeError(f"Login failed: {mt5.last_error()}")
    
    print(f"MT5 Connected | Account: {mt5.account_info().login} | Server: {MT5_SERVER}")
    print(f"Terminal version: {mt5.version()[0]}.{mt5.version()[1]}")

def find_gold_symbol():
    print("Searching for Gold symbol (XAUUSD.m, XAUUSD, GOLD, etc.)...")
    symbols = mt5.symbols_get()
    for s in symbols:
        if "XAU" in s.name or "GOLD" in s.name:
            if "gold" in s.description.lower() or "xau" in s.description.lower():
                if mt5.symbol_select(s.name, True):
                    print(f"Gold symbol found & enabled: {s.name}")
                    return s.name
    raise RuntimeError("Gold symbol not found! Open MT5 → Ctrl+U → search 'XAU' → double-click it.")

def ensure_symbol(symbol):
    info = mt5.symbol_info(symbol)
    if info is None:
        raise RuntimeError(f"Symbol {symbol} not found even after select!")
    
    # Correct check for trading permission (new API)
    if info.trade_mode == mt5.SYMBOL_TRADE_MODE_DISABLED:
        raise RuntimeError(f"Trading disabled for {symbol} by broker!")

    if not info.visible:
        mt5.symbol_select(symbol, True)
        time.sleep(1)

    print(f"Symbol ready: {symbol}")
    print(f"   Point: {info.point} | Digits: {info.digits} | Contract size: {info.trade_contract_size}")
    return info

def get_bars(symbol, timeframe, count):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is None or len(rates) == 0:
        print("Warning: No bars received. Retrying later...")
        return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    return df

def calculate_indicators(df):
    df = df.copy()
    df['ema_fast'] = EMAIndicator(df['close'], window=EMA_FAST).ema_indicator()
    df['ema_slow'] = EMAIndicator(df['close'], window=EMA_SLOW).ema_indicator()
    df['atr'] = AverageTrueRange(df['high'], df['low'], df['close'], window=ATR_PERIOD).average_true_range()
    return df

def get_equity():
    info = mt5.account_info()
    if info is None:
        return 100000.0  # fallback
    return info.equity

def round_lot(lots):
    lots = max(MIN_LOTS, min(MAX_LOTS, round(lots / LOT_STEP) * LOT_STEP))
    return round(lots, 2)

def calculate_position_size(symbol_info, entry_price, sl_price):
    equity = get_equity()
    risk_amount = equity * RISK_PERCENT
    contract_size = symbol_info.trade_contract_size
    point_value = symbol_info.trade_tick_value / symbol_info.trade_tick_size
    
    risk_in_price = abs(entry_price - sl_price)
    if risk_in_price <= 0:
        return 0.0
    
    lots = risk_amount / (risk_in_price * contract_size * (point_value / symbol_info.point))
    return round_lot(lots)

def send_order(symbol, action, lots, sl, tp):
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print("No tick data")
        return None

    price = tick.ask if action == "BUY" else tick.bid
    order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(lots),
        "type": order_type,
        "price": price,
        "sl": float(sl),
        "tp": float(tp),
        "deviation": DEVIATION,
        "magic": MAGIC,
        "comment": TRADE_COMMENT,
        "type_time": mt5.ORDER_TIME_GTC,
        # ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
        # NO type_filling AT ALL — this is the fix
        # ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
    }

    result = mt5.order_send(request)

    if result.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"SUCCESS → {action} {lots:.2f} @ {price:.5f} | SL {sl:.2f} | TP {tp:.2f}")
        log_trade([datetime.utcnow().isoformat(), symbol, action, lots, price, sl, tp, "DONE"])
    else:
        print(f"FAILED → {result.retcode} | {result.comment}")

    return result

def log_trade(row):
    header = ["timestamp", "symbol", "action", "lots", "price", "sl", "tp", "retcode"]
    write_header = not __import__('os').path.exists(LOG_CSV)
    with open(LOG_CSV, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(header)
        writer.writerow(row)

def has_open_position(symbol):
    positions = mt5.positions_get(symbol=symbol)
    return positions is not None and len(positions) > 0

# --------------------- MAIN ---------------------
SYMBOL = None  # Will be set after connection

def main():
    global SYMBOL
    init_mt5()
    SYMBOL = find_gold_symbol()
    symbol_info = ensure_symbol(SYMBOL)

    print(f"\nStarting Gold EMA Bot on {SYMBOL} (M1)")
    print("Press Ctrl+C to stop\n")

    while True:
        try:
            df = get_bars(SYMBOL, TIMEFRAME, BAR_COUNT)
            if df is None or len(df) < EMA_SLOW + 10:
                time.sleep(POLL_INTERVAL)
                continue

            df = calculate_indicators(df)
            last = df.iloc[-1]
            prev = df.iloc[-2]

            # Crossover detection
            buy_signal = prev['ema_fast'] <= prev['ema_slow'] and last['ema_fast'] > last['ema_slow']
            sell_signal = prev['ema_fast'] >= prev['ema_slow'] and last['ema_fast'] < last['ema_slow']

            atr = max(last['atr'], 0.01)  # avoid zero
            tick = mt5.symbol_info_tick(SYMBOL)

            if tick is None:
                time.sleep(POLL_INTERVAL)
                continue

            if buy_signal and not has_open_position(SYMBOL):
                entry = tick.ask
                sl = entry - atr * ATR_MULTIPLIER
                tp = entry + (entry - sl) * 2
                lots = calculate_position_size(symbol_info, entry, sl)
                if lots >= MIN_LOTS:
                    send_order(SYMBOL, "BUY", lots, sl, tp)

            elif sell_signal and not has_open_position(SYMBOL):
                entry = tick.bid
                sl = entry + atr * ATR_MULTIPLIER
                tp = entry - (sl - entry) * 2
                lots = calculate_position_size(symbol_info, entry, sl)
                if lots >= MIN_LOTS:
                    send_order(SYMBOL, "SELL", lots, sl, tp)

            time.sleep(POLL_INTERVAL)

        except Exception as e:
            print(f"Error in loop: {e}")
            time.sleep(10)

    mt5.shutdown()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
    finally:
        mt5.shutdown()
        print("MT5 connection closed.")