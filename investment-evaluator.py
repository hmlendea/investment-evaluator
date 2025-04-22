import yfinance as yf
import pandas as pd
import ta
import argparse

# Setup argparse
parser = argparse.ArgumentParser(description="Analysis for financial symbols.")

parser.add_argument("--symbol", type=str, nargs="+", required=True, help="Symbols list")
parser.add_argument("--period", type=str, default="1y", help="Data period for historical prices (e.g. 3mo, 6mo, 1y)")
parser.add_argument("--ignore-closed", action="store_true", help="Ignore symbols with closed markets")
parser.add_argument("--min-score", type=int, default=0, help="Minimum score required to display a symbol")

args = parser.parse_args()

def calculate_buy_confidence_score(data_frame, price, ma200, rsi14, instrument_type):
    score = 0

    # --- MA200 scoring (0–3)
    ma200_ratio = price / ma200
    if 0.97 <= ma200_ratio <= 1.00:
        score += 3
    elif 0.93 <= ma200_ratio < 0.97:
        score += 2
    elif 0.88 <= ma200_ratio < 0.93:
        score += 1

    # --- RSI scoring (0–3) + penalty if overbought
    if instrument_type == "ETF":
        if 35 <= rsi14 < 40:
            score += 3
        elif 40 <= rsi14 <= 45:
            score += 2
        elif 45 <= rsi14 <= 50:
            score += 1
    elif instrument_type == "IDX":
        if 35 <= rsi14 < 42:
            score += 2
        elif 42 <= rsi14 <= 50:
            score += 1
    else:
        if 30 <= rsi14 < 35:
            score += 3
        elif 35 <= rsi14 < 40:
            score += 2
        elif 40 <= rsi14 <= 45:
            score += 1
    if rsi14 > 70:
        score -= 1  # Potential overbought condition

    # --- Volume scoring (0–1)
    volume_ma20 = data_frame["Volume"].rolling(window=20).mean().iloc[-1]
    current_volume = data_frame["Volume"].iloc[-1]
    if current_volume >= volume_ma20:
        score += 1

    # --- Combined MA50 and EMA50 logic (0–1)
    # Only score if both trend and recent momentum are aligned
    ma50_series = data_frame["Close"].rolling(window=50).mean()
    ma50 = ma50_series.iloc[-1]
    ema50 = data_frame["Close"].ewm(span=50).mean().iloc[-1]
    if price > ema50 and ma50 > ma200:
        score += 1

    # --- Price above recent support (0–1)
    recent_low = data_frame["Close"].tail(10).min()
    if price > recent_low * 1.02:
        score += 1

    # --- MACD signal (0–2)
    macd_indicator = ta.trend.MACD(close=data_frame["Close"])
    macd_line = macd_indicator.macd().iloc[-1]
    signal_line = macd_indicator.macd_signal().iloc[-1]
    if macd_line > signal_line:
        score += 2

    # --- ROC (0–1)
    roc = ta.momentum.ROCIndicator(close=data_frame["Close"], window=10).roc().iloc[-1]
    if roc > 2:
        score += 1

    # --- EMA200 (0–1)
    ema200 = data_frame["Close"].ewm(span=200).mean().iloc[-1]
    if price > ema200:
        score += 1

    # --- ATR (0–1) – if volatility is reasonable
    atr = ta.volatility.AverageTrueRange(
        high=data_frame["High"],
        low=data_frame["Low"],
        close=data_frame["Close"],
        window=14
    ).average_true_range().iloc[-1]
    atr_percent = atr / price
    if 0.01 < round(atr_percent, 4) < 0.03:
        score += 1

    # --- Golden Cross recently (0–1)
    if len(ma50_series.dropna()) > 5 and len(data_frame["Close"].rolling(window=200).mean().dropna()) > 5:
        past_ma50 = ma50_series.shift(5).iloc[-1]
        past_ma200 = data_frame["Close"].rolling(window=200).mean().shift(5).iloc[-1]
        if past_ma50 < past_ma200 and ma50 > ma200:
            score += 1

    # --- Bollinger Band width (0–1)
    # Low BB width suggests volatility contraction — potential breakout (not directional)
    bb = ta.volatility.BollingerBands(close=data_frame["Close"], window=20, window_dev=2)
    band_width = (bb.bollinger_hband() - bb.bollinger_lband()) / data_frame["Close"]
    if band_width.iloc[-1] < 0.05:
        score += 1

    return score

def get_confidence_level(score):
    if score >= 15:
        return 4
    elif score >= 13:
        return 3
    elif score >= 10:
        return 2
    elif score >= 7:
        return 1
    else:
        return 0

def get_confidence_colour(confidence_level):
    if confidence_level == 4:
        return "&a"

    if confidence_level == 3:
        return "&2"

    if confidence_level == 2:
        return "&e"

    if confidence_level == 1:
        return "&6"

    return "&c"

def get_recommendation(confidence_level):
    if confidence_level == 4:
        return "Buy (Very High confidence)"
    elif confidence_level == 3:
        return "Buy (High confidence)"
    elif confidence_level == 2:
        return "Buy (Medium confidence)"
    elif confidence_level == 1:
        return "Buy (Low confidence)"
    else:
        return "Do not buy"

