"""
SMC-Based Trading Bot for MT5 (XAUUSD.m) - With Liquidity Grab Detection
- Detects Bullish Order Blocks (OB) + Fair Value Gaps (FVG) + Liquidity Grabs (LG)
- Confirmation: RSI >50 + Fibonacci 61.8% retrace + LG (price sweeps low then reverses)
- Entry: On OB retest with confirmations
- Exit: 1:2 RR TP or trailing stop on BOS
- Risk: 1% per trade, max 1 position
- Real-time M15 data from MT5
- Run with MT5 terminal open & logged in
"""

import time
import csv
from datetime import datetime
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange

# --------------------- CONFIG ---------------------
MT5_LOGIN = 5043219485  # Your demo/live login
MT5_PASSWORD = "AtVd*7Jz"  # Replace with actual
MT5_SERVER = "MetaQuotes-Demo"  # Or "-Live"

SYMBOL = "XAUUSD"
TIMEFRAME = mt5.TIMEFRAME_M15  # M15 for intraday SMC
BAR_COUNT = 200  # Bars for calculations

RSI_PERIOD = 14
RSI_THRESHOLD = 50  # For bullish confirmation
ATR_PERIOD = 14
ATR_SL_MULT = 1.5  # SL = ATR * mult
RR_RATIO = 2.0  # 1:2 risk-reward

RISK_PERCENT = 0.01  # 1% risk per trade
MAX_LOTS = 5.0
MIN_LOTS = 0.01
LOT_STEP = 0.01

DEVIATION = 20
MAGIC = 20251203
TRADE_COMMENT = "SMC_Bot"
LOG_CSV = "smc_trades.csv"
POLL_INTERVAL = 15  # Seconds between checks
# --------------------------------------------------

def init_mt5():
    if not mt5.initialize():
        raise RuntimeError(f"MT5 init failed: {mt5.last_error()}")
    if MT5_LOGIN:
        if not mt5.login(MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER):
            raise RuntimeError(f"Login failed: {mt5.last_error()}")
    print(f"Connected | Account: {mt5.account_info().login}")

def ensure_symbol(symbol):
    if not mt5.symbol_select(symbol, True):
        raise RuntimeError(f"Failed to add {symbol} to Market Watch")
    info = mt5.symbol_info(symbol)
    if info is None or info.trade_mode == mt5.SYMBOL_TRADE_MODE_DISABLED:
        raise RuntimeError(f"Trading disabled for {symbol}")
    print(f"Symbol ready: {symbol}")
    return info

def get_bars(symbol, timeframe, count):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is None or len(rates) < count:
        return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    return df

def detect_bullish_ob(df):
    """Find last down candle before up move (demand zone)"""
    ob_lows = []
    for i in range(1, len(df)-1):
        if df['close'].iloc[i-1] > df['close'].iloc[i] and df['close'].iloc[i] < df['close'].iloc[i+1]:
            ob_lows.append(df['low'].iloc[i])
    return ob_lows[-1] if ob_lows else None  # Latest OB

def detect_fvg(df):
    """Detect upward FVG (gap to fill)"""
    for i in range(1, len(df)-1):
        if df['high'].iloc[i-1] < df['low'].iloc[i+1]:
            return (df['high'].iloc[i-1], df['low'].iloc[i+1])  # Gap range
    return None

def detect_liquidity_grab(df):
    """Detect bullish liquidity grab: Price sweeps recent low then reverses (wick below swing low + close above)"""
    for i in range(2, len(df)):
        swing_low = df['low'].iloc[i-2:i].min()
        if df['low'].iloc[i] < swing_low and df['close'].iloc[i] > df['open'].iloc[i]:  # Wick sweep + bullish close
            return df['low'].iloc[i]  # Grab level
    return None

def calculate_fib_retrace(df):
    """Simple Fib 61.8% from recent swing high/low"""
    swing_high = df['high'].max()
    swing_low = df['low'].min()
    fib_618 = swing_high - 0.618 * (swing_high - swing_low)
    return fib_618

def get_equity():
    info = mt5.account_info()
    return info.equity if info else 100000.0

