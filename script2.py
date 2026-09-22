import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.signal import argrelextrema
import datetime
import warnings

warnings.filterwarnings('ignore')

# --- PAGE CONFIG ---
st.set_page_config(page_title="VN Market Support Screener", page_icon="🤑", layout="wide")

st.title("VN Market Support Screener")

st.markdown("""
Built by **Khang Dang**.

The algorithm automatically filters out low-liquidity stocks (< 20B VND/day) and dead sideway trends (60-day amplitude < 15%). A signal is triggered only when a stock meets strict mathematical support rules: either safely landing on a Volume Profile Support (within ±3% of POC), successfully bouncing 2%-6% from a historical double bottom, or confirming a breakout with a +20% volume surge.

This tool was first designed and run on terminal in 2025 for personal use. The motive was to save time going through multiple tickers to find solid entry points. Finding the tool effective, I decided to share it to my fellow traders. This screening tool is designed exclusively for information filtering and does not constitute investment advice. Any final decision to execute a stock purchase rests entirely with the user.
""")
st.divider()


# --- MATH & QUANT FUNCTIONS ---
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


# --- DATA PROCESSING ---
@st.cache_data(ttl=900)
def process_market_data(tickers, adtv_threshold):
    results = []
    start_date = datetime.date.today() - datetime.timedelta(days=365)

    for ticker in tickers:
        ticker_vn = f"{ticker}.VN" if not ticker.endswith(".VN") else ticker
        df = yf.download(ticker_vn, start=start_date, progress=False)

        if df.empty or len(df) < 120: continue

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)

        df = df.dropna()

        # 1. Liquidity Filter
        df['Turnover'] = df['Close'] * df['Volume']
        current_adtv = df['Turnover'].tail(20).mean() / 1e9
        if current_adtv < adtv_threshold: continue

        # 2. Anti-Sideway Filter
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

        # ==========================================
        # SETUP 1: DOUBLE BOTTOM BOUNCE
        # ==========================================
        historical_valleys = find_historical_valleys(df.tail(120).iloc[:-15])
        recent_low = df['Low'].tail(15).min()

        is_testing_old_bottom = any((abs(recent_low - v) / v) <= 0.02 for v in historical_valleys)
        has_bounced = 1.02 <= (current_price / recent_low) <= 1.06

        if is_testing_old_bottom and has_bounced and current_rsi < 50:
            signal = "🟢 Double Bottom Bounce"
            support_level = recent_low

            # ==========================================
        # SETUP 2: POC SUPPORT
        # ==========================================
        in_poc_zone = (poc_price * 0.985 <= current_price <= poc_price * 1.03)
        recent_high = df['High'].tail(20).max()
        came_from_above = recent_high > (poc_price * 1.04)
        not_bouncing_from_below = recent_low >= (poc_price * 0.97)

        if in_poc_zone and came_from_above and not_bouncing_from_below and not signal:
            signal = "🟡 POC Support"
            support_level = poc_price

        # ==========================================
        # SETUP 3: CONFIRMED BREAKOUT
        # ==========================================
        prev_high_60 = df['High'].iloc[-61:-1].max().item()
        if (current_price >= prev_high_60) and (current_vol > df['Vol20'].iloc[-1].item() * 1.2) and (
                current_rsi > 60) and not signal:
            signal = "🔥 Confirmed Breakout"
            support_level = prev_high_60

            # ==========================================
        # SAVE RESULTS
        # ==========================================
        if signal:
            distance_to_support = abs(current_price - support_level) / support_level
            ticker_clean = ticker.replace(".VN", "")

            results.append({
                "Ticker": ticker_clean,
                "Price": round(current_price, 2),
                "Setup": signal,
                "Support Level": round(support_level, 2),
                "Distance": f"{int(distance_to_support * 100)} %",
                "Liquidity": round(current_adtv, 1),
                "Chart": f"https://fireant.vn/dashboard/content/symbols/{ticker_clean}"
            })

    return pd.DataFrame(results)


# --- SIDEBAR CONFIG ---
with st.sidebar:
    st.header("⚙️ Screener Settings")
    default_tickers = "ACB, BCM, BID, BVH, CTG, FPT, GAS, GVR, HDB, HPG, MBB, MSN, MWG, PLX, POW, SAB, SHB, SSB, SSI, STB, TCB, TPB, VCB, VHM, VIB, VIC, VJC, VNM, VPB, VRE, VND, VCI, HCM, DIG, PDR, DXG, KDH, NLG, KBC, IDC, PVD, PVS, BSR, DGC, DCM, HSG, NKG, FRT, PNJ, GEX"
    tickers_input = st.text_area("Ticker List:", value=default_tickers)
    tickers_list = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

    adtv_threshold = st.number_input("Min Liquidity (Bil VND):", min_value=1.0, value=20.0, step=5.0)
    run_btn = st.button("Run Screener", type="primary", use_container_width=True)

# --- MAIN DISPLAY ---
if run_btn:
    if not tickers_list:
        st.warning("Please enter at least one ticker.")
    else:
        with st.spinner("Scanning the market..."):
            result_df = process_market_data(tickers_list, adtv_threshold)

        if result_df.empty:
            st.info("No tickers meet the criteria at the moment. Standing by.")
        else:
            st.success(f"Found {len(result_df)} tickers meeting the criteria.")

            st.dataframe(
                result_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Setup": st.column_config.TextColumn("Setup"),
                    "Liquidity": st.column_config.NumberColumn("Liquidity (Bil VND)", format="%.1f"),
                    "Chart": st.column_config.LinkColumn("View Chart", display_text="Fireant Link")
                }
            )

            st.markdown("### Top Ticker Chart")
            top_ticker = result_df.iloc[0]['Ticker']
            df_chart = yf.download(f"{top_ticker}.VN", period="6mo", progress=False)
            if isinstance(df_chart.columns, pd.MultiIndex):
                df_chart.columns = df_chart.columns.droplevel(1)

            fig = go.Figure(data=[go.Candlestick(x=df_chart.index,
                                                 open=df_chart['Open'], high=df_chart['High'],
                                                 low=df_chart['Low'], close=df_chart['Close'],
                                                 name="Price")])

            support_level_chart = result_df.iloc[0]['Support Level']
            fig.add_hline(y=support_level_chart, line_dash="dash", line_color="rgba(0, 255, 127, 0.8)",
                          annotation_text="Support / Stoploss Level")
            fig.update_layout(template="plotly_dark", height=500, margin=dict(l=0, r=0, t=30, b=0),
                              xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
else:
    st.info("👈 Click 'Run Screener' in the sidebar to start.")