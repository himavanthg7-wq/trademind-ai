"""
TradeMind AI - Best-First Search & Heuristic Evaluation Module
Implements an AI Best-First Search algorithm using a Priority Queue (OPEN list)
and CLOSED set to evaluate and recommend optimal stock selections based on multi-factor heuristics.
"""

import heapq
import pandas as pd
import numpy as np


# Predefined investment strategy heuristic presets
HEURISTIC_PRESETS = {
    "Balanced": {
        "weight_30d": 0.30,
        "weight_365d": 0.25,
        "weight_current": 0.20,
        "weight_52w": 0.25,
        "description": "Balanced mix of short-term momentum, long-term trend, and 52-week position."
    },
    "Momentum Chaser": {
        "weight_30d": 0.45,
        "weight_365d": 0.15,
        "weight_current": 0.30,
        "weight_52w": 0.10,
        "description": "Prioritizes stocks with strong recent momentum and intraday surges."
    },
    "Long-Term Value": {
        "weight_30d": 0.10,
        "weight_365d": 0.50,
        "weight_current": 0.10,
        "weight_52w": 0.30,
        "description": "Focuses on 1-year compounded gains and established price levels."
    },
    "Mean Reversion / Value Dip": {
        "weight_30d": 0.15,
        "weight_365d": 0.40,
        "weight_current": 0.05,
        "weight_52w": 0.40,
        "description": "Emphasizes solid 1-year foundations trading at favorable 52-week support."
    }
}


def normalize_series(series: pd.Series) -> pd.Series:
    """Normalize a pandas Series to [0, 1] range via min-max scaling."""
    s_min = series.min()
    s_max = series.max()
    if s_max == s_min:
        return pd.Series(0.5, index=series.index)
    return (series - s_min) / (s_max - s_min)


def compute_heuristic_scores(df: pd.DataFrame, weights: dict = None) -> pd.DataFrame:
    """
    Computes normalized factor scores and the final composite heuristic score h(s).
    
    Factors:
      - 30D Score: 30-day percentage performance
      - 365D Score: 365-day percentage performance
      - Current Score: Current / live day change percentage
      - 52W Position: Current price relative to 52-week Low and High
    """
    data = df.copy()

    if weights is None:
        weights = HEURISTIC_PRESETS["Balanced"]

    w_30d = weights.get("weight_30d", 0.30)
    w_365d = weights.get("weight_365d", 0.25)
    w_curr = weights.get("weight_current", 0.20)
    w_52w = weights.get("weight_52w", 0.25)

    # Normalize weights so they sum to 1.0
    w_sum = w_30d + w_365d + w_curr + w_52w
    if w_sum > 0:
        w_30d /= w_sum
        w_365d /= w_sum
        w_curr /= w_sum
        w_52w /= w_sum

    # Calculate factor scores
    if "30 d % chng" in data.columns:
        data["30D Score"] = normalize_series(data["30 d % chng"])
    else:
        data["30D Score"] = 0.5

    if "365 d % chng" in data.columns:
        data["365D Score"] = normalize_series(data["365 d % chng"])
    else:
        data["365D Score"] = 0.5

    # Use live change if present, else fallback to static % Chng
    curr_col = "Live Change" if "Live Change" in data.columns else "% Chng"
    if curr_col in data.columns:
        data["Current Score"] = normalize_series(data[curr_col])
    else:
        data["Current Score"] = 0.5

    # 52-week position
    if "52w H" in data.columns and "52w L" in data.columns and "LTP" in data.columns:
        range_52w = data["52w H"] - data["52w L"]
        data["52W Position"] = np.where(
            range_52w > 0,
            (data["LTP"] - data["52w L"]) / range_52w,
            0.5
        )
        data["52W Position"] = data["52W Position"].clip(0.0, 1.0)
    else:
        data["52W Position"] = 0.5

    # Composite Heuristic Score h(n) scaled to 0 - 100
    data["Heuristic Score"] = (
        data["30D Score"] * w_30d +
        data["365D Score"] * w_365d +
        data["Current Score"] * w_curr +
        data["52W Position"] * w_52w
    ) * 100

    return data


class StockSearchNode:
    """Represents a search state/node in the Best-First Search space."""

    def __init__(self, symbol: str, score: float, row_data: pd.Series):
        self.symbol = symbol
        self.score = score
        self.row_data = row_data

    def __lt__(self, other):
        # Max-heap priority queue: higher score has higher priority
        return self.score > other.score


def best_first_search(stocks: pd.DataFrame, top_k: int = 1, return_trace: bool = False):
    """
    AI Best-First Search implementation using a Priority Queue (OPEN list)
    and Visited Set (CLOSED list).
    
    Parameters:
      - stocks: DataFrame containing stock records with 'Heuristic Score'.
      - top_k: Number of top candidate stocks to extract.
      - return_trace: If True, returns (results, search_trace_list).
    
    Returns:
      - If top_k == 1 and not return_trace: Single best stock pd.Series (backward compatible).
      - If top_k > 1 and not return_trace: DataFrame of top_k stocks.
      - If return_trace: tuple (results, trace_logs).
    """
    if stocks is None or stocks.empty:
        if return_trace:
            return None, []
        return None

    if "Heuristic Score" not in stocks.columns:
        stocks = compute_heuristic_scores(stocks)

    # OPEN List: Priority queue of candidate states ordered by heuristic h(n)
    open_list = []
    for idx, row in stocks.iterrows():
        symbol = row.get("Symbol", f"Stock_{idx}")
        score = float(row["Heuristic Score"])
        node = StockSearchNode(symbol, score, row)
        heapq.heappush(open_list, node)

    closed_set = set()
    selected_nodes = []
    search_trace = []
    step = 0

    total_candidates = len(open_list)

    # Expand the most promising node at each step
    while open_list and len(selected_nodes) < top_k:
        step += 1
        best_node = heapq.heappop(open_list)
        symbol = best_node.symbol

        if symbol in closed_set:
            continue

        closed_set.add(symbol)
        selected_nodes.append(best_node)

        search_trace.append({
            "step": step,
            "expanded_node": symbol,
            "heuristic_score": round(best_node.score, 2),
            "open_queue_size": len(open_list),
            "closed_nodes_count": len(closed_set),
            "rank": len(selected_nodes),
            "reasoning": (
                f"Expanded state {symbol} with highest heuristic score h(n) = {best_node.score:.2f}. "
                f"Remaining in frontier: {len(open_list)} nodes."
            )
        })

    if not selected_nodes:
        if return_trace:
            return None, search_trace
        return None

    if top_k == 1 and not return_trace:
        return selected_nodes[0].row_data

    result_df = pd.DataFrame([n.row_data for n in selected_nodes])

    if return_trace:
        return result_df, search_trace

    return result_df