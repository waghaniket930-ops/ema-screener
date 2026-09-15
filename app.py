import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import requests

st.set_page_config(page_title="All 2000+ NSE Stocks Screener (9/15 EMA)", layout="wide")

# Fetch all 2000+ official equity tickers directly from NSE
@st.cache_data(ttl=86400)
def get_all_nse_symbols():
    try:
        url = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        resp = requests.get(url, headers=headers, timeout=15)
        df = pd.read_csv(pd.io.common.StringIO(resp.text))
        # Keep only equity segment (EQ)
        eq_df = df[df[" SERIES"].str.strip() == "EQ"] if " SERIES" in df.columns else df
        symbols = [sym.strip() for sym in eq_df["SYMBOL"].dropna().tolist()]
        return symbols
    except Exception:
        # Fallback list
        return ["RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "BHARTIARTL", "ITC", "SBIN", "LT", "BAJFINANCE"]

# Fast multi-threaded batch scanner
def scan_batch(symbols, interval="1d"):
    tickers = [f"{s}.NS" for s in symbols]
    period = "1mo" if interval in ["5m", "15m", "1h"] else "3mo"
    
    # Batch download all tickers at once
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

            # Filter: 9 EMA > 15 EMA
            if c_9 > c_15:
                is_fresh = (p_9 <= p_15)
                spread = round(((c_9 - c_15) / c_15) * 100, 2)
                results.append({
                    "Symbol": s,
                    "LTP (₹)": round(c_close, 2),
                    "9 EMA": round(c_9, 2),
                    "15 EMA": round(c_15, 2),
                    "Spread (%)": spread,
                    "Signal": "🚀 Fresh 9/15 Cross" if is_fresh else "🟢 9 EMA > 15 EMA"
                })
        except Exception:
            continue
            
    return results

# TradingView chart embedding
def render_tv_chart(symbol, interval="D"):
    tv_map = {"1d": "D", "1h": "60", "15m": "15", "5m": "5"}
    chart_interval = tv_map.get(interval, "D")
    
    html_code = f"""
    <div class="tradingview-widget-container" style="height:620px;width:100%;">
      <div id="tv_chart" style="height:calc(100% - 32px);width:100%;"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget(
      {{
        "autosize": true,
        "symbol": "NSE:{symbol}",
        "interval": "{chart_interval}",
        "timezone": "Asia/Kolkata",
        "theme": "dark",
        "style": "1",
        "locale": "en",
        "enable_publishing": false,
        "allow_symbol_change": true,
        "studies": [
          {{ "id": "MAExp@tv-basicstudies", "inputs": {{ "length": 9 }} }},
          {{ "id": "MAExp@tv-basicstudies", "inputs": {{ "length": 15 }} }}
        ],
        "container_id": "tv_chart"
      }}
      );
      </script>
    </div>
    """
    components.html(html_code, height=620)

# --- Streamlit UI ---
st.title("⚡ All 2000+ NSE Stocks Screener")
st.caption("Batch scanning all listed NSE equity stocks for **9 EMA > 15 EMA** + TradingView charts.")

all_symbols = get_all_nse_symbols()
st.info(f"Loaded **{len(all_symbols)}** active NSE listed companies from official archives.")

col1, col2 = st.columns(2)
with col1:
    timeframe = st.selectbox("Select Timeframe", ["1d", "1h", "15m", "5m"])
with col2:
    scan_limit = st.slider("Number of stocks to scan", min_value=50, max_value=len(all_symbols), value=len(all_symbols), step=50)

if st.button("🚀 Scan All NSE Stocks", type="primary"):
    target_stocks = all_symbols[:scan_limit]
    batch_size = 100
    all_results = []
    
    prog_bar = st.progress(0)
    status = st.empty()

    # Process in batches of 100 for high speed
    for i in range(0, len(target_stocks), batch_size):
        chunk = target_stocks[i:i + batch_size]
        status.text(f"Scanning stocks {i+1} to {min(i + batch_size, len(target_stocks))} of {len(target_stocks)}...")
        res = scan_batch(chunk, interval=timeframe)
        all_results.extend(res)
        prog_bar.progress(min((i + batch_size) / len(target_stocks), 1.0))

    status.empty()
    prog_bar.empty()

    if all_results:
        st.session_state["results"] = pd.DataFrame(all_results)
    else:
        st.session_state["results"] = pd.DataFrame()
        st.warning("No stocks matched the 9 EMA > 15 EMA condition.")

# Display results table & TradingView chart
if "results" in st.session_state and not st.session_state["results"].empty:
    df_res = st.session_state["results"]
    st.subheader(f"Matching Stocks Found: {len(df_res)}")
    
    st.dataframe(
        df_res.style.map(
            lambda v: "color: #00E676; font-weight: bold;" if "Fresh" in str(v) else "color: #81C784;",
            subset=["Signal"]
        ),
        use_container_width=True
    )

    st.markdown("---")
    st.subheader("📊 Live TradingView Chart")
    selected_stock = st.selectbox("Pick a stock from results:", df_res["Symbol"].tolist())
    
    if selected_stock:
        render_tv_chart(selected_stock, timeframe)
    
