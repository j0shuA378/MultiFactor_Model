import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List, Optional

def calculate_garman_klass_volatility(
    high: pd.Series, low: pd.Series, open_p: pd.Series, close: pd.Series, window: int = 20
) -> pd.Series:
    """
    Garman-Klass Volatility:
    An institutional high-efficiency volatility estimator utilizing intraday OHLC.
    8x more statistically efficient than standard close-to-close volatility.
    Formula: 0.5 * ln(H/L)^2 - (2*ln(2) - 1) * ln(C/O)^2
    """
    log_hl = np.log(high / low)
    log_co = np.log(close / open_p)
    gk_var = 0.5 * (log_hl ** 2) - (2.0 * np.log(2.0) - 1.0) * (log_co ** 2)
    rolling_gk = gk_var.rolling(window=window).mean()
    ann_gk_vol = np.sqrt(np.maximum(0.0, rolling_gk) * 252.0) * 100.0
    return ann_gk_vol.bfill()

def calculate_parkinson_volatility(high: pd.Series, low: pd.Series, window: int = 20) -> pd.Series:
    """
    Parkinson Volatility:
    Institutional estimator based on high-low range.
    Formula: sqrt( (1 / (4*ln(2)*n)) * sum(ln(H/L)^2) ) * sqrt(252)
    """
    log_hl = np.log(high / low)
    rolling_var = (log_hl ** 2).rolling(window=window).mean() / (4.0 * np.log(2.0))
    ann_park_vol = np.sqrt(np.maximum(0.0, rolling_var) * 252.0) * 100.0
    return ann_park_vol.bfill()

def winsorize_series(series: pd.Series, method: str = 'mad', n_sigmas: float = 3.0) -> pd.Series:
    """
    Winsorization of factor outliers (Barra / AQR Standard).
    MAD (Median Absolute Deviation):
    median +/- 3 * 1.4826 * MAD
    """
    s = series.copy()
    valid = s.dropna()
    if len(valid) < 10:
        return s

    if method == 'mad':
        med = float(valid.median())
        mad = float((valid - med).abs().median())
        if mad > 1e-8:
            threshold = n_sigmas * 1.4826 * mad
            return s.clip(lower=med - threshold, upper=med + threshold)
        return s
    else:
        mean = float(valid.mean())
        std = float(valid.std())
        if std > 1e-8:
            return s.clip(lower=mean - n_sigmas * std, upper=mean + n_sigmas * std)
        return s

