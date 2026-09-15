import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests

st.set_page_config(page_title="NSE 9/15 EMA Bullish Screener", layout="wide")

@st.cache_data(ttl=86400)
def get_nifty_500():
    try:
        url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        df = pd.read_csv(pd.io.common.StringIO(response.text))
        return [f"{sym}.NS" for sym in df["Symbol"].dropna().tolist()]
    except Exception:
        return [
            "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
            "BHARTIARTL.NS", "ITC.NS", "SBIN.NS", "LT.NS", "BAJFINANCE.NS"
        ]

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

        # Strategy Condition: 9 EMA must be ABOVE 15 EMA
        if ema9_c > ema15_c:
            is_fresh_cross = (ema9_p <= ema15_p)
            status = "🚀 Fresh Crossover" if is_fresh_cross else "🟢 Uptrend (9 > 15)"
            
            return {
                "Symbol": symbol.replace(".NS", ""),
                "LTP": round(close, 2),
                "9 EMA": round(ema9_c, 2),
                "15 EMA": round(ema15_c, 2),
                "Signal": status,
                "Data": data
            }
        return None
    except Exception:
        return None

# --- Dashboard UI ---
st.title("📈 NSE Bullish Screener (9 EMA > 15 EMA)")

col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    universe = st.selectbox("Stock Universe", ["NIFTY 50", "NIFTY Bank", "NIFTY 500"])
with col2:
    timeframe = st.selectbox("Timeframe", ["1d", "1h", "15m", "5m"])
with col3:
    max_scan = st.number_input("Scan Limit", min_value=5, max_value=500, value=30, step=5)

if universe == "NIFTY 500":
    pool = get_nifty_500()[:max_scan]
else:
    pool = WATCHLISTS[universe][:max_scan]

if st.button("Run Screener", type="primary"):
    results = []
    charts = {}
    
    prog = st.progress(0)
    status_box = st.empty()

    for idx, sym in enumerate(pool):
        status_box.text(f"Scanning {sym}...")
        res = scan_stock(sym, timeframe)
        if res:
            charts[res["Symbol"]] = res.pop("Data")
            results.append(res)
        prog.progress((idx + 1) / len(pool))

    status_box.empty()
    prog.empty()

    if results:
        df = pd.DataFrame(results)
        st.session_state["results"] = df
        st.session_state["charts"] = charts
    else:
        st.warning("No stocks found where 9 EMA is above 15 EMA.")

# Show Table & Candlestick Chart if data exists
if "results" in st.session_state and not st.session_state["results"].empty:
    st.subheader(f"Stocks where 9 EMA > 15 EMA ({len(st.session_state['results'])})")
    st.dataframe(st.session_state["results"], use_container_width=True)

    st.markdown("---")
    st.subheader("📊 Candlestick Chart with 9 & 15 EMA")
    selected_sym = st.selectbox("Select stock to inspect:", st.session_state["results"]["Symbol"].tolist())

    if selected_sym:
        chart_df = st.session_state["charts"][selected_sym].tail(80)

        fig = go.Figure()

        # Candlestick Trace
        fig.add_trace(go.Candlestick(
            x=chart_df.index,
            open=chart_df["Open"],
            high=chart_df["High"],
            low=chart_df["Low"],
            close=chart_df["Close"],
            name="Candles"
        ))

        # 9 EMA line (Green)
        fig.add_trace(go.Scatter(
            x=chart_df.index,
            y=chart_df["EMA_9"],
            line=dict(color="#00E676", width=1.5),
            name="9 EMA"
        ))

        # 15 EMA line (Red)
        fig.add_trace(go.Scatter(
            x=chart_df.index,
            y=chart_df["EMA_15"],
            line=dict(color="#FF1744", width=1.5),
            name="15 EMA"
        ))

        fig.update_layout(
            title=f"{selected_sym} Candlestick Chart ({timeframe.upper()})",
            yaxis_title="Price (₹)",
            xaxis_rangeslider_visible=False,
            template="plotly_dark",
            height=550
        )

        st.plotly_chart(fig, use_container_width=True)
