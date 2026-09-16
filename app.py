import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import time

st.set_page_config(page_title="NSE Live 9/15 EMA Screener", layout="wide")

# Fetch all listed equities from official NSE archives
@st.cache_data(ttl=86400)
def get_all_symbols():
    try:
        url = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=15)
        df = pd.read_csv(pd.io.common.StringIO(resp.text))
        eq_df = df[df[" SERIES"].str.strip() == "EQ"] if " SERIES" in df.columns else df
        return sorted(list(set([sym.strip() for sym in eq_df["SYMBOL"].dropna().tolist()])))
    except Exception:
        return sorted([
            "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "BHARTIARTL", 
            "ITC", "SBIN", "LT", "BAJFINANCE", "HCLTECH", "MARUTI", "SUNPHARMA",
            "TATAMOTORS", "KOTAKBANK", "AXISBANK", "NTPC", "TITAN", "POWERGRID"
        ])

# Fast batch scanner strictly for 9 EMA > 15 EMA
def scan_batch(symbols, interval="5m"):
    tickers = [f"{s}.NS" for s in symbols]
    period = "5d" if interval in ["1m", "5m", "15m"] else "1mo"
    
    data = yf.download(
        tickers=" ".join(tickers),
        period=period,
        interval=interval,
        group_by="ticker",
        threads=True,
        progress=False
    )
    
    matches = []
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

            # Condition: 9 EMA strictly above 15 EMA
            if c_9 > c_15:
                is_fresh = (p_9 <= p_15)
                spread = round(((c_9 - c_15) / c_15) * 100, 2)
                matches.append({
                    "Symbol": s,
                    "LTP (₹)": round(c_close, 2),
                    "9 EMA": round(c_9, 2),
                    "15 EMA": round(c_15, 2),
                    "Spread (%)": spread,
                    "Status": "🚀 Fresh 9/15 Crossover" if is_fresh else "🟢 9 EMA > 15 EMA (Uptrend)",
                    "Angel One": f"https://trade.angelone.in/",
                    "TradingView": f"https://in.tradingview.com/chart/?symbol=NSE:{s}"
                })
        except Exception:
            continue
            
    return matches

# --- UI Dashboard ---
st.title("⚡ Real-Time NSE 9/15 EMA Bullish Screener")
st.caption("Live scan for Indian Equities where **9 EMA > 15 EMA** (IST Market Hours: 9:15 AM – 3:30 PM)")

all_symbols = get_all_symbols()

col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    timeframe = st.selectbox("Select Timeframe", ["5m", "15m", "1h", "1d"], index=0)

with col2:
    scan_limit = st.slider("Universe Size", min_value=50, max_value=len(all_symbols), value=150, step=50)

with col3:
    auto_refresh = st.checkbox("🔄 Auto Refresh (Every 30s)", value=False)

def run_scan():
    pool = all_symbols[:scan_limit]
    results = []
    
    prog = st.progress(0)
    status = st.empty()
    batch_size = 50

    for i in range(0, len(pool), batch_size):
        chunk = pool[i:i + batch_size]
        status.text(f"Scanning stocks {i+1} to {min(i + batch_size, len(pool))} of {len(pool)}...")
        batch_matches = scan_batch(chunk, interval=timeframe)
        results.extend(batch_matches)
        prog.progress(min((i + batch_size) / len(pool), 1.0))

    status.empty()
    prog.empty()

    if results:
        st.session_state["ema_results"] = pd.DataFrame(results)
    else:
        st.session_state["ema_results"] = pd.DataFrame()
        st.warning("No stocks currently have 9 EMA above 15 EMA in this batch.")

if st.button("🚀 Scan Now", type="primary"):
    run_scan()

# Display Results
if "ema_results" in st.session_state and not st.session_state["ema_results"].empty:
    df_res = st.session_state["ema_results"]
    
    # Sort: Fresh Crossovers at the top, then largest EMA spread
    df_res["is_fresh"] = df_res["Status"].str.contains("Fresh")
    df_res = df_res.sort_values(by=["is_fresh", "Spread (%)"], ascending=[False, False]).drop(columns=["is_fresh"])

    st.subheader(f"Matching Stocks ({len(df_res)})")

    # Render table with clickable execution links
    st.dataframe(
        df_res,
        column_config={
            "TradingView": st.column_config.LinkColumn("TradingView Chart", display_text="Open Chart"),
            "Angel One": st.column_config.LinkColumn("Angel One Trade", display_text="Trade on Angel"),
            "Spread (%)": st.column_config.NumberColumn("EMA Spread %", format="%.2f%%"),
            "LTP (₹)": st.column_config.NumberColumn("LTP (₹)", format="₹%.2f"),
        },
        use_container_width=True,
        hide_index=True
    )

# Auto-refresh loop
if auto_refresh:
    time.sleep(30)
    st.rerun()
                
