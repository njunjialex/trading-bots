import MetaTrader5 as mt5
mt5.initialize()
mt5.login(2001632821, password="nft3rsNjunj@", server="JustMarkets-Demo")

request = {
    "action": mt5.TRADE_ACTION_DEAL,
    "symbol": "XAUUSD.m",
    "volume": 0.01,
    "type": mt5.ORDER_TYPE_BUY,
    "price": mt5.symbol_info_tick("XAUUSD.m").ask,
    "sl": 0.0, "tp": 0.0,
    "deviation": 20,
    "magic": 999999,
    "comment": "TEST_NO_FILLING",
    # NO type_filling line at all
}
result = mt5.order_send(request)
print(result)