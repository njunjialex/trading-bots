# check_autotrading.py
# Run this anytime to see if your JustMarkets-Demo allows Python orders

import MetaTrader5 as mt5
from datetime import datetime

def check_autotrading_status():
    if not mt5.initialize():
        print("MT5 initialize failed:", mt5.last_error())
        return

    # Try to login (optional – works even without login on running terminal)
    # mt5.login(2001632821, password="your_password", server="JustMarkets-Demo")

    print(f"{'='*50}")
    print(f"AUTOTRADING STATUS CHECK – {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}")

    # 1. Terminal-level AutoTrading (the button at the top)
    terminal_info = mt5.terminal_info()
    if terminal_info:
        trade_allowed = terminal_info.trade_allowed
        autotrading_button = "ENABLED (Green)" if trade_allowed else "DISABLED (Red)"
        print(f"Terminal AutoTrading Button : {autotrading_button}")
    else:
        print("Could not read terminal_info()")

    # 2. Server-level permission (this is what causes retcode 10026)
    account_info = mt5.account_info()
    if account_info:
        server_trade_allowed = account_info.trade_allowed
        print(f"Server allows trading     : {'YES' if server_trade_allowed else 'NO ← THIS CAUSES 10026'}")
    else:
        print("Could not read account_info()")

    # 3. Quick test order (the ultimate truth)
    symbol = "XAUUSD.m"
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        print(f"No tick data for {symbol} → symbol not in Market Watch?")
    else:
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": 0.01,
            "type": mt5.ORDER_TYPE_BUY,
            "price": tick.ask,
            "deviation": 20,
            "magic": 999999,
            "comment": "AUTOTRADING_TEST",
            # NO type_filling → works on JustMarkets
        }
        result = mt5.order_send(request)
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"TEST ORDER → SUCCESS! AutoTrading is 100% working")
        elif result.retcode == 10026:
            print(f"TEST ORDER → FAILED with 10026 → Server disabled AutoTrading")
            print(f"   → Open MT5 → Click the AutoTrading button (top toolbar) to turn it green")
        else:
            print(f"TEST ORDER → Other error: {result.retcode} | {result.comment}")

    mt5.shutdown()

# ——————————————— RUN IT ———————————————
if __name__ == "__main__":
    check_autotrading_status()