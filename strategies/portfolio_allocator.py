import numpy as np
import pandas as pd
from typing import Dict, Any, List
from core.metrics import compute_performance_metrics

def blend_multi_strategy_portfolio(
    results_map: Dict[str, Dict[str, Any]],
    weights: Dict[str, float],
    initial_capital: float = 100000.0
) -> Dict[str, Any]:
    """
    Blends multiple strategies into an institutional multi-strategy portfolio.
    Computes blended equity curve, performance metrics, and correlation matrix.
    """
    strat_keys = list(results_map.keys())
    if not strat_keys:
        return {}

    # Normalize weights
    total_w = sum(weights.get(k, 1.0) for k in strat_keys) or 1.0
    norm_weights = {k: weights.get(k, 1.0) / total_w for k in strat_keys}

    # Extract daily equity series for each strategy
    curves = {}
    bench_curve = None
    for k in strat_keys:
        eq_list = results_map[k]["equity_curve"]
        df_k = pd.DataFrame(eq_list).set_index("date")
        curves[k] = df_k["equity"]
        if bench_curve is None and "benchmark" in df_k.columns:
            bench_curve = df_k["benchmark"]

    df_curves = pd.DataFrame(curves).dropna()
    df_returns = df_curves.pct_change().dropna()

    # Calculate correlation matrix between strategies
    corr_matrix = df_returns.corr().round(3).to_dict()

    # Blended portfolio daily returns
    blended_returns = pd.Series(0.0, index=df_returns.index)
    for k in strat_keys:
        if k in df_returns.columns:
            blended_returns += df_returns[k] * norm_weights[k]

    # Construct blended equity curve
    blended_equity = (1.0 + blended_returns).cumprod() * initial_capital
    blended_equity = pd.concat([pd.Series([initial_capital], index=[df_curves.index[0]]), blended_equity])

    # Reindex benchmark to match dates
    bench_series = bench_curve.reindex(blended_equity.index).ffill() if bench_curve is not None else blended_equity

    # Compute aggregate metrics
    all_trades = []
    for k in strat_keys:
        for t in results_map[k].get("trades", []):
            t_copy = dict(t)
            t_copy["strategy"] = k
            all_trades.append(t_copy)

    metrics = compute_performance_metrics(blended_equity, bench_series, all_trades)

    blended_curve_records = [
        {
            "date": str(d),
            "equity": round(float(blended_equity.loc[d]), 2),
            "benchmark": round(float(bench_series.loc[d]), 2)
        }
        for d in blended_equity.index
    ]

    return {
        "metrics": metrics,
        "weights": {k: round(w, 3) for k, w in norm_weights.items()},
        "correlation_matrix": corr_matrix,
        "equity_curve": blended_curve_records,
        "total_trades": len(all_trades)
    }
