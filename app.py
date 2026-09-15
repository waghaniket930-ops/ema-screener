import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import requests

st.set_page_config(page_title="Universal Indian Stock Screener & TradingView", layout="wide")

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

# TradingView Pro Terminal: Unlocked symbol search for ALL symbols
def render_full_tradingview(symbol, interval="D"):
    tv_map = {"1d": "D", "1h": "60", "15m": "15", "5m": "5"}
    chart_interval = tv_map.get(interval, "D")
    
    # Format symbol prefix correctly if not already present
    formatted_symbol = symbol if ":" in symbol else f"NSE:{symbol}"
    
    tradingview_html = f"""
    <div class="tradingview-widget-container" style="height:720px; width:100%;">
      <div id="tradingview_full_chart" style="height:100%; width:100%;"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget({{
        "autosize": true,
        "symbol": "{formatted_symbol}",
        "interval": "{chart_interval}",
        "timezone": "Asia/Kolkata",
        "theme": "dark",
        "style": "1",
        "locale": "in",
        "toolbar_bg": "#131722",
        "enable_publishing": false,
        "hide_side_toolbar": false,
        "allow_symbol_change": true,
        "save_image": true,
        "details": true,
        "hotlist": true,
        "calendar": true,
        "show_popup_button": true,
        "popup_width": "1000",
        "popup_height": "650",
        "studies": [
          {{
            "id": "MAExp@tv-basicstudies",
            "inputs": {{ "length": 9 }}
          }},
          {{
            "id": "MAExp@tv-basicstudies",
            "inputs": {{ "length": 15 }}
          }}
        ],
        "container_id": "tradingview_full_chart"
      }});
      </script>
    </div>
    """
    components.html(tradingview_html, height=730)

# --- App UI ---
st.title("📈 All Indian Stocks Screener & TradingView Terminal")
st.caption("Scan all listed companies for **9 EMA > 15 EMA**, or search **any symbol in the world** directly inside TradingView.")

all_symbols = get_all_symbols()

# Popular market index shortcuts
INDEX_SHORTCUTS = {
    "NIFTY 50 Index": "NSE:NIFTY",
    "BANK NIFTY Index": "NSE:BANKNIFTY",
    "BSE SENSEX Index": "BSE:SENSEX",
    "NIFTY IT Index": "NSE:CNXIT"
}

# ----------------- SECTION 1: UNIVERSAL CHART SEARCH -----------------
st.markdown("### 🔍 Chart Terminal (All Stocks, Indices & Commodities)")
sc1, sc2, sc3 = st.columns([2, 2, 1])

with sc1:
    quick_index = st.selectbox("Quick Index View:", ["None"] + list(INDEX_SHORTCUTS.keys()))

with sc2:
    selected_stock = st.selectbox(
        "Or pick from 2,000+ NSE Equities:",
        options=all_symbols,
        index=all_symbols.index("RELIANCE") if "RELIANCE" in all_symbols else 0
    )

with sc3:
    chart_tf = st.selectbox("Timeframe", ["1d", "1h", "15m", "5m"], key="chart_tf")

# Determine active symbol
if quick_index != "None":
    active_symbol = INDEX_SHORTCUTS[quick_index]
else:
    active_symbol = f"NSE:{selected_stock}"

st.info("💡 **Tip:** You can also click the symbol name inside the top-left of the chart widget itself to search **any symbol across the globe** (NSE, BSE, MCX, Crypto, Forex).")
render_full_tradingview(active_symbol, chart_tf)

st.markdown("---")

# ----------------- SECTION 2: 9/15 EMA SCREENER -----------------
st.markdown("### ⚡ Screener: Scan All Stocks for 9 EMA > 15 EMA")

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
    
    st.markdown("#### View Screened Match in Chart")
    match_pick = st.selectbox("Select match to open in TradingView:", df_res["Symbol"].tolist())
    if match_pick:
        render_full_tradingview(f"NSE:{match_pick}", screener_timeframe)
        
