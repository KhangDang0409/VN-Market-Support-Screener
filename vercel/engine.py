"""Original screening arithmetic; only Streamlit UI/cache removed."""
import datetime
import numpy as np
import pandas as pd
import yfinance as yf
from scipy.signal import argrelextrema

def calculate_rsi(data, periods=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1 / periods, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1 / periods, adjust=False).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_volume_profile_poc(df, bins=20):
    hist, bin_edges = np.histogram(df['Close'], bins=bins, weights=df['Volume'])
    poc_idx = np.argmax(hist)
    return (bin_edges[poc_idx] + bin_edges[poc_idx + 1]) / 2

def find_historical_valleys(df, order=10):
    local_min_idx = argrelextrema(df['Close'].values, np.less, order=order)[0]
    valleys = df['Close'].iloc[local_min_idx]
    historical_valleys = valleys[valleys.index < (df.index[-1] - pd.Timedelta(days=10))]
    return historical_valleys.values

def process_market_data(tickers, adtv_threshold):
    results = []
    start_date = datetime.date.today() - datetime.timedelta(days=365)
    for ticker in tickers:
        ticker_vn = f"{ticker}.VN" if not ticker.endswith('.VN') else ticker
        df = yf.download(ticker_vn, start=start_date, progress=False)
        if df.empty or len(df) < 120: continue
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df = df.dropna()
        df['Turnover'] = df['Close'] * df['Volume']
        current_adtv = df['Turnover'].tail(20).mean() / 1e9
        if current_adtv < adtv_threshold: continue
        df_60d = df.tail(60)
        high_60d = df_60d['High'].max()
        low_60d = df_60d['Low'].min()
        amplitude = (high_60d - low_60d) / low_60d
        if amplitude < 0.15: continue
        df['Vol20'] = df['Volume'].rolling(20).mean()
        df['RSI'] = calculate_rsi(df['Close'])
        current_price = df['Close'].iloc[-1].item()
        current_vol = df['Volume'].iloc[-1].item()
        current_rsi = df['RSI'].iloc[-1].item()
        poc_price = calculate_volume_profile_poc(df_60d)
        signal = None
        support_level = poc_price
        historical_valleys = find_historical_valleys(df.tail(120).iloc[:-15])
        recent_low = df['Low'].tail(15).min()
        is_testing_old_bottom = any((abs(recent_low - v) / v) <= 0.02 for v in historical_valleys)
        has_bounced = 1.02 <= (current_price / recent_low) <= 1.06
        if is_testing_old_bottom and has_bounced and current_rsi < 50:
            signal = '🟢 Double Bottom Bounce'
            support_level = recent_low
        in_poc_zone = (poc_price * 0.985 <= current_price <= poc_price * 1.03)
        recent_high = df['High'].tail(20).max()
        came_from_above = recent_high > (poc_price * 1.04)
        not_bouncing_from_below = recent_low >= (poc_price * 0.97)
        if in_poc_zone and came_from_above and not_bouncing_from_below and not signal:
            signal = '🟡 POC Support'
            support_level = poc_price
        prev_high_60 = df['High'].iloc[-61:-1].max().item()
        if (current_price >= prev_high_60) and (current_vol > df['Vol20'].iloc[-1].item() * 1.2) and (current_rsi > 60) and not signal:
            signal = '🔥 Confirmed Breakout'
            support_level = prev_high_60
        if signal:
            distance_to_support = abs(current_price - support_level) / support_level
            ticker_clean = ticker.replace('.VN', '')
            results.append({'Ticker': ticker_clean, 'Price': round(current_price, 2), 'Setup': signal, 'Support Level': round(support_level, 2), 'Distance': f'{int(distance_to_support * 100)} %', 'Liquidity': round(current_adtv, 1), 'Chart': f'https://fireant.vn/dashboard/content/symbols/{ticker_clean}'})
    return pd.DataFrame(results)
