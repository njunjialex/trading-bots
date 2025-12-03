import MetaTrader5 as mt5

# Display package info
print("MetaTrader5 package author: ", mt5.__author__)
print("MetaTrader5 package version: ", mt5.__version__)

# Specify path to MT5 terminal (adjust to your installation)
terminal_path = "C:/Program Files/MetaTrader 5/terminal64.exe"

# Initialize with path and increased timeout (in milliseconds; default is 60000)
if not mt5.initialize(path=terminal_path, timeout=180000):
    print("initialize() failed, error code =", mt5.last_error())
    quit()

# Now attempt login (use your demo credentials)
account = 5043219485  # Your demo account number
password = "AtVd*7Jz"
server = "MetaQuotes-Demo"  # e.g., "MetaQuotes-Demo"
if not mt5.login(account, server=server, password=password):
    print("login() failed, error code =", mt5.last_error())
    mt5.shutdown()
    quit()

print("Connected and logged in successfully!")
print("Account info:", mt5.account_info())

# Don't forget to shutdown when done
mt5.shutdown()