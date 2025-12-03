import MetaTrader5 as mt5

if not mt5.initialize():
    print("initialize() failed")
    quit()

print("Searching for Gold symbols your broker offers...\n")

found = False
symbols = mt5.symbols_get()
for s in symbols:
    if "XAU" in s.name.upper() or "GOLD" in s.name.upper():
        print(f"✓ {s.name:15}  →  {s.description}")
        found = True

if not found:
    print("No Gold symbol found at all. Your broker may not offer it on this account.")

mt5.shutdown()