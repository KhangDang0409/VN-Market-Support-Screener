import yfinance as yf
import pandas as pd
import numpy as np
from scipy.signal import argrelextrema
import datetime
import random
import warnings
import time

warnings.filterwarnings('ignore')


# ==========================================
# 1. CORE SCREENER FUNCTIONS (V4.2 PURE QUANT LOGIC)
# ==========================================
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


# ==========================================
# 2. AUTO-BACKTEST ENGINE (50 RANDOM DATES)
# ==========================================
def run_random_backtest():
    print("=" * 85)
    print("⏳ BLIND AUTO-BACKTEST ENGINE (V4.2) - 50 RANDOM HISTORICAL DATES ⏳")
    print("=" * 85)

    tickers = [
        "ACB", "BCM", "BID", "BVH", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG",
        "MBB", "MSN", "MWG", "PLX", "POW", "SAB", "SHB", "SSB", "SSI", "STB",
        "TCB", "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE",
        "VND", "VCI", "HCM", "DIG", "PDR", "DXG", "KDH", "NLG", "KBC", "IDC",
        "PVD", "PVS", "BSR", "DGC", "DCM", "HSG", "NKG", "FRT", "PNJ", "GEX"
    ]

    print("\n📥 Fetching historical market data for 50 tickers (Please wait 20-30 seconds)...")
    start_time = time.time()

    all_data = {}
    for ticker in tickers:
        df = yf.download(f"{ticker}.VN", start="2022-01-01", progress=False)
        if not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            all_data[ticker] = df.dropna()

    print(f"✅ Data fetched successfully! ({time.time() - start_time:.1f} seconds)")

    # 2. SELECT 50 RANDOM DATES
    ref_df = all_data["HPG"]
    valid_dates = ref_df.index.tolist()
    # Exclude first 150 days (needs history for POC/Valleys) and last 30 days (needs future T+20 data)
    safe_dates = valid_dates[150:-30]

    random_dates = random.sample(safe_dates, 50)
    random_dates.sort()

    print("\n🎲 Generated 50 random dates. Initializing Screener Engine...")
    print("-" * 85)

    total_signals_all_days = 0
    total_wins_all_days = 0
    days_with_signals = 0

    for i, target_date in enumerate(random_dates, 1):
        daily_signals = 0
        daily_wins = 0

        for ticker, df in all_data.items():
            # Slice the data to simulate being blind to the future
            df_past = df.loc[:target_date]
            df_future = df.loc[target_date:].iloc[1:]

            if len(df_past) < 120 or len(df_future) < 20:
                continue

            # -- APPLY STRICT V4.2 LOGIC --
            df_past_cal = df_past.copy()

            # 1. Liquidity Filter
            df_past_cal['Turnover'] = df_past_cal['Close'] * df_past_cal['Volume']
            current_adtv = df_past_cal['Turnover'].tail(20).mean() / 1e9
            if current_adtv < 20.0: continue

            # 2. Anti-Sideway Filter
            df_60d = df_past_cal.tail(60)
            high_60d = df_60d['High'].max()
            low_60d = df_60d['Low'].min()
            amplitude = (high_60d - low_60d) / low_60d
            if amplitude < 0.15: continue

            # Calculate Indicators
            df_past_cal['Vol20'] = df_past_cal['Volume'].rolling(20).mean()
            df_past_cal['RSI'] = calculate_rsi(df_past_cal['Close'])

            buy_price = df_past_cal['Close'].iloc[-1].item()
            current_vol = df_past_cal['Volume'].iloc[-1].item()
            current_rsi = df_past_cal['RSI'].iloc[-1].item()
            poc_price = calculate_volume_profile_poc(df_60d)

            signal = None

            # Setup 1: Double Bottom Bounce
            historical_valleys = find_historical_valleys(df_past_cal.tail(120).iloc[:-15])
            recent_low = df_past_cal['Low'].tail(15).min()

            is_testing_old_bottom = any((abs(recent_low - v) / v) <= 0.02 for v in historical_valleys)
            has_bounced = 1.02 <= (buy_price / recent_low) <= 1.06

            if is_testing_old_bottom and has_bounced and current_rsi < 50:
                signal = "Double Bottom Bounce"

            # Setup 2: POC Support (Gravity Logic)
            in_poc_zone = (poc_price * 0.985 <= buy_price <= poc_price * 1.03)
            recent_high = df_past_cal['High'].tail(20).max()
            came_from_above = recent_high > (poc_price * 1.04)
            not_bouncing_from_below = recent_low >= (poc_price * 0.97)

            if in_poc_zone and came_from_above and not_bouncing_from_below and not signal:
                signal = "POC Support"

            # Setup 3: Confirmed Breakout
            prev_high_60 = df_past_cal['High'].iloc[-61:-1].max().item()
            if (buy_price >= prev_high_60) and (current_vol > df_past_cal['Vol20'].iloc[-1].item() * 1.2) and (
                    current_rsi > 60) and not signal:
                signal = "Confirmed Breakout"

            # -- EVALUATE FUTURE DATA IF SIGNAL TRIGGERED --
            if signal:
                daily_signals += 1
                total_signals_all_days += 1

                df_future_eval = df_future.head(20)  # Evaluate next 20 days (T+20)
                max_gain = (df_future_eval['High'].max().item() / buy_price - 1) * 100
                final_return = (df_future_eval['Close'].iloc[-1].item() / buy_price - 1) * 100

                # Win Condition: Target > 5% reached during T+20, OR strictly profitable at close of T+20
                if max_gain >= 5.0 or final_return > 0:
                    daily_wins += 1
                    total_wins_all_days += 1

        # PRINT DAILY RESULTS
        date_str = target_date.strftime('%Y-%m-%d')
        if daily_signals > 0:
            days_with_signals += 1
            win_rate = (daily_wins / daily_signals) * 100
            print(
                f"[{i:02d}/50] Date: {date_str} | Triggers: {daily_signals} | ✅ Wins: {daily_wins} | Win Rate: {win_rate:05.1f}%")
        else:
            print(f"[{i:02d}/50] Date: {date_str} | No valid setups (Noise/Sideway successfully filtered)")

    # ==========================================
    # 4. OVERALL CAMPAIGN SUMMARY
    # ==========================================
    print("=" * 85)
    print("🏆 FINAL CAMPAIGN REPORT: 50-DAY BLIND BACKTEST 🏆")
    print("=" * 85)
    print(f"📌 Total random dates tested: 50")
    print(f"📌 Days with active signals: {days_with_signals} days")
    print(f"📌 Total trades executed: {total_signals_all_days} trades")

    if total_signals_all_days > 0:
        final_win_rate = (total_wins_all_days / total_signals_all_days) * 100
        print(f"✅ Total Winning Trades: {total_wins_all_days}")
        print(f"🚀 AVERAGE WIN RATE: {final_win_rate:.1f}%")
        print(
            "\n*Note: A trade is considered a 'Win' if max gain > 5% within T+20 (allowing take-profit) OR if the final return after 20 days is strictly > 0.*")
    else:
        print("No trades triggered across all 50 days. The filters might be exceptionally strict.")


if __name__ == "__main__":
    run_random_backtest()