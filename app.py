import os
import time
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from heuristic import (
    best_first_search,
    compute_heuristic_scores,
    HEURISTIC_PRESETS
)
import live_data


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="TradeMind AI - Intelligent NSE Stock Analysis",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# CUSTOM STYLING (CSS)
# ============================================================

st.markdown("""
<style>
    .main-title {
        font-size: 38px;
        font-weight: 800;
        text-align: center;
        margin-bottom: 4px;
        background: linear-gradient(90deg, #1E88E5, #00C853);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .subtitle {
        text-align: center;
        font-size: 16px;
        color: #78909C;
        margin-bottom: 24px;
    }
    .metric-card {
        background-color: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 12px;
        padding: 16px;
        text-align: center;
    }
    .badge-live {
        background-color: #00C853;
        color: white;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: bold;
    }
    .badge-sim {
        background-color: #FFA000;
        color: white;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: bold;
    }
    .badge-offline {
        background-color: #E53935;
        color: white;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: bold;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 16px;
        font-weight: 600;
        padding: 10px 20px;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# TITLE HEADER
# ============================================================

st.markdown('<div class="main-title">📈 TradeMind AI</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">'
    'AI-Powered NSE Stock Analysis Engine with Best-First Search & Real-Time Upstox Streaming'
    '</div>',
    unsafe_allow_html=True
)


# ============================================================
# LOAD & CLEAN HISTORICAL DATASET
# ============================================================

@st.cache_data
def load_and_clean_data(csv_path="data/National_Stock_Exchange_of_India_Ltd.csv"):
    if not os.path.exists(csv_path):
        return None

    df_raw = pd.read_csv(csv_path)
    df_raw.columns = df_raw.columns.str.strip()

    numeric_cols = [
        "Open", "High", "Low", "LTP", "% Chng",
        "Volume (lacs)", "52w H", "52w L",
        "365 d % chng", "30 d % chng"
    ]

    for col in numeric_cols:
        if col in df_raw.columns:
            df_raw[col] = (
                df_raw[col]
                .astype(str)
                .str.replace(",", "", regex=False)
                .str.replace("%", "", regex=False)
            )
            df_raw[col] = pd.to_numeric(df_raw[col], errors="coerce")

    # Filter critical columns
    important_cols = ["Symbol", "LTP", "% Chng", "30 d % chng", "365 d % chng", "52w H", "52w L"]
    cleaned = df_raw.dropna(subset=important_cols).copy()
    return cleaned


df_base = load_and_clean_data()

if df_base is None or df_base.empty:
    st.error(
        "❌ Dataset not found. Please ensure 'data/National_Stock_Exchange_of_India_Ltd.csv' is present."
    )
    st.stop()


# ============================================================
# LIVE WEBSOCKET STREAM INITIALIZATION
# ============================================================

if "feed_started" not in st.session_state:
    try:
        live_data.start_background_feed()
        st.session_state["feed_started"] = True
    except Exception as e:
        st.session_state["feed_started"] = False


# ============================================================
# SIDEBAR CONTROLS
# ============================================================

st.sidebar.markdown("## ⚙️ Strategy & Controls")

# Strategy Presets
strategy_choice = st.sidebar.selectbox(
    "Investment Strategy Preset",
    list(HEURISTIC_PRESETS.keys()) + ["Custom Weights"],
    help="Select a predefined investment strategy or customize heuristic weights manually."
)

if strategy_choice == "Custom Weights":
    st.sidebar.markdown("### 🎚️ Heuristic Factor Weights")
    w_30d = st.sidebar.slider("30-Day Momentum (Short-term)", 0.0, 1.0, 0.30, 0.05)
    w_365d = st.sidebar.slider("365-Day Performance (Long-term)", 0.0, 1.0, 0.25, 0.05)
    w_curr = st.sidebar.slider("Current Day Change (Intraday)", 0.0, 1.0, 0.20, 0.05)
    w_52w = st.sidebar.slider("52-Week Range Position", 0.0, 1.0, 0.25, 0.05)
    
    current_weights = {
        "weight_30d": w_30d,
        "weight_365d": w_365d,
        "weight_current": w_curr,
        "weight_52w": w_52w
    }
else:
    preset = HEURISTIC_PRESETS[strategy_choice]
    current_weights = {
        "weight_30d": preset["weight_30d"],
        "weight_365d": preset["weight_365d"],
        "weight_current": preset["weight_current"],
        "weight_52w": preset["weight_52w"]
    }
    st.sidebar.info(f"📌 **{strategy_choice}**: {preset['description']}")

st.sidebar.divider()

# Live Data Feed Controls
st.sidebar.markdown("### ⚡ Upstox Live Feed Settings")
stream_status = live_data.get_status_summary()

if stream_status["status"] == "CONNECTED":
    st.sidebar.markdown('Status: <span class="badge-live">● LIVE CONNECTED</span>', unsafe_allow_html=True)
elif stream_status["status"] == "SIMULATED":
    st.sidebar.markdown('Status: <span class="badge-sim">● SIMULATION MODE</span>', unsafe_allow_html=True)
else:
    st.sidebar.markdown('Status: <span class="badge-offline">● OFFLINE / READY</span>', unsafe_allow_html=True)

st.sidebar.caption(f"Ticks received: {stream_status['received_ticks_count']} | Last update: {stream_status['last_update']}")

enable_sim = st.sidebar.checkbox(
    "Enable Demo Ticks Simulation",
    value=stream_status["is_simulated"],
    help="Enable simulated price ticks to test live dashboard outside NSE market hours (09:15-15:30 IST)."
)
if enable_sim != stream_status["is_simulated"]:
    live_data.enable_simulation(enable_sim)
    st.rerun()

auto_refresh = st.sidebar.checkbox("Auto-Refresh Live View", value=False)
if auto_refresh:
    refresh_rate = st.sidebar.slider("Refresh Interval (seconds)", 3, 30, 5)
    time.sleep(refresh_rate)
    st.rerun()

if st.sidebar.button("🔄 Refresh Data Now"):
    st.rerun()

st.sidebar.divider()

# Top-K Slider
top_n = st.sidebar.slider(
    "Number of Top Recommendations",
    min_value=3,
    max_value=20,
    value=10
)


# ============================================================
# COMPUTE HEURISTIC SCORES (INTEGRATING LIVE DATA IF AVAILABLE)
# ============================================================

df = df_base.copy()
live_ticks = live_data.calculate_live_change()

# If live ticks are available for stocks, augment the dataframe
if live_ticks:
    df["Is_Live"] = False
    for symbol, tick in live_ticks.items():
        mask = df["Symbol"] == symbol
        if mask.any():
            df.loc[mask, "Live_LTP"] = tick["LTP"]
            df.loc[mask, "Live_Change"] = tick["Live Change"]
            df.loc[mask, "Is_Live"] = True

    # Overwrite LTP and % Chng with live values where live feed exists
    if "Live_LTP" in df.columns:
        df["LTP"] = df["Live_LTP"].combine_first(df["LTP"])
    if "Live_Change" in df.columns:
        df["% Chng"] = df["Live_Change"].combine_first(df["% Chng"])

# Compute heuristic scores based on selected weights
df = compute_heuristic_scores(df, current_weights)


# ============================================================
# MAIN TABS INTERFACE
# ============================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 AI Screener & Best-First Search",
    "⚡ Live Market Streamer (Upstox)",
    "🔍 Deep Dive & Stock Comparator",
    "🧠 AI Theory & Algorithm Guide"
])


# ============================================================
# TAB 1: AI SCREENER & BEST-FIRST SEARCH
# ============================================================

with tab1:
    # Key Market Metrics
    st.markdown("### 📌 Market Snapshot")
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    m_col1.metric("Tracked Stocks", len(df))
    m_col2.metric("Average Daily Change", f"{df['% Chng'].mean():.2f}%")
    m_col3.metric("Average 30D Return", f"{df['30 d % chng'].mean():.2f}%")
    m_col4.metric("Average 365D Return", f"{df['365 d % chng'].mean():.2f}%")

    st.divider()

    # Run AI Best-First Search with full search trajectory
    top_stocks_df, search_trace = best_first_search(df, top_k=top_n, return_trace=True)
    best_stock = top_stocks_df.iloc[0] if top_stocks_df is not None and not top_stocks_df.empty else None

    # Highlight Best-First Search Winner
    st.markdown("### 🏆 AI Best-First Search Selection")
    if best_stock is not None:
        w_col1, w_col2, w_col3, w_col4 = st.columns(4)
        
        is_live_badge = " 🟢 (Live)" if best_stock.get("Is_Live", False) else ""
        w_col1.success(f"### {best_stock['Symbol']}{is_live_badge}")
        w_col2.metric("Heuristic Score h(n)", f"{best_stock['Heuristic Score']:.2f} / 100")
        w_col3.metric("Current Price (LTP)", f"₹{best_stock['LTP']:,.2f}", f"{best_stock['% Chng']:+.2f}%")
        w_col4.metric("30-Day Momentum", f"{best_stock['30 d % chng']:+.2f}%", f"365D: {best_stock['365 d % chng']:+.2f}%")
    
    st.info(
        f"💡 **AI Search Rationale**: The Best-First Search algorithm extracted **{best_stock['Symbol']}** "
        f"from the Priority Queue (OPEN list) as having the highest heuristic estimate "
        f"under the **{strategy_choice}** strategy weights."
    )

    st.divider()

    # Visualizing Top Stocks by Heuristic Score
    st.markdown(f"### 📊 Top {top_n} Stocks Evaluated by Best-First Search")
    
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        fig_bar = px.bar(
            top_stocks_df,
            x="Symbol",
            y="Heuristic Score",
            color="Heuristic Score",
            color_continuous_scale="Viridis",
            title=f"Top {top_n} Stocks Ranked by Priority Queue h(n)",
            text="Heuristic Score"
        )
        fig_bar.update_traces(texttemplate="%{text:.1f}", textposition="outside")
        fig_bar.update_layout(height=420, xaxis_title="Stock Symbol", yaxis_title="Heuristic Score")
        st.plotly_chart(fig_bar, use_container_width=True)

    with chart_col2:
        # Comparison of 30-Day vs 365-Day performance
        perf_data = top_stocks_df[["Symbol", "30 d % chng", "365 d % chng"]].copy()
        perf_data = perf_data.rename(columns={"30 d % chng": "30-Day Return", "365 d % chng": "365-Day Return"})
        perf_melted = perf_data.melt(id_vars="Symbol", var_name="Timeframe", value_name="Return %")

        fig_perf = px.bar(
            perf_melted,
            x="Symbol",
            y="Return %",
            color="Timeframe",
            barmode="group",
            title="Momentum vs Long-Term Trend Comparison",
            color_discrete_map={"30-Day Return": "#29B6F6", "365-Day Return": "#66BB6A"}
        )
        fig_perf.update_layout(height=420, xaxis_title="Stock Symbol", yaxis_title="Return (%)")
        st.plotly_chart(fig_perf, use_container_width=True)

    # Risk vs Performance Scatter
    st.markdown("### 🎯 Risk / Valuation Landscape (LTP vs Heuristic Score)")
    fig_scatter = px.scatter(
        df,
        x="LTP",
        y="Heuristic Score",
        size="Volume (lacs)",
        color="% Chng",
        hover_name="Symbol",
        color_continuous_scale="RdYlGn",
        title="Stock Valuation Distribution (Size = Trading Volume in Lacs)",
        labels={"LTP": "Current Price (₹)", "Heuristic Score": "Heuristic Score h(n)", "% Chng": "Today Change (%)"}
    )
    fig_scatter.update_layout(height=480)
    st.plotly_chart(fig_scatter, use_container_width=True)

    # Step-by-Step AI Search Traversal Trace
    with st.expander("🤖 Inspect Best-First Search Priority Queue Trajectory (Trace Logs)"):
        st.markdown(
            "Below is the exact step-by-step state expansion log showing how the Priority Queue (OPEN list) "
            "and Visited Set (CLOSED list) operated during execution:"
        )
        trace_df = pd.DataFrame(search_trace)
        st.dataframe(
            trace_df[["step", "expanded_node", "heuristic_score", "open_queue_size", "closed_nodes_count", "reasoning"]],
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# TAB 2: LIVE MARKET STREAMER (UPSTOX WEBSOCKET)
# ============================================================

with tab2:
    st.markdown("### ⚡ Real-Time Upstox Market Streamer")
    
    st_info = live_data.get_status_summary()
    status_color = "#00C853" if st_info["status"] == "CONNECTED" else ("#FFA000" if st_info["status"] == "SIMULATED" else "#E53935")
    status_label = "LIVE CONNECTED" if st_info["status"] == "CONNECTED" else ("SIMULATION ACTIVE" if st_info["is_simulated"] else "READY / OFFLINE")

    # Header Streamer Status Bar
    st.markdown(
        f"""
        <div style="background-color: rgba(255, 255, 255, 0.03); border: 1px solid rgba(128, 128, 128, 0.2); border-left: 5px solid {status_color}; padding: 14px 18px; border-radius: 8px; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                <div>
                    <span style="font-weight: 700; font-size: 15px; margin-right: 12px;">Upstox Streamer:</span>
                    <span style="background-color: {status_color}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: bold;">
                        ● {status_label}
                    </span>
                    <span style="color: gray; margin-left: 15px; font-size: 13px;">
                        Monitored Stocks: <b>{st_info['subscribed_count']}</b> | Ticks: <b>{st_info['received_ticks_count']}</b> | Last Tick: <b>{st_info['last_update']}</b>
                    </span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Build CSV baseline cache so any selected stock has instant price data
    csv_baselines = {}
    for _, r in df_base.iterrows():
        s_sym = r["Symbol"]
        s_ltp = float(r["LTP"])
        s_chng = float(r["Chng"]) if "Chng" in r and not pd.isna(r["Chng"]) else 0.0
        s_cp = s_ltp - s_chng if (s_ltp - s_chng) > 0 else s_ltp
        csv_baselines[s_sym] = {
            "ltp": s_ltp,
            "cp": s_cp,
            "high": float(r["High"]) if "High" in r and not pd.isna(r["High"]) else s_ltp,
            "low": float(r["Low"]) if "Low" in r and not pd.isna(r["Low"]) else s_ltp
        }

    # Watchlist Management Toolbar
    st.markdown("#### 🛠️ Live Watchlist & Stock Selector")
    tb_col1, tb_col2 = st.columns([3, 2])

    with tb_col1:
        # All currently monitored symbols
        current_monitored = list(live_data.STOCKS.keys())
        if "focused_live_stock" not in st.session_state or st.session_state["focused_live_stock"] not in current_monitored:
            st.session_state["focused_live_stock"] = current_monitored[0] if current_monitored else "RELIANCE"

        selected_live = st.selectbox(
            "🎯 Select Live Stock to Inspect in Detail (Spotlight):",
            current_monitored,
            index=current_monitored.index(st.session_state["focused_live_stock"]) if st.session_state["focused_live_stock"] in current_monitored else 0,
            key="spotlight_selector",
            help="Select any stock from your active live watchlist to view its real-time tick analytics."
        )
        st.session_state["focused_live_stock"] = selected_live

    with tb_col2:
        # Unsubscribed stocks available to add
        unsubscribed_stocks = [s for s in sorted(df_base["Symbol"].unique()) if s not in live_data.STOCKS]
        add_col_sel, add_col_btn = st.columns([3, 2])
        with add_col_sel:
            new_sym_to_add = st.selectbox(
                "➕ Add NSE Stock to Live Stream:",
                unsubscribed_stocks if unsubscribed_stocks else ["All Added"],
                key="new_stock_dropdown"
            )
        with add_col_btn:
            st.write("")
            st.write("")
            if st.button("➕ Add Stock", use_container_width=True, disabled=(not unsubscribed_stocks or new_sym_to_add == "All Added")):
                if new_sym_to_add and new_sym_to_add != "All Added":
                    live_data.subscribe_symbols([new_sym_to_add], csv_baselines)
                    st.session_state["focused_live_stock"] = new_sym_to_add
                    st.success(f"✅ Added **{new_sym_to_add}** to Live Watchlist!")
                    st.rerun()

    # Active Watchlist Quick-Pills / Chips
    st.markdown("**Currently Streaming:** " + " ".join([
        f"`{sym}`" + (" 🌟" if sym == st.session_state["focused_live_stock"] else "")
        for sym in current_monitored
    ]))

    st.divider()

    # ========================================================
    # 🎯 LIVE STOCK SPOTLIGHT (Selected Stock Hero Card)
    # ========================================================
    f_sym = st.session_state["focused_live_stock"]
    f_tick = live_ticks.get(f_sym)
    f_csv = df[df["Symbol"] == f_sym].iloc[0] if (df["Symbol"] == f_sym).any() else None

    if f_csv is not None:
        f_ltp = f_tick["LTP"] if f_tick else f_csv["LTP"]
        f_cp = f_tick["Previous Close"] if f_tick else (f_csv["LTP"] - f_csv["Chng"] if "Chng" in f_csv else f_csv["LTP"])
        f_chng = f_tick["Live Change"] if f_tick else f_csv["% Chng"]
        f_delta_amount = f_ltp - f_cp
        f_h_score = f_csv["Heuristic Score"]

        st.markdown(f"### 🎯 Live Stock Spotlight: **{f_sym}**")

        spotlight_card = st.container()
        with spotlight_card:
            sp_col1, sp_col2, sp_col3, sp_col4 = st.columns(4)
            
            # Big LTP Card
            chng_color = "#00C853" if f_chng >= 0 else "#FF5252"
            chng_sign = "+" if f_chng >= 0 else ""
            sp_col1.metric(
                label=f"Real-Time Price ({f_sym})",
                value=f"₹{f_ltp:,.2f}",
                delta=f"{chng_sign}{f_chng:.2f}% ({chng_sign}₹{f_delta_amount:.2f})"
            )
            
            sp_col2.metric(
                label="Previous Close",
                value=f"₹{f_cp:,.2f}"
            )
            
            sp_col3.metric(
                label="Day Range (Low - High)",
                value=f"₹{f_csv['Low']:,.2f} - ₹{f_csv['High']:,.2f}"
            )
            
            sp_col4.metric(
                label="Live Heuristic Score h(n)",
                value=f"{f_h_score:.2f} / 100",
                delta=f"52W Pos: {f_csv['52W Position']*100:.1f}%"
            )

            # Intraday Visual Progress Bar
            day_l = f_csv['Low']
            day_h = f_csv['High']
            day_range = max(1e-6, day_h - day_l)
            curr_pos_pct = min(100.0, max(0.0, ((f_ltp - day_l) / day_range) * 100.0))

            st.markdown(
                f"""
                <div style="margin-top: 10px; margin-bottom: 20px; background-color: rgba(255,255,255,0.04); padding: 12px 18px; border-radius: 8px; border: 1px solid rgba(128,128,128,0.15);">
                    <div style="display: flex; justify-content: space-between; font-size: 13px; color: gray; margin-bottom: 5px;">
                        <span>Day Low: <b>₹{day_l:,.2f}</b></span>
                        <span><b>Intraday Price Position: {curr_pos_pct:.1f}%</b></span>
                        <span>Day High: <b>₹{day_h:,.2f}</b></span>
                    </div>
                    <div style="background-color: rgba(128,128,128,0.2); height: 8px; border-radius: 4px; overflow: hidden;">
                        <div style="background: linear-gradient(90deg, #1E88E5, {chng_color}); height: 100%; width: {curr_pos_pct}%; border-radius: 4px;"></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

    st.divider()

    # ========================================================
    # 📡 REAL-TIME WATCHLIST CARDS (RESPONSIVE GRID)
    # ========================================================
    st.markdown("#### 📡 Real-Time Watchlist Tickers")
    active_syms = list(live_ticks.keys()) if live_ticks else current_monitored

    if not active_syms:
        st.info("No active stocks in watchlist. Use the '➕ Add NSE Stock' dropdown above to add stocks.")
    else:
        num_cards_per_row = 3
        for row_start in range(0, len(active_syms), num_cards_per_row):
            card_cols = st.columns(num_cards_per_row)
            for col_idx in range(num_cards_per_row):
                item_idx = row_start + col_idx
                if item_idx < len(active_syms):
                    sym = active_syms[item_idx]
                    tdata = live_ticks.get(sym, csv_baselines.get(sym, {"ltp": 0.0, "cp": 0.0, "Live Change": 0.0}))
                    c_ltp = tdata["LTP"] if "LTP" in tdata else tdata.get("ltp", 0.0)
                    c_cp = tdata["Previous Close"] if "Previous Close" in tdata else tdata.get("cp", 0.0)
                    c_chng = tdata.get("Live Change", ((c_ltp - c_cp) / c_cp * 100) if c_cp else 0.0)
                    
                    is_focused = (sym == st.session_state["focused_live_stock"])
                    border_style = "2px solid #1E88E5" if is_focused else "1px solid rgba(128,128,128,0.2)"
                    bg_style = "rgba(30, 136, 229, 0.08)" if is_focused else "rgba(255,255,255,0.03)"

                    with card_cols[col_idx]:
                        st.markdown(
                            f"""
                            <div style="border: {border_style}; background-color: {bg_style}; border-radius: 10px; padding: 12px; margin-bottom: 12px;">
                                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                                    <span style="font-weight: 700; font-size: 16px;">{sym} {'🌟' if is_focused else ''}</span>
                                    <span style="color: {'#00C853' if c_chng >= 0 else '#FF5252'}; font-weight: 700; font-size: 14px;">
                                        {'+' if c_chng >= 0 else ''}{c_chng:.2f}%
                                    </span>
                                </div>
                                <div style="font-size: 20px; font-weight: 800; margin-bottom: 4px;">₹{c_ltp:,.2f}</div>
                                <div style="font-size: 12px; color: gray;">Prev Close: ₹{c_cp:,.2f}</div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                        c_btn1, c_btn2 = st.columns([1, 1])
                        with c_btn1:
                            if st.button("Inspect 🎯", key=f"focus_{sym}", use_container_width=True):
                                st.session_state["focused_live_stock"] = sym
                                st.rerun()
                        with c_btn2:
                            if len(active_syms) > 1 and st.button("Remove ❌", key=f"remove_{sym}", use_container_width=True):
                                live_data.unsubscribe_symbols([sym])
                                if st.session_state["focused_live_stock"] == sym:
                                    remaining = [s for s in active_syms if s != sym]
                                    st.session_state["focused_live_stock"] = remaining[0] if remaining else "RELIANCE"
                                st.rerun()

    st.divider()

    # ========================================================
    # 📊 LIVE RE-RANKING TABLE & LIVE CHART
    # ========================================================
    st.markdown("#### ⚡ Live Re-ranking Table & Percentage Change Chart")
    
    live_rows = []
    for sym in active_syms:
        tdata = live_ticks.get(sym, csv_baselines.get(sym, {"ltp": 0.0, "cp": 0.0, "Live Change": 0.0}))
        c_ltp = tdata["LTP"] if "LTP" in tdata else tdata.get("ltp", 0.0)
        c_cp = tdata["Previous Close"] if "Previous Close" in tdata else tdata.get("cp", 0.0)
        c_chng = tdata.get("Live Change", ((c_ltp - c_cp) / c_cp * 100) if c_cp else 0.0)
        
        stock_match = df[df["Symbol"] == sym]
        h_score = stock_match["Heuristic Score"].iloc[0] if not stock_match.empty else None
        
        live_rows.append({
            "Selected": "🌟 Focus" if sym == st.session_state["focused_live_stock"] else "",
            "Symbol": sym,
            "Live Price (₹)": round(c_ltp, 2),
            "Previous Close (₹)": round(c_cp, 2),
            "Live Change (%)": round(c_chng, 2),
            "Live Heuristic Score": round(h_score, 2) if h_score else 0.0,
            "Last Traded Time": tdata.get("Last Traded Time", "Live")
        })

    live_table_df = pd.DataFrame(live_rows).sort_values("Live Heuristic Score", ascending=False)
    
    tab_col1, tab_col2 = st.columns([3, 2])
    with tab_col1:
        st.dataframe(live_table_df, use_container_width=True, hide_index=True)
    with tab_col2:
        fig_live = px.bar(
            live_table_df,
            x="Symbol",
            y="Live Change (%)",
            color="Live Change (%)",
            color_continuous_scale="RdYlGn",
            title="Intraday Live Percentage Changes",
            text="Live Change (%)"
        )
        fig_live.update_traces(texttemplate="%{text:+.2f}%", textposition="outside")
        fig_live.update_layout(height=350, yaxis_title="Day Change (%)")
        st.plotly_chart(fig_live, use_container_width=True)


# ============================================================
# TAB 3: DEEP DIVE & STOCK COMPARATOR
# ============================================================

with tab3:
    st.markdown("### 🔍 Individual Stock Deep Dive")

    selected_stock = st.selectbox(
        "Choose Stock for Detailed Analysis",
        sorted(df["Symbol"].unique()),
        index=0
    )

    stock_row = df[df["Symbol"] == selected_stock].iloc[0]

    # Metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current Price (LTP)", f"₹{stock_row['LTP']:,.2f}", f"{stock_row['% Chng']:+.2f}%")
    c2.metric("Day Range", f"₹{stock_row['Low']:,.2f} - ₹{stock_row['High']:,.2f}")
    c3.metric("52-Week Range", f"₹{stock_row['52w L']:,.2f} - ₹{stock_row['52w H']:,.2f}")
    c4.metric("Heuristic Score", f"{stock_row['Heuristic Score']:.2f} / 100")

    # 52-Week Price Range Gauge
    st.markdown("#### 📏 52-Week Price Position Gauge")
    low_52 = stock_row["52w L"]
    high_52 = stock_row["52w H"]
    ltp_val = stock_row["LTP"]

    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=ltp_val,
        title={'text': f"{selected_stock}: Current LTP vs 52-Week High / Low"},
        gauge={
            'axis': {'range': [low_52 * 0.95, high_52 * 1.05]},
            'bar': {'color': "#1E88E5"},
            'steps': [
                {'range': [low_52 * 0.95, low_52 + (high_52 - low_52) * 0.33], 'color': "rgba(239, 83, 80, 0.2)"},
                {'range': [low_52 + (high_52 - low_52) * 0.33, low_52 + (high_52 - low_52) * 0.66], 'color': "rgba(255, 202, 40, 0.2)"},
                {'range': [low_52 + (high_52 - low_52) * 0.66, high_52 * 1.05], 'color': "rgba(102, 187, 106, 0.2)"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 3},
                'thickness': 0.75,
                'value': high_52
            }
        }
    ))
    fig_gauge.update_layout(height=280)
    st.plotly_chart(fig_gauge, use_container_width=True)

    # Heuristic Component Breakdown
    st.markdown("#### 🧠 Heuristic Factor Breakdown")
    breakdown_df = pd.DataFrame({
        "Factor": [
            "30-Day Momentum",
            "365-Day Long Term",
            "Current / Live Change",
            "52-Week Position"
        ],
        "Factor Normalized Score (0-100)": [
            stock_row["30D Score"] * 100,
            stock_row["365D Score"] * 100,
            stock_row["Current Score"] * 100,
            stock_row["52W Position"] * 100
        ],
        "Active Strategy Weight": [
            f"{current_weights['weight_30d']*100:.1f}%",
            f"{current_weights['weight_365d']*100:.1f}%",
            f"{current_weights['weight_current']*100:.1f}%",
            f"{current_weights['weight_52w']*100:.1f}%"
        ]
    })
    
    fig_factor = px.bar(
        breakdown_df,
        x="Factor",
        y="Factor Normalized Score (0-100)",
        color="Factor",
        text="Factor Normalized Score (0-100)",
        title=f"Factor Scores for {selected_stock}"
    )
    fig_factor.update_traces(texttemplate="%{text:.1f}", textposition="outside")
    fig_factor.update_layout(height=350, showlegend=False)
    st.plotly_chart(fig_factor, use_container_width=True)

    st.divider()

    # Side-by-Side Stock Comparator
    st.markdown("### ⚖️ Side-by-Side Stock Comparator")
    comp_col1, comp_col2 = st.columns(2)
    with comp_col1:
        stock_a = st.selectbox("Compare Stock A", sorted(df["Symbol"].unique()), index=0)
    with comp_col2:
        stock_b = st.selectbox("Compare Stock B", sorted(df["Symbol"].unique()), index=min(1, len(df)-1))

    row_a = df[df["Symbol"] == stock_a].iloc[0]
    row_b = df[df["Symbol"] == stock_b].iloc[0]

    comparison_table = pd.DataFrame({
        "Metric": [
            "Current Price (₹)",
            "Today's Change (%)",
            "30-Day Change (%)",
            "365-Day Change (%)",
            "52-Week High (₹)",
            "52-Week Low (₹)",
            "Volume (Lacs)",
            "Heuristic Score h(n)"
        ],
        stock_a: [
            f"₹{row_a['LTP']:,.2f}",
            f"{row_a['% Chng']:+.2f}%",
            f"{row_a['30 d % chng']:+.2f}%",
            f"{row_a['365 d % chng']:+.2f}%",
            f"₹{row_a['52w H']:,.2f}",
            f"₹{row_a['52w L']:,.2f}",
            f"{row_a['Volume (lacs)']:,.2f}",
            f"{row_a['Heuristic Score']:.2f}"
        ],
        stock_b: [
            f"₹{row_b['LTP']:,.2f}",
            f"{row_b['% Chng']:+.2f}%",
            f"{row_b['30 d % chng']:+.2f}%",
            f"{row_b['365 d % chng']:+.2f}%",
            f"₹{row_b['52w H']:,.2f}",
            f"₹{row_b['52w L']:,.2f}",
            f"{row_b['Volume (lacs)']:,.2f}",
            f"{row_b['Heuristic Score']:.2f}"
        ]
    })
    st.dataframe(comparison_table, use_container_width=True, hide_index=True)


