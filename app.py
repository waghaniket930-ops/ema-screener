import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import requests

st.set_page_config(
    page_title="NSE Live Screener (India IST)", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

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

# Indian Market Real-Time Chart Widget (Configured for IST + NSE Feed)
def render_india_realtime_chart(symbol, interval="5"):
    clean_sym = symbol.replace("NSE:", "").replace(".NS", "").strip()

    tv_html = f"""
    <div class="tradingview-widget-container" style="height:650px; width:100%;">
      <div id="tv_chart_container" style="height:100%; width:100%;"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget({{
        "autosize": true,
        "symbol": "NSE:{clean_sym}",
        "interval": "{interval}",
        "timezone": "Asia/Kolkata",
        "theme": "dark",
        "style": "1",
        "locale": "in",
        "toolbar_bg": "#131722",
        "enable_publishing": false,
        "allow_symbol_change": true,
        "save_image": true,
        "hide_side_toolbar": false,
        "withdateranges": true,
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
        "container_id": "tv_chart_container"
      }});
      </script>
    </div>
    """
    components.html(tv_html, height=660)

# Multi-threaded batch scanner for 9 EMA > 15 EMA
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
st.title("🇮🇳 NSE Real-Time Chart & 9/15 EMA Screener")
st.caption("Live streaming ticks for Indian Equities (Asia/Kolkata IST) • Market Hours: 9:15 AM – 3:30 PM IST")

all_symbols = get_all_symbols()

# ----------------- SECTION 1: LIVE CHART -----------------
st.markdown("### 🔴 Live Real-Time Chart (IST)")
col_c1, col_c2 = st.columns([3, 1])

with col_c1:
    selected_stock = st.selectbox(
        "Select Stock for Real-Time IST Feed:",
        options=all_symbols,
        index=all_symbols.index("RELIANCE") if "RELIANCE" in all_symbols else 0
    )

with col_c2:
    tf_options = {"5 Minutes": "5", "15 Minutes": "15", "1 Hour": "60", "Daily": "D"}
    selected_tf_label = st.selectbox("Candle Timeframe", list(tf_options.keys()), index=1)
    chart_interval = tf_options[selected_tf_label]

render_india_realtime_chart(selected_stock, chart_interval)

st.markdown("---")

# ----------------- SECTION 2: SCREENER -----------------
st.markdown("### ⚡ Scan Market for 9 EMA > 15 EMA")

col1, col2 = st.columns([1, 1])
with col1:
    screener_tf = st.selectbox("Screener Timeframe", ["15m", "5m", "1h", "1d"], index=0)
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
        render_india_realtime_chart(match_pick, chart_interval)
