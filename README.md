# 📊 Investment Evaluator

**Investment Evaluator** is a command-line tool for analyzing financial instruments using technical indicators such as RSI, MACD, moving averages, and momentum (ROC).  
It calculates a buy confidence score based on these signals to help evaluate potential investment opportunities.

---

## 🚀 Features

- Analyze one or multiple stock symbols via `Yahoo! Finance`
- Adjustable scoring system based on:
  - RSI (adaptive per instrument type: stocks, ETFs, indices)
  - MA200, MA50, EMA50
  - MACD signal
  - Rate of Change (ROC)
  - Volume vs. average volume
  - Price support zone
- Filter by:
  - Minimum score (`--min-score`)
  - Market status (open/closed) with `--ignore-closed`
  - Historical period (`--period`, default: `1y`)
- Custom console color-coding for clarity
- Lightweight and fast CLI script

---

## 🧪 Example Usage

```bash
python investment_evaluator.py --symbol AAPL.US IS3N.DE NVDA --period 1y --min-score 7 --ignore-closed
```

---

## 📥 Installation

1. Clone the repository:

```bash
git clone https://github.com/your-username/investment-evaluator.git
cd investment-evaluator
```

2. Install the dependencies:

```bash
pip install yfinance ta pandas
```

---

## 📌 Parameters

| Argument         | Description                                                                 |
|------------------|-----------------------------------------------------------------------------|
| `--symbol`        | One or more stock symbols (required)                                       |
| `--period`        | Time range for historical data (e.g., `3mo`, `6mo`, `1y`, `2y`)            |
| `--min-score`     | Minimum buy confidence score required to display a result                  |
| `--ignore-closed` | If present, symbols with closed markets are skipped                        |

## ⚠️ Disclaimer

> This project is intended **for educational and informational purposes only**.  
> It **does not provide financial advice**, and must not be used as a basis for investment decisions.  
> The authors and contributors of this tool are **not financial advisors**, and they assume **no liability** for any losses or damages arising from the use of this software.  
> **There are no guarantees** regarding the accuracy, reliability, completeness, or performance of any output or analysis generated.  
> Always do your own research (DYOR) and consult a licensed professional before making financial decisions.
