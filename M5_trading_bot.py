import MetaTrader5 as mt5
import pandas as pd
import time
from datetime import datetime

# ---- CONFIG ----
SYMBOL = "XAUUSD"
TIMEFRAME = mt5.TIMEFRAME_M1
LOT = 0.1
MAGIC = 123456
MAX_SPREAD_POINTS = 20 # Adjusted to allow slightly higher spreads (e.g., 2.0 pips)

# ---- Connect to MT5 ----
if not mt5.initialize():
    print(f"Failed to initialize MetaTrader 5: Error code = {mt5.last_error()}")
    quit()
else:
    print(f"{datetime.now()} - MetaTrader 5 initialized successfully.")

# ---- Fetch OHLCV Data ----
def get_data(symbol, timeframe, bars):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

# ---- Compute Indicators ----
def compute_indicators(df):
    df['ema50'] = df['close'].ewm(span=50).mean()
    df['std'] = df['close'].rolling(20).std()
    df['bb_upper'] = df['close'].rolling(20).mean() + 2 * df['std']
    df['bb_lower'] = df['close'].rolling(20).mean() - 2 * df['std']
    df['atr'] = (df['high'] - df['low']).rolling(14).mean()

    # RSI
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # Heikin Ashi Calculation
    ha_df = df.copy()
    ha_df['ha_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    ha_df['ha_open'] = 0.0
    for i in range(len(ha_df)):
        if i == 0:
            ha_df.at[i, 'ha_open'] = df['open'].iloc[i]
        else:
            ha_df.at[i, 'ha_open'] = (ha_df['ha_open'].iloc[i - 1] + ha_df['ha_close'].iloc[i - 1]) / 2
    df['ha_open'] = ha_df['ha_open']
    df['ha_close'] = ha_df['ha_close']
    return df

# ---- Trading Signal Logic ----
def check_trade_opportunity(df):
    last = df.iloc[-1]

    symbol_info_tick = mt5.symbol_info_tick(SYMBOL)
    if symbol_info_tick is None:
        print(f"{datetime.now()} - Error getting tick info.")
        return None

    symbol_info = mt5.symbol_info(SYMBOL)
    if symbol_info is None:
        print(f"{datetime.now()} - Error getting symbol info.")
        return None

    spread = symbol_info_tick.ask - symbol_info_tick.bid
    spread_in_points = spread / symbol_info.point
    print(f"{datetime.now()} - Bid: {symbol_info_tick.bid}, Ask: {symbol_info_tick.ask}, Spread: {spread_in_points:.1f} points")

    if spread_in_points > MAX_SPREAD_POINTS:
        print(f"{datetime.now()} - Skipping: Spread too high ({spread_in_points:.1f} points).")
        return None

    # Entry condition: Only place a trade if none is open
    positions = mt5.positions_get(symbol=SYMBOL)
    if positions and len(positions) > 0:
        print(f"{datetime.now()} - Skipping: Existing open position.")
        return None

    ha_bullish = last['ha_close'] > last['ha_open']
    ha_bearish = last['ha_close'] < last['ha_open']

    # Buy Signal
    if last['close'] < last['bb_lower'] and last['rsi'] < 30 and ha_bullish:
        return {'direction': 'buy', 'atr': last['atr']}

    # Sell Signal
    if last['close'] > last['bb_upper'] and last['rsi'] > 70 and ha_bearish:
        return {'direction': 'sell', 'atr': last['atr']}

    return None

# ---- Place Order ----
def place_order(signal):
    direction = signal['direction']
    atr = signal['atr']

    symbol_info_tick = mt5.symbol_info_tick(SYMBOL)
    symbol_info = mt5.symbol_info(SYMBOL)

    if symbol_info_tick is None or symbol_info is None:
        print(f"{datetime.now()} - Error getting symbol info for placing order.")
        return

    price = symbol_info_tick.ask if direction == 'buy' else symbol_info_tick.bid
    sl = price - atr if direction == 'buy' else price + atr
    tp = price + 1.5 * atr if direction == 'buy' else price - 1.5 * atr

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": LOT,
        "type": mt5.ORDER_TYPE_BUY if direction == 'buy' else mt5.ORDER_TYPE_SELL,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 10,
        "magic": MAGIC,
        "comment": "XAU scalping bot - ATR logic",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result is None:
        print(f"{datetime.now()} - Order send failed.")
    elif result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"{datetime.now()} - Order failed: {result.retcode}")
    else:
        print(f"{datetime.now()} - Order placed: {direction.upper()} | SL: {sl:.2f} | TP: {tp:.2f}")

# ---- Main Trading Loop ----
try:
    while True:
        df = get_data(SYMBOL, TIMEFRAME, 100)
        if df is not None and not df.empty:
            df = compute_indicators(df.copy())
            signal = check_trade_opportunity(df)
            if signal:
                place_order(signal)
        else:
            print(f"{datetime.now()} - No data available for {SYMBOL}")
        time.sleep(60)
except KeyboardInterrupt:
    print(f"{datetime.now()} - Bot stopped by user.")
finally:
    mt5.shutdown()
    print(f"{datetime.now()} - MetaTrader 5 shutdown.")