def standardize_factor(series: pd.Series, window: int = 60, min_periods: int = 15) -> pd.Series:
    """
    Rolling time-series Z-score standardization with MAD winsorization.
    Z = (x - rolling_mean) / rolling_std, clipped to [-3.0, 3.0].
    """
    winsorized = winsorize_series(series)
    eff_w = min(window, max(min_periods, len(series) // 3))
    rolling_mean = winsorized.rolling(window=eff_w, min_periods=min_periods).mean()
    rolling_std = winsorized.rolling(window=eff_w, min_periods=min_periods).std().replace(0, np.nan)
    z = (winsorized - rolling_mean) / rolling_std
    return z.fillna(0.0).clip(-3.0, 3.0)

def calculate_12_1_momentum(close: pd.Series, long_window: int = 252, skip_window: int = 21) -> pd.Series:
    """
    Jegadeesh-Titman / Novy-Marx Institutional 12M-1M Momentum:
    Captures intermediate-to-long term momentum while skipping the most recent 1 month (21 days)
    to eliminate microstructure short-term liquidity reversal contamination.
    """
    n = len(close)
    eff_long = min(long_window, max(25, int(n * 0.75)))
    eff_skip = min(skip_window, max(2, int(eff_long * 0.08)))
    mom_12_1 = (close.shift(eff_skip) / close.shift(eff_long)) - 1.0
    return mom_12_1.fillna(0.0)

def calculate_risk_adjusted_momentum(
    close: pd.Series,
    high: Optional[pd.Series] = None,
    low: Optional[pd.Series] = None,
    open_p: Optional[pd.Series] = None,
    window: int = 63,
    vol_window: int = 20
) -> pd.Series:
    """
    Barroso & Santa-Clara (2015) Volatility-Scaled Momentum:
    Scales cumulative returns by realized / Garman-Klass volatility.
    Neutralizes 'Momentum Crashes' during explosive volatility expansions.
    Mom_RiskAdj = Return_window / (Annualized Volatility + epsilon)
    """
    eff_w = min(window, max(15, len(close) // 4))
    raw_ret = (close / close.shift(eff_w)) - 1.0

    if high is not None and low is not None and open_p is not None:
        vol = calculate_garman_klass_volatility(high, low, open_p, close, window=vol_window) / 100.0
    else:
        daily_ret = close.pct_change()
        vol = (daily_ret.rolling(window=vol_window, min_periods=5).std() * np.sqrt(252)).bfill().fillna(0.25)

    risk_adj = raw_ret / (vol + 0.05)
    return risk_adj.fillna(0.0)

def calculate_residual_momentum(
    asset_close: pd.Series,
    market_close: Optional[pd.Series] = None,
    window: int = 60,
    mom_window: int = 20
) -> pd.Series:
    """
    Blitz, Falkeling & Swinkels (2011) Beta-Neutral Residual Momentum:
    Extracts pure idiosyncratic alpha by hedging out systematic market benchmark exposure.
    Residual return: epsilon_t = R_i,t - beta_i,lagged * R_m,t
    ResMom = Rolling_Mean(epsilon, mom_window) / Rolling_Std(epsilon, window)
    """
    r_asset = asset_close.pct_change().fillna(0.0)
    if market_close is not None and len(market_close) == len(asset_close):
        r_market = market_close.pct_change().fillna(0.0)
    else:
        # High-order exponential smoothed drift as market proxy
        r_market = r_asset.ewm(span=window, adjust=False).mean()

    eff_w = min(window, max(20, len(asset_close) // 4))
    cov = r_asset.rolling(window=eff_w, min_periods=10).cov(r_market)
    var_m = r_market.rolling(window=eff_w, min_periods=10).var()
    beta = (cov / var_m).fillna(1.0).clip(0.1, 3.0)

    # Use lagged beta to prevent forward lookahead bias
    res_daily = r_asset - beta.shift(1).fillna(1.0) * r_market
    eff_mom = min(mom_window, max(5, eff_w // 3))
    res_mean = res_daily.rolling(window=eff_mom, min_periods=5).mean() * np.sqrt(252)
    res_std = (res_daily.rolling(window=eff_w, min_periods=10).std() * np.sqrt(252)).replace(0, np.nan)

    res_mom = res_mean / (res_std + 1e-4)
    return res_mom.fillna(0.0)

def calculate_trend_quality_momentum(close: pd.Series, window: int = 40) -> pd.Series:
    """
    Frog-in-the-Pan (Da, Gurun, Warachka 2014) Trend Quality Momentum:
    Measures trajectory smoothness and continuous information flow.
    Calculates rolling OLS slope of log-prices multiplied by R-squared goodness-of-fit.
    Smooth persistent drift scores high; sporadic jump spikes score low.
    """
    eff_w = min(window, max(15, len(close) // 4))
    log_p = np.log(close.values)
    n = len(log_p)
    out_vals = np.full(n, np.nan, dtype=np.float64)

    x = np.arange(eff_w, dtype=np.float64)
    x_mean = x.mean()
    x_dev = x - x_mean
    ss_x = np.dot(x_dev, x_dev)

    for i in range(eff_w - 1, n):
        sub_y = log_p[i - eff_w + 1 : i + 1]
        y_mean = sub_y.mean()
        y_dev = sub_y - y_mean
        ss_y = np.dot(y_dev, y_dev)
        if ss_y <= 1e-8:
            out_vals[i] = 0.0
            continue
        ss_xy = np.dot(x_dev, y_dev)
        slope = ss_xy / ss_x
        r2 = (ss_xy * ss_xy) / (ss_x * ss_y)
        out_vals[i] = slope * r2

    return pd.Series(out_vals, index=close.index).bfill().fillna(0.0)

def calculate_volume_confirmed_momentum(close: pd.Series, volume: pd.Series, window: int = 20) -> pd.Series:
    """
    Lee & Swaminathan (2000) Volume-Confirmed Momentum:
    Validates momentum when price gains are accompanied by institutional volume accumulation.
    Volume Surge Multiplier = Volume / Rolling_SMA(Volume)
    """
    eff_w = min(window, max(5, len(close) // 10))
    ret = (close / close.shift(eff_w) - 1.0).fillna(0.0)
    vol_sma = volume.rolling(window=eff_w, min_periods=3).mean().replace(0, np.nan)
    vol_ratio = (volume / vol_sma).fillna(1.0).clip(0.5, 3.0)
    return (ret * vol_ratio).fillna(0.0)

def calculate_information_coefficient(factor_scores: pd.Series, forward_returns: pd.Series) -> float:
    """
    Information Coefficient (IC):
    Spearman rank correlation between factor score at time t and forward return at t+k.
    The benchmark metric used by institutional quantitative asset managers to assess factor efficacy.
    """
    valid = pd.concat([factor_scores, forward_returns], axis=1).dropna()
    if len(valid) < 10:
        return 0.0
    rank_ic = valid.iloc[:, 0].corr(valid.iloc[:, 1], method='spearman')
    return float(round(rank_ic, 4)) if not np.isnan(rank_ic) else 0.0

def calculate_rolling_ic(factor_scores: pd.Series, forward_returns: pd.Series, window: int = 40) -> pd.Series:
    """Rolling Rank Information Coefficient over time"""
    valid = pd.concat([factor_scores, forward_returns], axis=1).dropna()
    eff_w = min(window, max(15, len(valid) // 3))
    # Rolling rank transformation to maintain Spearman rank consistency
    r1 = valid.iloc[:, 0].rolling(window=eff_w).rank()
    r2 = valid.iloc[:, 1].rolling(window=eff_w).rank()
    rolling_ic = r1.rolling(window=eff_w).corr(r2)
    return rolling_ic.fillna(0.0)

def calculate_factor_ir(rolling_ic: pd.Series) -> Dict[str, float]:
    """
    Calculates Information Ratio (IR) and t-statistic of Factor IC:
    IR = Mean(IC) / Std(IC)
    t-stat = Mean(IC) / (Std(IC) / sqrt(N))
    """
    clean_ic = rolling_ic.dropna()
    if len(clean_ic) < 5:
        return {"ic_mean": 0.0, "ic_std": 0.0, "ir": 0.0, "t_stat": 0.0}
    ic_mean = float(clean_ic.mean())
    ic_std = float(clean_ic.std())
    n = len(clean_ic)
    ir = float(ic_mean / ic_std) if ic_std > 1e-6 else 0.0
    t_stat = float(ic_mean / (ic_std / np.sqrt(n))) if ic_std > 1e-6 else 0.0
    return {
        "ic_mean": round(ic_mean, 4),
        "ic_std": round(ic_std, 4),
        "ir": round(ir, 3),
        "t_stat": round(t_stat, 2)
    }

def calculate_factor_decay_ic(factor_scores: pd.Series, close: pd.Series, lags: Optional[List[int]] = None) -> Dict[str, float]:
    """Computes IC term structure decay profile across forward horizons"""
    if lags is None:
        lags = [1, 3, 5, 10, 20]
    decay = {}
    for lag in lags:
        if len(close) > lag + 5:
            fwd_ret = (close.shift(-lag) / close) - 1.0
            ic = calculate_information_coefficient(factor_scores, fwd_ret)
            decay[f"{lag}D"] = ic
    return decay

def calculate_quintile_spread(factor_scores: pd.Series, forward_returns: pd.Series) -> Dict[str, float]:
    """
    Computes top vs bottom quantile forward return spread (Q5 - Q1).
    Tests monotonicity and long-short efficacy.
    """
    valid = pd.DataFrame({"factor": factor_scores, "fwd_ret": forward_returns}).dropna()
    if len(valid) < 20:
        return {"q5_return": 0.0, "q1_return": 0.0, "spread": 0.0}
    try:
        valid["quantile"] = pd.qcut(valid["factor"], q=5, labels=False, duplicates='drop')
        means = valid.groupby("quantile")["fwd_ret"].mean()
        q1 = float(means.iloc[0]) if len(means) > 0 else 0.0
        q5 = float(means.iloc[-1]) if len(means) > 0 else 0.0
        return {
            "q5_return": round(q5 * 100.0, 2),
            "q1_return": round(q1 * 100.0, 2),
            "spread": round((q5 - q1) * 100.0, 2)
        }
    except Exception:
        return {"q5_return": 0.0, "q1_return": 0.0, "spread": 0.0}

def compute_institutional_risk_measures(returns: pd.Series, confidence: float = 0.95) -> Dict[str, float]:
    """
    Computes institutional risk management metrics:
    - Value at Risk (Historical VaR 95%)
    - Conditional Value at Risk (CVaR / Expected Shortfall 95%)
    - Skewness (偏度: asymmetry of return distribution)
    - Kurtosis (峰度: fat-tail risk)
    - Tail Ratio (95th percentile vs 5th percentile)
    """
    clean_rets = returns.dropna()
    if len(clean_rets) < 20:
        return {"var_95_pct": 0.0, "cvar_95_pct": 0.0, "skewness": 0.0, "kurtosis": 0.0, "tail_ratio": 1.0}

    # Historical VaR (percentage loss)
    var_quantile = np.percentile(clean_rets, (1.0 - confidence) * 100.0)
    var_95 = float(abs(var_quantile) * 100.0)

    # CVaR (Expected Shortfall) = Average loss beyond VaR threshold
    tail_losses = clean_rets[clean_rets <= var_quantile]
    cvar_95 = float(abs(tail_losses.mean()) * 100.0) if len(tail_losses) > 0 else var_95

    # Skewness & Kurtosis
    skew = float(clean_rets.skew())
    kurt = float(clean_rets.kurtosis())

    # Tail Ratio
    p95 = np.percentile(clean_rets, 95)
    p05 = abs(np.percentile(clean_rets, 5))
    tail_ratio = float(p95 / p05) if p05 > 1e-6 else 1.0

    return {
        "var_95_pct": round(var_95, 2),
        "cvar_95_pct": round(cvar_95, 2),
        "skewness": round(skew, 2),
        "kurtosis": round(kurt, 2),
        "tail_ratio": round(tail_ratio, 2)
    }

def target_volatility_position_sizing(
    realized_volatility: pd.Series,
    target_vol_annual: float = 0.15,
    max_leverage: float = 1.0
) -> pd.Series:
    """
    Volatility Targeting (AQR / Bridgewater Institutional Sizing):
    Scales position sizing inversely with market volatility so that portfolio risk remains steady.
    Weight_t = min(max_leverage, target_vol / realized_vol_t)
    """
    ann_vol_dec = realized_volatility / 100.0
    safe_vol = ann_vol_dec.replace(0, np.nan).fillna(target_vol_annual)
    raw_weights = target_vol_annual / safe_vol
    clipped_weights = raw_weights.clip(lower=0.2, upper=max_leverage)
    return clipped_weights
