import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import requests

st.set_page_config(page_title="NSE Live Screener (India IST)", layout="wide")

# Fetch all listed equities from official NSE archives
@st.cache_data(ttl=86400)
def get_all_symbols():
    try:
        url = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=15)
        df = pd.read_csv(pd.io.common.StringIO(resp.text))
        eq_df = df[df[" SERIES"].str.strip() == "EQ"] if " SERIES" in df.columns else df
        symbols = sorted(list(set([sym.strip() for sym in eq_df["SYMBOL"].dropna().tolist()])))
        return symbols
    except Exception:
        return sorted([
            "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "BHARTIARTL", 
            "ITC", "SBIN", "LT", "BAJFINANCE", "HCLTECH", "MARUTI", "SUNPHARMA",
            "TATAMOTORS", "KOTAKBANK", "AXISBANK", "NTPC", "TITAN", "POWERGRID"
        ])

# Unrestricted Real-Time Chart (No "only available on TradingView" popup)
def render_live_chart(symbol, interval="5m"):
    clean_sym = symbol.replace("NSE:", "").replace(".NS", "").strip()

    # Map spot index tickers that trigger the TradingView popup to safe equivalents
    INDEX_SAFE_MAP = {
        "NIFTY": "NIFTY1!",
        "BANKNIFTY": "BANKNIFTY1!",
        "CNXIT": "CNXIT",
        "SENSEX": "RELIANCE"
    }
    target_ticker = INDEX_SAFE_MAP.get(clean_sym, clean_sym)

    tf_map = {"1m": "1", "5m": "5", "15m": "15", "1h": "60", "1d": "D"}
    tv_tf = tf_map.get(interval, "5")

    # Pure widget iframe embed bypasses the symbol-lock dialog
    embed_url = (
        f"https://s.tradingview.com/widgetembed/?"
        f"frameElementId=tradingview_widget"
        f"&symbol=NSE%3A{target_ticker}"
        f"&interval={tv_tf}"
        f"&hidesidetoolbar=0"
        f"&symboledit=1"
        f"&saveimage=1"
        f"&toolbarbg=f1f3f6"
        f"&studies=%5B%7B%22id%22%3A%22MAExp%40tv-basicstudies%22%2C%22inputs%22%3A%7B%22length%22%3A9%7D%7D%2C%7B%22id%22%3A%22MAExp%40tv-basicstudies%22%2C%22inputs%22%3A%7B%22length%22%3A15%7D%7D%5D"
        f"&theme=dark"
        f"&style=1"
        f"&timezone=Asia%2FKolkata"
    )

    components.iframe(embed_url, height=650, scrolling=True)

# Batch scanner for 9 EMA > 15 EMA
def scan_batch(symbols, interval="15m"):
    tickers = [f"{s}.NS" for s in symbols]
    period = "1mo" if interval in ["1m", "5m", "15m", "1h"] else "3mo"
    
    data = yf.download(
        tickers=" ".join(tickers),
        period=period,
        interval=interval,
        group_by="ticker",
        threads=True,
        progress=False
    )
    
    results = []
    for s in symbols:
        ticker = f"{s}.NS"
        try:
            df = data[ticker].dropna() if len(symbols) > 1 else data.dropna()
            if len(df) < 16:
                continue
            
            close = df["Close"]
            ema_9 = close.ewm(span=9, adjust=False).mean()
            ema_15 = close.ewm(span=15, adjust=False).mean()

            c_close = float(close.iloc[-1])
            c_9 = float(ema_9.iloc[-1])
            c_15 = float(ema_15.iloc[-1])
            p_9 = float(ema_9.iloc[-2])
            p_15 = float(ema_15.iloc[-2])

            if c_9 > c_15:
                is_fresh = (p_9 <= p_15)
                spread = round(((c_9 - c_15) / c_15) * 100, 2)
                results.append({
                    "Symbol": s,
                    "LTP (₹)": round(c_close, 2),
                    "9 EMA": round(c_9, 2),
                    "15 EMA": round(c_15, 2),
                    "Spread (%)": spread,
                    "Signal": "🚀 Fresh Cross" if is_fresh else "🟢 9 > 15 Uptrend"
                })
        except Exception:
            continue
            
    return results

# --- UI Dashboard ---
st.title("🇮🇳 NSE Real-Time Market Charts & 9/15 EMA Screener")
st.caption("Live streaming ticks for Indian Equities (Asia/Kolkata IST) • Market Hours: 9:15 AM – 3:30 PM IST")

all_symbols = get_all_symbols()

# ----------------- SECTION 1: SEARCH & VIEW CHART -----------------
st.markdown("### 🔴 Real-Time Chart (IST)")
col_c1, col_c2 = st.columns([3, 1])

with col_c1:
    selected_stock = st.selectbox(
        "Select or Search Any Stock:",
        options=all_symbols,
        index=all_symbols.index("RELIANCE") if "RELIANCE" in all_symbols else 0
    )

with col_c2:
    chart_tf = st.selectbox("Candle Timeframe", ["5m", "15m", "1h", "1d"], index=0)

render_live_chart(selected_stock, chart_tf)

st.markdown("---")

# ----------------- SECTION 2: 9/15 EMA SCREENER -----------------
st.markdown("### ⚡ Scan Market for 9 EMA > 15 EMA")

col1, col2 = st.columns([1, 1])
with col1:
    screener_tf = st.selectbox("Screener Timeframe", ["15m", "5m", "1h", "1d"], index=0, key="scan_tf")
with col2:
    scan_limit = st.slider("Stocks to scan", min_value=50, max_value=len(all_symbols), value=150, step=50)

if st.button("🚀 Run EMA Screener", type="primary"):
    pool = all_symbols[:scan_limit]
    all_matches = []
    
    prog = st.progress(0)
    status = st.empty()
    batch_size = 50

    for i in range(0, len(pool), batch_size):
        chunk = pool[i:i + batch_size]
        status.text(f"Scanning stocks {i+1} to {min(i + batch_size, len(pool))} of {len(pool)}...")
        res = scan_batch(chunk, interval=screener_tf)
        all_matches.extend(res)
        prog.progress(min((i + batch_size) / len(pool), 1.0))

    status.empty()
    prog.empty()

    if all_matches:
        st.session_state["results_df"] = pd.DataFrame(all_matches)
    else:
        st.session_state["results_df"] = pd.DataFrame()
        st.warning("No stocks matched the 9 EMA > 15 EMA condition.")

if "results_df" in st.session_state and not st.session_state["results_df"].empty:
    df_res = st.session_state["results_df"]
    st.subheader(f"Matching Stocks ({len(df_res)})")
    st.dataframe(df_res, use_container_width=True)

    st.markdown("#### Open Match in Live Chart")
    match_pick = st.selectbox("Choose a screened stock:", df_res["Symbol"].tolist())
    if match_pick:
        render_live_chart(match_pick, screener_tf)
        