def generate_score_bar(score, max_score = 17):
    filled = "▇" * score
    empty = "░" * (max_score - score)
    return filled + empty

def get_market_state(stock_info):
    market_state = stock_info.get("marketState", "UNKNOWN")

    if market_state == "REGULAR":
        return "Open"
    elif market_state == "PRE":
        return "Pre-opening"
    else:
        return "Closed"

def get_market_state_colour(market_state):
    if market_state == 'Open':
        return "&2"
    elif market_state == 'Pre-opening':
        return "&e"
    else:
        return "&c"

def get_instrument_name(stock_info):
    long_name = stock_info.get("longName", "Unknown")

    long_name = long_name.replace(", Inc", " Inc")
    long_name = long_name.replace("plc", "PLC")
    long_name = long_name.removesuffix(" ETF")
    long_name = long_name.removesuffix(" ETF Shares")
    long_name = long_name.removesuffix(".")

    return long_name


def get_instrument_type(stock_info):
    quote_type = stock_info.get("quoteType", "unknown");

    if quote_type == "EQUITY":
        return "STC"
    elif quote_type == "INDEX":
        return "IDX"
    else:
        return quote_type

def get_moving_average(data_frame, window):
    mean = data_frame["Close"].rolling(window=window).mean()
    return mean.iloc[-1]

def get_relative_strength_index(data_frame, window):
    rsi = ta.momentum.RSIIndicator(close=data_frame["Close"], window=window).rsi()
    return rsi.iloc[-1]

def get_yahoo_finance_symbol(symbol):
    symbol = symbol.upper()

    map = {
        "VOW1.DE": "VOW3.DE"
    }

    symbol = symbol.replace(".FR", ".PA")
    symbol = symbol.replace(".IT", ".MI")
    symbol = symbol.replace(".UK", ".L")
    symbol = symbol.replace(".US", "")

    return map.get(symbol, symbol).upper()

def analyse_symbol(symbol, period):
    symbol = symbol.upper()
    yfinance_symbol = get_yahoo_finance_symbol(symbol)

    try:
        stock = yf.Ticker(yfinance_symbol)
        price = stock.history(period="1d")["Close"].iloc[-1]

        data_frame = stock.history(period=period)
        data_frame.dropna(inplace=True)
    except Exception as ex:
        print(f"Error analyzing symbol {symbol}: {ex}")
        return

    if args.ignore_closed and stock.info.get("marketState", "UNKNOWN") != "REGULAR":
        return

    instrument_type = get_instrument_type(stock.info)
    ma200 = get_moving_average(data_frame, 200)
    rsi14 = get_relative_strength_index(data_frame, 14)

    buy_confidence_score = calculate_buy_confidence_score(data_frame, price, ma200, rsi14, instrument_type)

    if buy_confidence_score >= args.min_score:
        display_results(symbol, stock.info, price, ma200, rsi14, buy_confidence_score);

def display_results(symbol, stock_info, price, ma200, rsi14, confidence_score):
    market_state = get_market_state(stock_info)
    market_state_colour = get_market_state_colour(market_state)
    confidence_level = get_confidence_level(confidence_score)
    confidence_colour = get_confidence_colour(confidence_level)

    instrument_name = get_instrument_name(stock_info)
    instrument_type = get_instrument_type(stock_info)
    currency = stock_info.get("currency", "???")
    ma200_percent = (ma200 / price) * 100
    score_max = 17
    score_bar = generate_score_bar(confidence_score, score_max)

    print_line(f"Analysis for the {market_state_colour}{market_state} &f{symbol} {instrument_type} &8({instrument_name})&r:")
    print_line(f"  Price: &f{price:.2f} &r{currency}")
    print_line(f"  MA200: &f{ma200:.2f} &r{currency} &8({ma200_percent:.2f}%)")
    print_line(f"  RSI14: &f{rsi14:.2f}")
    print_line(f"  Score: {confidence_colour}{score_bar} &8({confidence_score}/{score_max})")

    if rsi14 > 70:
        print_line(f"  &6⚠️ RSI is high! Asset might be overbought.")

    if market_state == 'Open':
        recommendation = get_recommendation(confidence_level)
        print_line(f"  Recommendation: {confidence_colour}{recommendation}")
    else:
        print_line(f"  Recommendation: N/A &8(Closed market)")
    
def print_line(message):
    message = message.replace("&r", "&7")
    message = message.replace("&2", "\033[32m")
    message = message.replace("&4", "\033[31m")
    message = message.replace("&6", "\033[33m")
    message = message.replace("&7", "\033[37m")
    message = message.replace("&8", "\033[90m")
    message = message.replace("&a", "\033[92m")
    message = message.replace("&c", "\033[91m")
    message = message.replace("&e", "\033[93m")
    message = message.replace("&f", "\033[0m")

    print(f"\033[37m{message}\033[0m")

for symbol in args.symbol:
    analyse_symbol(symbol, args.period)
