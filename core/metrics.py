import numpy as np
import pandas as pd
from typing import Dict, Any, List

def calculate_drawdown_series(equity_series: pd.Series) -> pd.Series:
    """Calculates rolling drawdown percentage series from equity series"""
    peak = equity_series.cummax()
    drawdown = (equity_series - peak) / peak
    return drawdown

def compute_performance_metrics(
    equity_series: pd.Series,
    benchmark_series: pd.Series,
    trades: List[Dict[str, Any]],
    risk_free_rate: float = 0.02
) -> Dict[str, Any]:
    """
    Computes comprehensive professional quantitative metrics for a strategy run.
    """
    if len(equity_series) < 2:
        return {}

    initial_capital = float(equity_series.iloc[0])
    final_equity = float(equity_series.iloc[-1])
    total_return_pct = ((final_equity - initial_capital) / initial_capital) * 100.0

    # Benchmark returns
    bench_initial = float(benchmark_series.iloc[0])
    bench_final = float(benchmark_series.iloc[-1])
    bench_return_pct = ((bench_final - bench_initial) / bench_initial) * 100.0

    # Daily returns
    strat_daily_ret = equity_series.pct_change().dropna()
    bench_daily_ret = benchmark_series.pct_change().dropna()

    total_days = len(equity_series)
    years = max(total_days / 252.0, 1.0 / 252.0)

    # CAGR (Compound Annual Growth Rate)
    if years > 0 and final_equity > 0:
        cagr = ((final_equity / initial_capital) ** (1.0 / max(years, 0.1)) - 1.0) * 100.0
    else:
        cagr = 0.0

    # Benchmark CAGR
    if years > 0 and bench_final > 0:
        bench_cagr = ((bench_final / bench_initial) ** (1.0 / max(years, 0.1)) - 1.0) * 100.0
    else:
        bench_cagr = 0.0

    # Volatility
    ann_volatility = float(strat_daily_ret.std() * np.sqrt(252) * 100.0) if len(strat_daily_ret) > 1 else 0.0
    bench_ann_vol = float(bench_daily_ret.std() * np.sqrt(252) * 100.0) if len(bench_daily_ret) > 1 else 0.0

    # Sharpe Ratio
    rf_daily = risk_free_rate / 252.0
    excess_ret = strat_daily_ret - rf_daily
    if len(strat_daily_ret) > 1 and strat_daily_ret.std() > 1e-8:
        sharpe = float(np.sqrt(252) * (excess_ret.mean() / strat_daily_ret.std()))
    else:
        sharpe = 0.0

    # Sortino Ratio (Downside volatility)
    downside_returns = strat_daily_ret[strat_daily_ret < 0]
    if len(downside_returns) > 1 and downside_returns.std() > 1e-8:
        sortino = float(np.sqrt(252) * (excess_ret.mean() / downside_returns.std()))
    else:
        sortino = sharpe

    # Max Drawdown
    dd_series = calculate_drawdown_series(equity_series)
    max_drawdown_pct = float(abs(dd_series.min()) * 100.0)

    # Calmar Ratio
    calmar = float(cagr / max_drawdown_pct) if max_drawdown_pct > 0.001 else 0.0

    # Alpha & Beta (strictly aligned by index to prevent length mismatch)
    aligned_rets = pd.concat([strat_daily_ret, bench_daily_ret], axis=1).dropna()
    if len(aligned_rets) > 10:
        s_arr = aligned_rets.iloc[:, 0].values
        b_arr = aligned_rets.iloc[:, 1].values
        cov_matrix = np.cov(s_arr, b_arr)
        bench_var = cov_matrix[1, 1]
        cov_strat_bench = cov_matrix[0, 1]
        beta = float(cov_strat_bench / bench_var) if bench_var > 1e-8 else 1.0
        alpha = float((cagr / 100.0) - (risk_free_rate + beta * ((bench_cagr / 100.0) - risk_free_rate))) * 100.0
    else:
        alpha = 0.0
        beta = 1.0

    # Trade statistics (single-pass accumulation)
    total_trades = len(trades)
    num_wins = 0
    num_losses = 0
    gross_profit = 0.0
    gross_loss = 0.0
    total_holding_days = 0.0

    for t in trades:
        pnl = float(t.get('pnl', 0.0))
        if pnl > 0:
            num_wins += 1
            gross_profit += pnl
        elif pnl < 0:
            num_losses += 1
            gross_loss += abs(pnl)
        total_holding_days += float(t.get('holding_days', 1))

    win_rate = float(num_wins / total_trades * 100.0) if total_trades > 0 else 0.0
    profit_factor = float(gross_profit / gross_loss) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)
    avg_win = float(gross_profit / num_wins) if num_wins > 0 else 0.0
    avg_loss = float(gross_loss / num_losses) if num_losses > 0 else 0.0
    win_loss_payoff = float(avg_win / avg_loss) if avg_loss > 0 else 0.0
    avg_holding_days = float(total_holding_days / total_trades) if total_trades > 0 else 0.0

    # Institutional Risk Measures (VaR, CVaR, Skewness, Kurtosis)
    var_95 = 0.0
    cvar_95 = 0.0
    skewness = 0.0
    kurtosis = 0.0
    tail_ratio = 1.0

    if len(strat_daily_ret) > 15:
        var_quantile = np.percentile(strat_daily_ret, 5.0)
        var_95 = float(abs(var_quantile) * 100.0)
        tail_losses = strat_daily_ret[strat_daily_ret <= var_quantile]
        cvar_95 = float(abs(tail_losses.mean()) * 100.0) if len(tail_losses) > 0 else var_95
        skewness = float(strat_daily_ret.skew())
        kurtosis = float(strat_daily_ret.kurtosis())
        p95 = np.percentile(strat_daily_ret, 95)
        p05 = abs(np.percentile(strat_daily_ret, 5))
        tail_ratio = float(p95 / p05) if p05 > 1e-6 else 1.0

    return {
        "initial_capital": round(initial_capital, 2),
        "final_equity": round(final_equity, 2),
        "total_return_pct": round(total_return_pct, 2),
        "benchmark_return_pct": round(bench_return_pct, 2),
        "cagr_pct": round(cagr, 2),
        "benchmark_cagr_pct": round(bench_cagr, 2),
        "annual_volatility_pct": round(ann_volatility, 2),
        "benchmark_volatility_pct": round(bench_ann_vol, 2),
        "sharpe_ratio": round(sharpe, 2),
        "sortino_ratio": round(sortino, 2),
        "max_drawdown_pct": round(max_drawdown_pct, 2),
        "calmar_ratio": round(calmar, 2),
        "alpha_pct": round(alpha, 2),
        "beta": round(beta, 2),
        "total_trades": total_trades,
        "winning_trades": num_wins,
        "losing_trades": num_losses,
        "win_rate_pct": round(win_rate, 2),
        "profit_factor": round(profit_factor, 2),
        "win_loss_payoff": round(win_loss_payoff, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "avg_holding_days": round(avg_holding_days, 1),
        "var_95_pct": round(var_95, 2),
        "cvar_95_pct": round(cvar_95, 2),
        "skewness": round(skewness, 2),
        "kurtosis": round(kurtosis, 2),
        "tail_ratio": round(tail_ratio, 2)
    }
