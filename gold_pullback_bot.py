"""
Gold Trend Pullback Pro Bot - XAUUSD H1 (JustMarkets-Demo Optimized)
- Trend Filter: Price > 200 EMA (bullish only)
- Entry: 21 EMA pullback + RSI(14) > 45 + BB Upper Breakout
- Risk: 1% equity, ATR(14) SL (2x), 1:2 RR TP
- Timeframe: H1 (less noise, trend capture)
- 2025 Gold Bull Tuned: Long bias, vol-aware
"""

import time
import csv
from datetime import datetime
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange, BollingerBands

# --------------------- CONFIG ---------------------
MT5_LOGIN = 5043219485
MT5_PASSWORD = "AtVd*7Jz"
MT5_SERVER = "MetaQuotes-Demo"

TIMEFRAME = mt5.TIMEFRAME_H1  # H1 for trend stability
BAR_COUNT = 300  # Enough for indicators

EMA_FAST = 21     # Pullback EMA
EMA_TREND = 200   # Trend filter
RSI_PERIOD = 14
RSI_THRESHOLD = 45  # Momentum filter
ATR_PERIOD = 14
ATR_SL_MULT = 2.0
RR_RATIO = 2.0    # 1:2 risk-reward

RISK_PERCENT = 0.01  # 1% risk
MAX_LOTS = 5.0
MIN_LOTS = 0.01
LOT_STEP = 0.01

DEVIATION = 20
MAGIC = 20251203  # Unique for this strategy
TRADE_COMMENT = "Gold_Pullback_Pro"
LOG_CSV = "gold_pullback_trades.csv"
POLL_INTERVAL = 60  # 1 min checks on H1
# --------------------------------------------------

import time
import MetaTrader5 as mt5

def init_mt5():
    """Connect + guarantee XAUUSD.m is visible and trading – JustMarkets-Demo proof"""
    
    # 1. Connect (no path/login = uses already-open MT5)
    if not mt5.initialize():
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")

    print("Connected to MetaTrader 5")
    print(f"Terminal version: {mt5.version()}")

    # 2. Account check
    account = mt5.account_info()
    if account is None:
        raise RuntimeError("Not logged in! Open MT5 → login to your JustMarkets-Demo account first.")
    print(f"Account: {account.login} | Balance: {account.balance:.2f} {account.currency}")

    # 3. FORCE XAUUSD.m into Market Watch (JustMarkets-Demo special version)
    target_symbol = "XAUUSD"
    
    # Try 3 times – sometimes the first select fails silently on demo
    for attempt in range(3):
        if mt5.symbol_select(target_symbol, True):
            print(f"XAUUSD added to Market Watch (attempt {attempt+1})")
            break
        else:
            print(f"symbol_select failed (attempt {attempt+1}) – retrying...")
            time.sleep(2)
    else:
        raise RuntimeError("Could NOT add XAUUSD automatically. Do this manually:\n"
                           "   → Open MT5 → Press Ctrl+U → type 'XAU' → double-click XAUUSD.m → Close")

    # Wait a tiny bit for the server to send ticks
    time.sleep(3)

    # Final safety check
    tick = mt5.symbol_info_tick(target_symbol)
    if tick is None or tick.bid == 0:
        raise RuntimeError("XAUUSD.m added but no price feed! Right-click XAUUSD.m in Market Watch → 'Show' or restart MT5.")

    print(f"GOLD LIVE → Bid {tick.bid:.2f} | Ask {tick.ask:.2f} | Spread {tick.ask - tick.bid:.2f}")
    print("=" * 65)
    print("BOT READY – You can now run the full Gold pullback bot")
    print("=" * 65)
def find_gold_symbol():
    symbols = mt5.symbols_get()
    for s in symbols:
        if "XAU" in s.name and ("gold" in s.description.lower() or "xau" in s.description.lower()):
            mt5.symbol_select(s.name, True)
            print(f"Gold enabled: {s.name}")
            return s.name
    raise RuntimeError("Gold not found! Ctrl+U in MT5 > search 'XAU' > enable.")

def ensure_symbol(symbol):
    info = mt5.symbol_info(symbol)
    if info is None or info.trade_mode == mt5.SYMBOL_TRADE_MODE_DISABLED:
        raise RuntimeError(f"Trading disabled for {symbol}")
    if not info.visible:
        mt5.symbol_select(symbol, True)
        time.sleep(1)
    print(f"Symbol ready: {symbol} | Contract: {info.trade_contract_size} | Tick Value: {info.trade_tick_value}")
    return info

def get_bars(symbol, timeframe, count):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is None or len(rates) < EMA_TREND + 10:
        return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    return df

