import os
import telebot
import requests
import pandas as pd
import ta
from dotenv import load_dotenv

# =========================
# ENV SETUP
# =========================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_KEY = os.getenv("API_KEY")

if not BOT_TOKEN:
    raise Exception("Missing BOT_TOKEN in Railway Variables")

bot = telebot.TeleBot(BOT_TOKEN)

print("🧠 SMC BOT RUNNING (CLEAN VERSION)")

# =========================
# GET MARKET DATA
# =========================
def get_data(symbol):
    try:
        url = "https://api.twelvedata.com/time_series"

        params = {
            "symbol": symbol,
            "interval": "1min",
            "outputsize": 80,
            "apikey": API_KEY
        }

        r = requests.get(url, timeout=10).json()

        if "values" not in r:
            print("API ERROR:", r)
            return None

        df = pd.DataFrame(r["values"])

        if df.empty:
            return None

        df["open"] = df["open"].astype(float)
        df["close"] = df["close"].astype(float)
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)

        return df[::-1]

    except Exception as e:
        print("GET DATA ERROR:", e)
        return None

# =========================
# INDICATORS
# =========================
def indicators(df):
    df["ema20"] = ta.trend.ema_indicator(df["close"], 20)
    df["ema50"] = ta.trend.ema_indicator(df["close"], 50)
    df["rsi"] = ta.momentum.rsi(df["close"], 14)
    return df

# =========================
# SMART MONEY LOGIC
# =========================
def liquidity_sweep(df):
    high = df["high"].tail(20).max()
    low = df["low"].tail(20).min()

    price = df["close"].iloc[-1]
    prev_close = df["close"].iloc[-2]

    if price > high and prev_close < high:
        return "BUY SWEEP 🔥"

    if price < low and prev_close > low:
        return "SELL SWEEP 🔻"

    return "NO SWEEP ⚪"


def fvg(df):
    try:
        for i in range(2, len(df)):
            if df["low"].iloc[i] > df["high"].iloc[i-2]:
                return "FVG UP 🟢"

            if df["high"].iloc[i] < df["low"].iloc[i-2]:
                return "FVG DOWN 🔴"

        return "NO FVG ⚪"
    except:
        return "NO FVG ⚪"


def trend(df):
    last = df.iloc[-1]

    if last["ema20"] > last["ema50"]:
        return "UPTREND 📈"
    elif last["ema20"] < last["ema50"]:
        return "DOWNTREND 📉"
    return "SIDEWAYS ⚪"


def bos(df):
    high = df["high"].tail(15).max()
    low = df["low"].tail(15).min()
    price = df["close"].iloc[-1]

    if price > high:
        return "BOS UP 🚀"
    elif price < low:
        return "BOS DOWN 🔻"
    return "NO BOS ⚪"


def signal(df):
    last = df.iloc[-1]
    sweep = liquidity_sweep(df)

    buy = (
        "BUY SWEEP" in sweep and
        last["ema20"] > last["ema50"] and
        last["rsi"] > 55
    )

    sell = (
        "SELL SWEEP" in sweep and
        last["ema20"] < last["ema50"] and
        last["rsi"] < 45
    )

    if buy:
        return "BUY 📈 (SMC ENTRY)"
    if sell:
        return "SELL 📉 (SMC ENTRY)"
    return "NO TRADE ⚪"


def format_msg(pair, price, sig, tr, bos_signal, sweep, fvg_signal):
    return f"""
🧠 SMC LEVEL 2 BOT

Pair: {pair}
Price: {price}

Trend: {tr}
Structure: {bos_signal}
Liquidity: {sweep}
FVG: {fvg_signal}

Signal: {sig}
"""

# =========================
# START COMMAND
# =========================
@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(message, """
🧠 SMART MONEY BOT READY

Commands:
/eurusd
/gbpusd
/gold
""")

# =========================
# HANDLER FUNCTION
# =========================
def process_pair(message, symbol, name):
    df = get_data(symbol)

    if df is None:
        bot.reply_to(message, "❌ Market error")
        return

    df = indicators(df)

    price = df["close"].iloc[-1]
    sig = signal(df)
    tr = trend(df)
    bos_signal = bos(df)
    sweep = liquidity_sweep(df)
    fvg_signal = fvg(df)

    bot.reply_to(message, format_msg(name, price, sig, tr, bos_signal, sweep, fvg_signal))

# =========================
# COMMANDS
# =========================
@bot.message_handler(commands=["eurusd"])
def eurusd(message):
    process_pair(message, "EUR/USD", "EURUSD")

@bot.message_handler(commands=["gbpusd"])
def gbpusd(message):
    process_pair(message, "GBP/USD", "GBPUSD")

@bot.message_handler(commands=["gold"])
def gold(message):
    process_pair(message, "XAU/USD", "GOLD")

# =========================
# FALLBACK HANDLER (FIX FOR YOUR ERROR)
# =========================
@bot.message_handler(content_types=['text'])
def fallback(message):
    bot.reply_to(message, "📊 Use /eurusd /gbpusd /gold")

# =========================
# RUN BOT (SAFE LOOP)
# =========================
while True:
    try:
        bot.infinity_polling(skip_pending=True)
    except Exception as e:
        print("BOT RESTARTING:", e)
