import streamlit as st
import yfinance as yf
import pandas as pd

st.set_page_config(page_title="NSE 9/15 EMA Screener", layout="wide")

WATCHLISTS = {
    "NIFTY 50 (Sample)": [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
        "BHARTIARTL.NS", "ITC.NS", "SBIN.NS", "LT.NS", "BAJFINANCE.NS"
    ],
    "NIFTY Bank": [
        "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS"
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

        if (ema9_p <= ema15_p) and (ema9_c > ema15_c):
            signal = "🚀 Bullish Crossover"
        elif (ema9_p >= ema15_p) and (ema9_c < ema15_c):
            signal = "🔻 Bearish Crossover"
        elif (ema9_c > ema15_c) and (close > ema9_c):
            signal = "🟢 Strong Uptrend"
        elif (ema9_c < ema15_c) and (close < ema9_c):
            signal = "🔴 Strong Downtrend"
        else:
            signal = "Neutral"

        return {
            "Symbol": symbol.replace(".NS", ""),
            "LTP": round(close, 2),
            "9 EMA": round(ema9_c, 2),
            "15 EMA": round(ema15_c, 2),
            "Signal": signal
        }
    except Exception:
        return None

st.title("📈 NSE 9 & 15 EMA Screener")
wl = st.selectbox("Select Watchlist", list(WATCHLISTS.keys()))
timeframe = st.selectbox("Timeframe", ["1d", "1h", "15m", "5m"])

if st.button("Run Screener", type="primary"):
    results = []
    with st.spinner("Scanning stocks..."):
        for sym in WATCHLISTS[wl]:
            res = scan_stock(sym, timeframe)
            if res:
                results.append(res)
    if results:
        st.dataframe(pd.DataFrame(results), use_container_width=True)
    else:
        st.warning("No data found.")
  