def calculate_indicators(df):
    df = df.copy()
    df['ema_fast'] = EMAIndicator(df['close'], EMA_FAST).ema_indicator()
    df['ema_trend'] = EMAIndicator(df['close'], EMA_TREND).ema_indicator()
    df['rsi'] = RSIIndicator(df['close'], RSI_PERIOD).rsi()
    df['atr'] = AverageTrueRange(df['high'], df['low'], df['close'], ATR_PERIOD).average_true_range()
    bb = BollingerBands(df['close'], window=20, window_dev=2)
    df['bb_upper'] = bb.bollinger_hband()
    df['bb_lower'] = bb.bollinger_lband()
    return df

def get_equity():
    info = mt5.account_info()
    return info.equity if info else 100000.0

def round_lot(lots):
    return max(MIN_LOTS, min(MAX_LOTS, round(lots / LOT_STEP) * LOT_STEP))

def calculate_lots(symbol_info, entry, sl, equity):
    risk_amount = equity * RISK_PERCENT
    contract_size = symbol_info.trade_contract_size
    tick_value = symbol_info.trade_tick_value
    risk_pips = abs(entry - sl) / symbol_info.point
    lots = risk_amount / (risk_pips * tick_value * contract_size / symbol_info.point)
    return round_lot(lots)

def send_order(symbol, action, lots, sl, tp):
    symbol_info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)
    if not symbol_info or not tick:
        print("Error: No symbol/tick data")
        return None

    price = tick.ask if action == "BUY" else tick.bid
    order_type = mt5.ORDER_TYPE_BUY if action == "BUY" else mt5.ORDER_TYPE_SELL

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lots,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": DEVIATION,
        "magic": MAGIC,
        "comment": TRADE_COMMENT,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,   # ← Force IOC (the only one your symbol supports)
    }

    # CRITICAL: Remove type_filling completely for JustMarkets-Demo
    # The broker ignores it anyway and uses its own default
    request.pop("type_filling", None)   # ← This one line fixes 10030 forever

    result = mt5.order_send(request)

    if result.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"ORDER SUCCESS → {action} {lots:.2f} @ {price:.2f} | SL {sl:.2f} | TP {tp:.2f}")
        log_trade([datetime.utcnow().isoformat(), symbol, action, lots, price, sl, tp, "DONE"])
    else:
        print(f"Order FAILED → Retcode: {result.retcode} | {result.comment}")

    return result

def log_trade(row):
    header = ["timestamp", "symbol", "action", "lots", "price", "sl", "tp", "retcode"]
    write_header = not csv_path_exists(LOG_CSV)  # Simple check
    with open(LOG_CSV, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(header)
        writer.writerow(row)

def csv_path_exists(path):  # Helper
    import os
    return os.path.exists(path)

def has_position(symbol):
    positions = mt5.positions_get(symbol=symbol)
    return positions and len(positions) > 0

# --------------------- MAIN ---------------------
SYMBOL = None

def main():
    global SYMBOL
    init_mt5()
    SYMBOL = find_gold_symbol()
    symbol_info = ensure_symbol(SYMBOL)

    print(f"\nGold Pullback Pro Live on {SYMBOL} (H1) | Bull Bias: Price > 200 EMA")
    print("Ctrl+C to stop\n")

    while True:
        try:
            df = get_bars(SYMBOL, TIMEFRAME, BAR_COUNT)
            if df is None:
                time.sleep(POLL_INTERVAL)
                continue

            df = calculate_indicators(df)
            last = df.iloc[-1]
            prev = df.iloc[-2]

            # Trend Filter: Only BUY if above 200 EMA (2025 bull alignment)
            if last['close'] <= last['ema_trend'] or has_position(SYMBOL):
                time.sleep(POLL_INTERVAL)
                continue

            atr = max(last['atr'], last['close'] * 0.001)  # Min buffer
            tick = mt5.symbol_info_tick(SYMBOL)
            if tick is None:
                continue

            # BUY Signal: Pullback to 21 EMA + RSI recovery + BB Upper breakout
            pullback = prev['close'] > prev['ema_fast'] and last['close'] <= last['ema_fast']  # Touched fast EMA
            momentum = last['rsi'] > RSI_THRESHOLD
            breakout = last['close'] > last['bb_upper']

            if pullback and momentum and breakout:
                entry = tick.ask
                sl = entry - (atr * ATR_SL_MULT)
                tp = entry + (entry - sl) * RR_RATIO
                lots = calculate_lots(symbol_info, entry, sl, get_equity())
                if lots >= MIN_LOTS:
                    send_order(SYMBOL, "BUY", lots, sl, tp)

            time.sleep(POLL_INTERVAL)

        except Exception as e:
            print(f"Loop error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBot stopped.")
    finally:
        mt5.shutdown()
        print("Disconnected.")