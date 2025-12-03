# Gold SMC Trading Bot
Automated Smart Money Concepts bot for XAUUSD.m on MT5 (JustMarkets-Demo/Live).

## Features
- Detects Order Blocks, FVGs, and Liquidity Grabs
- RSI + Fib confirmation for entries
- 1% risk management, 1:2 RR
- Logs trades to CSV

## Setup
1. Install MT5 and log in to your JustMarkets account
2. Install Python 3.10+ and create venv: `python -m venv venv`
3. Activate venv: `venv\Scripts\activate` (Windows)
4. Install requirements: `pip install -r requirements.txt`
5. Update `MT5_PASSWORD` in `gold_smc_bot.py`
6. Run: `python gold_smc_bot.py`

## Disclaimer
This is for educational purposes. Trading involves risk. Test on demo first!

## License
MIT License