import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests

st.set_page_config(page_title="NSE 9/15 EMA Screener & Charts", layout="wide")

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

# Simple native candlestick + 9/15 EMA chart
def render_simple_chart(symbol, interval="1d"):
    period = "1mo" if interval in ["5m", "15m", "1h"] else "6mo"
    ticker = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol
    
    with st.spinner(f"Loading chart for {symbol}..."):
        df = yf.download(ticker, period=period, interval=interval, progress=False)
        
    if df.empty or len(df) < 15:
        st.warning(f"No chart data available for {symbol}.")
        return

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]

    df["EMA_9"] = df["Close"].ewm(span=9, adjust=False).mean()
    df["EMA_15"] = df["Close"].ewm(span=15, adjust=False).mean()
    
    # Display last 80 candles for clarity
    chart_df = df.tail(80)

    fig = go.Figure()

    # Candlestick Trace
    fig.add_trace(go.Candlestick(
        x=chart_df.index,
        open=chart_df["Open"],
        high=chart_df["High"],
        low=chart_df["Low"],
        close=chart_df["Close"],
        name="Price"
    ))

    # 9 EMA line (Green)
    fig.add_trace(go.Scatter(
        x=chart_df.index,
        y=chart_df["EMA_9"],
        line=dict(color="#00E676", width=2),
        name="9 EMA"
    ))

    # 15 EMA line (Red)
    fig.add_trace(go.Scatter(
        x=chart_df.index,
        y=chart_df["EMA_15"],
        line=dict(color="#FF1744", width=2),
        name="15 EMA"
    ))

    fig.update_layout(
        title=f"{symbol} Candlestick Chart ({interval})",
        yaxis_title="Price (₹)",
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        height=550,
        margin=dict(l=20, r=20, t=50, b=20)
    )

    st.plotly_chart(fig, use_container_width=True)

# Fast multi-threaded batch scanner
def scan_batch(symbols, interval="1d"):
    tickers = [f"{s}.NS" for s in symbols]
    period = "1mo" if interval in ["5m", "15m", "1h"] else "3mo"
    
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

            # Condition: 9 EMA strictly above 15 EMA
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

# --- App UI ---
st.title("📈 Indian Stock Screener & Simple Candlestick Chart")
st.caption("Scan all NSE listed companies for **9 EMA > 15 EMA** with built-in interactive candlestick charts.")

all_symbols = get_all_symbols()

# ----------------- SECTION 1: SEARCH ANY STOCK -----------------
st.markdown("### 🔍 Chart Any Stock")
col_s1, col_s2 = st.columns([3, 1])

with col_s1:
    selected_stock = st.selectbox(
        "Select or type any stock to display chart:",
        options=all_symbols,
        index=all_symbols.index("RELIANCE") if "RELIANCE" in all_symbols else 0
    )

with col_s2:
    chart_tf = st.selectbox("Timeframe", ["1d", "1h", "15m", "5m"], key="chart_tf")

render_simple_chart(selected_stock, chart_tf)

st.markdown("---")

# ----------------- SECTION 2: 9/15 EMA SCREENER -----------------
st.markdown("### ⚡ Screener: Scan for 9 EMA > 15 EMA")

col1, col2 = st.columns([1, 1])
with col1:
    screener_timeframe = st.selectbox("Scan Timeframe", ["1d", "1h", "15m", "5m"], key="scan_tf")
with col2:
    scan_limit = st.slider("Number of stocks to scan", min_value=50, max_value=len(all_symbols), value=200, step=50)

if st.button("🚀 Run 9/15 EMA Screener", type="primary"):
    pool = all_symbols[:scan_limit]
    all_matches = []
    
    prog = st.progress(0)
    status = st.empty()
    batch_size = 50

    for i in range(0, len(pool), batch_size):
        chunk = pool[i:i + batch_size]
        status.text(f"Scanning stocks {i+1} to {min(i + batch_size, len(pool))} of {len(pool)}...")
        res = scan_batch(chunk, interval=screener_timeframe)
        all_matches.extend(res)
        prog.progress(min((i + batch_size) / len(pool), 1.0))

    status.empty()
    prog.empty()

    if all_matches:
        st.session_state["screener_results"] = pd.DataFrame(all_matches)
    else:
        st.session_state["screener_results"] = pd.DataFrame()
        st.warning("No stocks found matching 9 EMA > 15 EMA in this batch.")

if "screener_results" in st.session_state and not st.session_state["screener_results"].empty:
    df_res = st.session_state["screener_results"]
    st.subheader(f"Matching Stocks ({len(df_res)})")
    st.dataframe(df_res, use_container_width=True)
    
    st.markdown("#### Inspect Screened Stock")
    match_pick = st.selectbox("Choose a stock from screened results:", df_res["Symbol"].tolist())
    if match_pick:
        render_simple_chart(match_pick, screener_timeframe)
    