def round_lot(lots):
    return max(MIN_LOTS, min(MAX_LOTS, round(lots / LOT_STEP) * LOT_STEP))

def calculate_lots(symbol_info, entry, sl, equity):
    risk_amount = equity * RISK_PERCENT
    risk_pips = abs(entry - sl) / symbol_info.point
    tick_value = symbol_info.trade_tick_value
    lots = risk_amount / (risk_pips * tick_value)
    return round_lot(lots)

def send_order(symbol, action, lots, sl, tp):
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
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
    }  # No type_filling – fixes 10030 on JustMarkets

    result = mt5.order_send(request)
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"SUCCESS: {action} {lots:.2f} @ {price:.2f} | SL {sl:.2f} | TP {tp:.2f}")
    else:
        print(f"FAILED: {result.retcode} - {result.comment}")
    return result

def log_trade(row):
    header = ["timestamp", "symbol", "action", "lots", "price", "sl", "tp", "retcode"]
    with open(LOG_CSV, 'a', newline='') as f:
        writer = csv.writer(f)
        if not os.path.exists(LOG_CSV):
            writer.writerow(header)
        writer.writerow(row)

def has_position(symbol):
    positions = mt5.positions_get(symbol=symbol)
    return len(positions) > 0 if positions else False

def main():
    init_mt5()
    symbol_info = ensure_symbol(SYMBOL)

    print(f"\nSMC Bot Running on {SYMBOL} ({TIMEFRAME})")
    while True:
        try:
            df = get_bars(SYMBOL, TIMEFRAME, BAR_COUNT)
            if df is None:
                time.sleep(POLL_INTERVAL)
                continue

            # SMC Signals
            ob_low = detect_bullish_ob(df)
            fvg = detect_fvg(df)
            lg_low = detect_liquidity_grab(df)
            if ob_low is None or fvg is None or lg_low is None:
                time.sleep(POLL_INTERVAL)
                continue

            # Confirmations
            rsi = RSIIndicator(df['close'], RSI_PERIOD).rsi().iloc[-1]
            fib_618 = calculate_fib_retrace(df.iloc[-50:])  # Last 50 bars for swing
            atr = AverageTrueRange(df['high'], df['low'], df['close'], ATR_PERIOD).average_true_range().iloc[-1]

            last_close = df['close'].iloc[-1]
            last_low = df['low'].iloc[-1]
            if last_close > ob_low and rsi > RSI_THRESHOLD and abs(last_close - fib_618) < atr * 0.5 and last_low <= lg_low and not has_position(SYMBOL):
                # ENTRY: Buy on OB retest + RSI + Fib + LG confluence
                entry = mt5.symbol_info_tick(SYMBOL).ask
                sl = entry - atr * ATR_SL_MULT
                tp = entry + (entry - sl) * RR_RATIO
                equity = get_equity()
                lots = calculate_lots(symbol_info, entry, sl, equity)
                if lots >= MIN_LOTS:
                    result = send_order(SYMBOL, "BUY", lots, sl, tp)
                    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                        log_trade([datetime.utcnow().isoformat(), SYMBOL, "BUY", lots, entry, sl, tp, "DONE"])

            # EXIT: For open position, trail or close on FVG fill (simple version)
            positions = mt5.positions_get(symbol=SYMBOL)
            if positions:
                pos = positions[0]
                if last_close >= fvg[1] if fvg else False:  # FVG filled
                    close_request = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": SYMBOL,
                        "volume": pos.volume,
                        "type": mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY,
                        "position": pos.ticket,
                        "price": mt5.symbol_info_tick(SYMBOL).bid if pos.type == 0 else mt5.symbol_info_tick(SYMBOL).ask,
                        "deviation": DEVIATION,
                        "magic": MAGIC,
                        "comment": "SMC_Close",
                        "type_time": mt5.ORDER_TIME_GTC,
                    }
                    mt5.order_send(close_request)
                    print(f"CLOSED position {pos.ticket} on FVG fill")

            time.sleep(POLL_INTERVAL)

        except Exception as e:
            print(f"Loop error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Bot stopped by user")
    finally:
        mt5.shutdown()
        print("MT5 disconnected")