# ============================================================
# TAB 4: AI THEORY & ALGORITHM GUIDE
# ============================================================

with tab4:
    st.markdown("### 🧠 AI Methodology: Best-First Search & Upstox Architecture")
    
    st.markdown(r"""
    #### 1. What is Best-First Search (BFS)?
    In Artificial Intelligence, **Best-First Search** is an informed heuristic search algorithm that explores a state space 
    by expanding the most promising node chosen according to an evaluation function $f(n)$.
    
    In TradeMind AI, the evaluation function is pure heuristic estimation:
    $$f(n) = h(n)$$
    
    Where:
    - **Node / State ($n$)**: A candidate stock $s \in S$.
    - **OPEN List (Priority Queue)**: A max-heap data structure storing active candidate nodes ordered by their heuristic estimate $h(n)$.
    - **CLOSED Set**: A hash set storing already visited/extracted nodes to avoid redundant expansions.
    - **Time Complexity**: $O(N \log N)$ to construct the priority queue and $O(K \log N)$ to extract the Top-$K$ recommendations.
    
    #### 2. The Heuristic Evaluation Function $h(s)$
    The heuristic score models investor utility by combining normalized financial factors into a composite score:
    
    $$h(s) = \left( w_{30\text{d}} \cdot S_{30\text{d}} + w_{365\text{d}} \cdot S_{365\text{d}} + w_{\text{curr}} \cdot S_{\text{curr}} + w_{52\text{w}} \cdot P_{52\text{w}} \right) \times 100$$
    
    Where:
    - $S_{30\text{d}}$: Min-max normalized 30-day percentage momentum.
    - $S_{365\text{d}}$: Min-max normalized 1-year compounded trend.
    - $S_{\text{curr}}$: Min-max normalized live day change.
    - $P_{52\text{w}}$: Relative position inside 52-week corridor: $\frac{\text{LTP} - 52\text{w Low}}{52\text{w High} - 52\text{w Low}}$.
    - Weights $\sum w_i = 1$ dynamically configured by investment strategy presets.
    
    #### 3. Real-Time Upstox WebSocket Architecture
    TradeMind AI utilizes the **Upstox MarketDataStreamerV3** protocol:
    1. **Authentication**: Upstox OAuth 2.0 Access Token via `.env`.
    2. **Instrument Key Resolution**: Cached offline JSON index (`data/instrument_keys.json`) with automated API fallback.
    3. **Background Thread**: Asynchronous non-blocking WebSocket daemon (`live_data.py`) streaming tick-by-tick `ltpc` (Last Traded Price & Close) messages.
    4. **Dynamic Fusion**: Incoming ticks seamlessly overwrite historical data points and dynamically trigger real-time heuristic re-ranking.
    """)


# ============================================================
# DISCLAIMER FOOTER
# ============================================================

st.divider()
st.caption(
    "⚠️ **Disclaimer**: TradeMind AI is an educational Artificial Intelligence project demonstrating "
    "heuristic search techniques and real-time financial WebSocket streaming. "
    "Heuristic scores and algorithmic rankings should not be construed as investment advice."
)