import streamlit as st
import yfinance as yf
import pandas as pd
import requests

st.set_page_config(page_title="NSE 9/15 EMA Screener", layout="wide")

@st.cache_data(ttl=86400)
def get_all_nse_symbols():
    """Fetch official list of all listed equity stocks on NSE"""
    try:
        url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        df = pd.read_csv(pd.io.common.StringIO(response.text))
        # Add .NS suffix required by yfinance
        return [f"{sym}.NS" for sym in df["SYMBOL"].dropna().tolist()]
    except Exception:
        # Fallback list if official CSV download fails
        return [
            "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
            "BHARTIARTL.NS", "ITC.NS", "SBIN.NS", "LT.NS", "BAJFINANCE.NS"
        ]

@st.cache_data(ttl=86400)
def get_nifty_500():
    try:
        url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        df = pd.read_csv(pd.io.common.StringIO(response.text))
        return [f"{sym}.NS" for sym in df["Symbol"].dropna().tolist()]
    except Exception:
        return get_all_nse_symbols()[:500]

# Predefined buckets
WATCHLISTS = {
    "NIFTY 50": [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
        "BHARTIARTL.NS", "ITC.NS", "SBIN.NS", "LT.NS", "BAJFINANCE.NS",
        "HCLTECH.NS", "MARUTI.NS", "SUNPHARMA.NS", "TATAMOTORS.NS", "KOTAKBANK.NS",
        "AXISBANK.NS", "NTPC.NS", "TITAN.NS", "ONGC.NS", "POWERGRID.NS"
    ],
    "NIFTY Bank": [
        "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS",
        "BANKBARODA.NS", "PNB.NS", "INDUSINDBK.NS", "AUBANK.NS", "FEDERALBNK.NS"
    ]
}

def scan_stock(symbol, interval="1d"):
    try:
        data = yf.download(symbol, period="6mo", interval=interval, progress=False)
        if data.empty or len(data) < 20:
            return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [col[0] for col in data.columns]

        data["EMA_9"] = data["Close"].ewm(span=9, adjust=False).mean()
        data["EMA_15"] = data["Close"].ewm(span=15, adjust=False).mean()

        curr = data.iloc[-1]
        prev = data.iloc[-2]
        close = float(curr["Close"])
        ema9_c, ema15_c = float(curr["EMA_9"]), float(curr["EMA_15"])
        ema9_p, ema15_p = float(prev["EMA_9"]), float(prev["EMA_15"])

        bullish_cross = (ema9_p <= ema15_p) and (ema9_c > ema15_c)
        bearish_cross = (ema9_p >= ema15_p) and (ema9_c < ema15_c)
        bullish_trend = (ema9_c > ema15_c) and (close > ema9_c)
        bearish_trend = (ema9_c < ema15_c) and (close < ema9_c)

        signal = "Neutral"
        if bullish_cross:
            signal = "🚀 Bullish Crossover"
        elif bearish_cross:
            signal = "🔻 Bearish Crossover"
        elif bullish_trend:
            signal = "🟢 Strong Uptrend"
        elif bearish_trend:
            signal = "🔴 Strong Downtrend"

        return {
            "Symbol": symbol.replace(".NS", ""),
            "LTP": round(close, 2),
            "9 EMA": round(ema9_c, 2),
            "15 EMA": round(ema15_c, 2),
            "Signal": signal
        }
    except Exception:
        return None

# --- UI ---
st.title("📈 Complete NSE 9 & 15 EMA Screener")

universe_choice = st.selectbox(
    "Choose Stock Universe",
    ["NIFTY 50", "NIFTY Bank", "NIFTY 500 (Recommended)", "ALL Listed NSE Stocks (~2000)"]
)

timeframe = st.selectbox("Timeframe", ["1d", "1h", "15m", "5m"])

# Get target list based on selection
if universe_choice == "NIFTY 500 (Recommended)":
    symbols_to_scan = get_nifty_500()
elif universe_choice == "ALL Listed NSE Stocks (~2000)":
    symbols_to_scan = get_all_nse_symbols()
else:
    symbols_to_scan = WATCHLISTS[universe_choice]

max_stocks = st.slider(
    "Limit scan size (lower = faster results)", 
    min_value=10, 
    max_value=len(symbols_to_scan), 
    value=min(100, len(symbols_to_scan))
)

if st.button("Run Screener", type="primary"):
    selected_pool = symbols_to_scan[:max_stocks]
    results = []
    
    progress = st.progress(0)
    status = st.empty()
    
    for i, sym in enumerate(selected_pool):
        status.text(f"Scanning ({i+1}/{len(selected_pool)}): {sym}")
        res = scan_stock(sym, timeframe)
        if res and res["Signal"] != "Neutral":
            results.append(res)
        progress.progress((i + 1) / len(selected_pool))
        
    status.empty()
    progress.empty()

    if results:
        st.subheader(f"Matching Signals ({len(results)})")
        st.dataframe(pd.DataFrame(results), use_container_width=True)
    else:
        st.warning("No crossover or strong trend signals detected.")
        
