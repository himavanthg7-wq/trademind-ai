# 📈 TradeMind AI: AI-Based NSE Stock Analysis

TradeMind AI is an Artificial Intelligence stock analysis and recommendation engine combining **Heuristic Best-First Search (BFS)** with **Real-Time Market Data Streaming** powered by the **Upstox API**.

---

## 🌟 Key Features

1. **AI Best-First Search (BFS) Engine**:
   - Implements informed search state expansion using a **Priority Queue (OPEN list)** and **Explored Set (CLOSED list)**.
   - Evaluates candidate stocks via a configurable composite heuristic function $h(n)$.
   - Full search trajectory inspection: view step-by-step priority queue popping, frontier size, and ranking rationale.

2. **Real-Time Market Streaming (Upstox WebSocket)**:
   - Live tick streaming via Upstox `MarketDataStreamerV3`.
   - Real-time Last Traded Price (LTP), Previous Close, and Intraday % Change.
   - Dynamic real-time heuristic score re-ranking based on live market ticks.
   - Automatic off-hours simulation generator to demonstrate live updates 24/7.

3. **Multi-Strategy Investment Presets**:
   - **Balanced**: Standard combination of momentum, long-term stability, and 52-week price range.
   - **Momentum Chaser**: Prioritizes short-term 30-day velocity and intraday price surges.
   - **Long-Term Value**: Heavy emphasis on 365-day compounded gains and historical resilience.
   - **Mean Reversion / Value Dip**: Targets stocks trading near favorable 52-week support with strong 1-year foundations.
   - **Custom Weights**: Fully customizable sliders for all heuristic components.

4. **Interactive Visualization Suite**:
   - Top-$K$ Heuristic Rankings bar chart with dynamic gradient scaling.
   - 30-Day vs 365-Day performance comparative analysis.
   - Risk/Valuation landscape scatter plot (LTP vs Heuristic Score sized by trading volume).
   - 52-Week Range position gauge with dynamic target thresholds.
   - Side-by-side comparative stock matrix.

---

## 🏗️ System Architecture

```
TradeMind AI
├── app.py                      # Main Streamlit Dashboard UI & Multi-Tab Analytics
├── heuristic.py                # AI Best-First Search, Priority Queue & Heuristic Scoring
├── live_data.py                # Thread-Safe Singleton Upstox WebSocket Stream Manager
├── instruments.py              # Upstox Instrument Key Resolution & JSON Caching
├── run_app.bat                 # One-Click Windows Launcher Script
├── requirements.txt            # Python Dependencies
├── .env                        # Upstox OAuth Token Configuration
└── data/
    ├── National_Stock_Exchange_of_India_Ltd.csv  # 50 NSE Equity Dataset
    └── instrument_keys.json                      # Cached Instrument Mappings
```

---

## 🧠 Artificial Intelligence Methodology

### 1. Best-First Search Formulation
- **State Space ($S$)**: Universe of available NSE equity instruments $\{s_1, s_2, \dots, s_N\}$.
- **Evaluation Function**: $f(n) = h(n)$, where $h(n)$ is the heuristic estimated desirability.
- **OPEN List**: Max-heap Priority Queue ordered by $h(n)$.
- **CLOSED Set**: Visited hash set preventing duplicate state evaluation.
- **Goal Condition**: Extraction of the top $K$ optimal states.

### 2. Heuristic Formula $h(s)$
$$h(s) = \left( w_{30\text{d}} \cdot S_{30\text{d}} + w_{365\text{d}} \cdot S_{365\text{d}} + w_{\text{curr}} \cdot S_{\text{curr}} + w_{52\text{w}} \cdot P_{52\text{w}} \right) \times 100$$

Where:
- $S_{30\text{d}}$: Min-Max normalized 30-day percentage momentum.
- $S_{365\text{d}}$: Min-Max normalized 365-day percentage trend.
- $S_{\text{curr}}$: Min-Max normalized live / current day percentage change.
- $P_{52\text{w}} = \text{clip}\left(\frac{\text{LTP} - 52\text{w Low}}{52\text{w High} - 52\text{w Low}}, 0, 1\right)$: 52-week corridor positioning.
- $\sum w_i = 1$: Dynamically configured strategy weights.

---

## 🚀 Quick Start & Usage

### 1. Prerequisites
- Python 3.10+ installed.

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Upstox API Token (Optional / Already Set)
In the `.env` file:
```env
UPSTOX_ACCESS_TOKEN=your_access_token_here
```
*(If no token is provided, the application automatically uses cached instrument data and simulated market ticks).*

### 4. Launch Application
You can run:
```bash
streamlit run app.py
```
Or double-click `run_app.bat` on Windows!

---

## 🧪 Test Scripts

The project includes standalone verification scripts:
- `python instruments.py`: Tests instrument key resolution and cache.
- `python test_live.py`: Tests Upstox WebSocket live streaming connection.
- `python test_change.py`: Tests live percentage change calculation.
- `python test_combined.py`: Tests combined live feeds with timestamping.
