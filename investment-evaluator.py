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

    # --- RSI scoring (0–3) adaptiv
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

    # --- Volume scoring (0–1)
    volume_ma20 = data_frame["Volume"].rolling(window=20).mean().iloc[-1]
    current_volume = data_frame["Volume"].iloc[-1]
    if current_volume >= volume_ma20:
        score += 1

    # --- MA50 > MA200 scoring (0–1)
    ma50_series = data_frame["Close"].rolling(window=50).mean()
    ma50 = ma50_series.iloc[-1]
    if ma50 > ma200:
        score += 1

    # --- Price above recent support (0–1)
    recent_low = data_frame["Close"].tail(10).min()
    if price > recent_low * 1.02:
        score += 1

    # --- EMA50 scoring (0–1)
    ema50 = data_frame["Close"].ewm(span=50).mean().iloc[-1]
    if price > ema50:
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

    # --- ATR (0–1) – dacă volatilitatea e rezonabilă
    atr = ta.volatility.AverageTrueRange(high=data_frame["High"],
                                         low=data_frame["Low"],
                                         close=data_frame["Close"],
                                         window=14).average_true_range().iloc[-1]
    if atr < price * 0.02:  # ATR < 2% din preț => volatilitate mică = +1
        score += 1

    # --- Golden Cross recent (0–1)
    past_ma50 = ma50_series.shift(5).iloc[-1]
    past_ma200 = data_frame["Close"].rolling(window=200).mean().shift(5).iloc[-1]
    if past_ma50 < past_ma200 and ma50 > ma200:
        score += 1

    # --- Bollinger Band width (0–1)
    bb = ta.volatility.BollingerBands(close=data_frame["Close"], window=20, window_dev=2)
    band_width = (bb.bollinger_hband() - bb.bollinger_lband()) / data_frame["Close"]
    if band_width.iloc[-1] < 0.05:  # <5% => compresie mare, posibil breakout
        score += 1

    return score

def get_formatted_recommendation(market_state, score):
    if market_state == "Open":
        if score >= 15:
            recommendation = "Buy (Very High confidence)"
            recommendation_colour = "&a"
        elif score >= 13:
            recommendation = "Buy (High confidence)"
            recommendation_colour = "&2"
        elif score >= 10:
            recommendation = "Buy (Medium confidence)"
            recommendation_colour = "&e"
        elif score >= 7:
            recommendation = "Buy (Low confidence)"
            recommendation_colour = "&6"
        else:
            recommendation = "Do not buy"
            recommendation_colour = "&c"
    else:
        recommendation = "N/A (Closed market)"
        recommendation_colour = "&r"

    return f"{recommendation_colour}{recommendation}&r"

def get_market_state(stock_info):
    market_state = stock_info.get("marketState", "UNKNOWN")

    if market_state == "REGULAR":
        return "Open"
    elif market_state == "PRE":
        return "Pre-opening"
    else:
        return "Closed"

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
        "LDO.IT": "LDO.MI",
        "VOW1.DE": "VOW3.DE"
    }

    symbol = symbol.replace(".FR", ".PA")
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

def display_results(symbol, stock_info, price, ma200, rsi14, buy_confidence_score):
    market_state = get_market_state(stock_info)
    recommendation = get_formatted_recommendation(market_state, buy_confidence_score)

    if market_state == 'Open':
        market_state_colour = "&2"
    elif market_state == 'Pre-opening':
        market_state_colour = "&e"
    else:
        market_state_colour = "&c"

    instrument_name = get_instrument_name(stock_info)
    instrument_type = get_instrument_type(stock_info)
    currency = stock_info.get("currency", "???")
    ma200_percent = (ma200 / price) * 100

    print_line(f"Analysis for the {market_state_colour}{market_state} &f{symbol} {instrument_type} &8({instrument_name})&r:")
    print_line(f"  Price: &f{price:.2f} &r{currency}")
    print_line(f"  MA200: &f{ma200:.2f} &r{currency} &8({ma200_percent:.2f}%)")
    print_line(f"  RSI14: &f{rsi14:.2f}")
    print_line(f"  Score: &f{buy_confidence_score}&r/17")

    if rsi14 > 70:
        print_line(f"  &6⚠️ RSI is high! Asset might be overbought.")

    print_line(f"  Recommendation: {recommendation}")

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
