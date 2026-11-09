# VN Market Support Screener (V4.2)

## Overview
The VN Market Support Screener is a quantitative filtering engine built for the Vietnamese stock market (HOSE/HNX). Originally designed as a personal terminal tool in 2025 to eliminate the noise of manual charting, it has been scaled into a Streamlit web application. 

This is **not** a prediction tool. It is a strict, rule-based mathematical algorithm that filters out low-liquidity assets and "dead" sideways trends, triggering signals only when a stock meets highly specific technical setups: a Volume Profile Support bounce, a historical Double Bottom validation, or a Confirmed Volume Breakout.

## Core Features & Filtering Logic

### 1. Pre-Screening Filters (Noise Reduction)
Before any technical setups are evaluated, the engine enforces strict baseline requirements:
* **Liquidity Filter:** Rejects stocks with an Average Daily Trading Volume (ADTV) below 20 billion VND to prevent slippage and trap risks.
* **Anti-Sideway Filter:** Rejects stocks lacking momentum by calculating the 60-day price amplitude. If the amplitude `(High - Low) / Low` is less than 15%, the stock is ignored.

### 2. Quantitative Setups (Signal Triggers)
A ticker is only flagged if it strictly satisfies one of three mathematical conditions:
* **Volume Profile POC Support:** Calculates the Point of Control (POC) over a 60-day period. Triggers if the current price lands within a strict ±3% zone of the POC, provided the price dropped from above (not a rejection from below).
* **Double Bottom Bounce:** Uses `scipy.signal.argrelextrema` to find local minimums over the past 120 days. Triggers if the current price tests an old valley (within a 2% margin) and has already bounced 2% - 6% with an RSI < 50.
* **Confirmed Breakout:** Triggers if the price breaches the 60-day high accompanied by a volume surge (> 120% of the 20-day moving average volume) and an RSI > 60.

## Auto-Backtest Engine (Blind Simulation)
To prove the algorithm's statistical edge, the project includes a standalone Python backtesting engine (`run_random_backtest`). 

Instead of cherry-picking a specific bull run, the engine runs a **Blind 50-Day Random Simulation**:
1. Fetches historical data (2022-Present) for a basket of 50 major VN30 and mid-cap tickers.
2. Selects **50 random historical dates** from the dataset.
3. For each date, it slices the dataframe to simulate being completely blind to the future (T+0).
4. Applies the strict V4.2 screener logic to see which tickers would have triggered a signal on that exact day.
5. Evaluates the actual future data (T+20). 

**Win Condition:**
A triggered setup is statistically recorded as a "Win" if:
* The stock achieves a maximum gain of **> 5% within the T+20 window** (allowing a realistic take-profit).
* OR the final return strictly remains **> 0% at the close of T+20**.

## Tech Stack
* **Python:** Core engine.
* **Streamlit:** Frontend web dashboard.
* **yfinance:** Market data retrieval (VN tickers formatted via Yahoo Finance mapping).
* **NumPy / Pandas:** Data manipulation and Vectorized calculations.
* **SciPy:** Mathematical local extrema detection (`argrelextrema`).
* **Plotly:** Interactive candlestick charting and support level rendering.

Vercel link: https://vn-market-support-screener.vercel.app

Streamlit link: https://vn-market-support-screener.streamlit.app
