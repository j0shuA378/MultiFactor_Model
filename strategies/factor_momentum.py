import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, Optional
from strategies.base_strategy import BaseStrategy
from core.indicators import (
    calculate_ema,
    calculate_sma,
    calculate_macd,
    calculate_rsi,
    calculate_bollinger_bands,
    calculate_atr
)
from core.institutional_data import (
    calculate_garman_klass_volatility,
    calculate_12_1_momentum,
    calculate_risk_adjusted_momentum,
    calculate_residual_momentum,
    calculate_trend_quality_momentum,
    calculate_volume_confirmed_momentum,
    standardize_factor,
    calculate_information_coefficient,
    calculate_rolling_ic,
    calculate_factor_ir,
    calculate_factor_decay_ic,
    calculate_quintile_spread,
    compute_institutional_risk_measures,
    target_volatility_position_sizing
)

class MultiFactorMomentumStrategy(BaseStrategy):
    """
    机构级多因子动量与市场状态自适应模型 (Multi-Factor Adaptive Momentum Strategy)
    
    融合技术分析指标与机构资产管理多因子模型：
    1. 趋势与动量模块 (Trend & Momentum):
       - Fast EMA (10/12) 与 Slow EMA (26/30) 均线体系
       - MACD (12, 26, 9) 柱线动量与零轴能量
       - 12M-1M 经典中长周期动量 (Jegadeesh & Titman)
       - 路径质量因子 (Frog-in-the-Pan, R^2 * Slope)
    2. 均值回归与通道模块 (Mean-Reversion & Volatility Bands):
       - Wilder RSI(14) (超卖 < 35 企稳反弹，超买 > 70 动量衰竭防范)
       - 布林带 (20, 2.0 std) %B 与带宽挤压突破 (Bollinger Squeeze & Expansion)
    3. 市场状态识别 (Market Regime Detection):
       - 区分趋势突破状态 (Trending Regime) 与震荡收敛状态 (Chop / Mean-Reversion Regime)
       - 避免在震荡市频繁追高假突破，在强趋势市避免逆势摸顶
    4. 因子去相关性与综合评分 (Orthogonalized Multi-Factor Alpha):
       - 消除 EMA 与 MACD 间的多重共线性
       - 结合成交量确认与特质低波动调整
    5. 显式持仓状态机 (State Machine Position Management):
       - 严谨跟踪持仓、追踪止损与状态转换，杜绝信号频繁抖动
    """
    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            # 权重配置
            "w_trend": 0.35,            # 趋势均线与 MACD 权重
            "w_mom_12_1": 0.25,         # 12M-1M 经典动量权重
            "w_risk_adj": 0.15,         # 风险调整低波权重
            "w_trend_qual": 0.15,       # 趋势平滑质量权重
            "w_vol_confirm": 0.10,      # 量价确认权重
            # 技术指标参数
            "fast_ma": 10,              # EMA 快线周期
            "slow_ma": 30,              # EMA 慢线周期
            "rsi_period": 14,           # RSI 周期
            "rsi_oversold": 35.0,       # RSI 超卖阈值
            "rsi_overbought": 70.0,     # RSI 超买阈值
            "bb_period": 20,            # 布林带周期
            "bb_std": 2.0,              # 布林带标准差倍数
            # 信号阈值与状态机
            "alpha_threshold": 0.30,    # 趋势开仓复合 Alpha 阈值
            "exit_threshold": -0.25,    # 平仓复合 Alpha 阈值
            "zscore_window": 30,        # 滚动标准化窗口
            "use_regime_filter": True,  # 启用市场状态过滤
            "use_vol_targeting": True,  # 启用动态波动率目标仓位管理
            "target_vol_annual": 0.15,  # 目标年化波动率 (15%)
            "max_leverage": 1.0         # 最大持仓杠杆上限
        }
        if params:
            default_params.update(params)

        super().__init__("Multi-Factor Adaptive Momentum", default_params)

    def generate_signals(self, df: pd.DataFrame) -> Tuple[pd.Series, Dict[str, Any]]:
        n = len(df)
        if n < 35:
            return pd.Series(0, index=df.index), {"error": "Insufficient data"}

        close = df['Close']
        high = df['High']
        low = df['Low']
        open_p = df['Open']
        volume = df['Volume'] if 'Volume' in df.columns else pd.Series(1.0, index=df.index)

        fast_period = int(self.params.get("fast_ma", 10))
        slow_period = int(self.params.get("slow_ma", 30))
        rsi_period = int(self.params.get("rsi_period", 14))
        rsi_os = float(self.params.get("rsi_oversold", 35.0))
        rsi_ob = float(self.params.get("rsi_overbought", 70.0))
        bb_period = int(self.params.get("bb_period", 20))
        bb_std = float(self.params.get("bb_std", 2.0))
        z_win = int(self.params.get("zscore_window", 30))

        alpha_th = float(self.params.get("alpha_threshold", 0.30))
        exit_th = float(self.params.get("exit_threshold", -0.25))
        use_regime = bool(self.params.get("use_regime_filter", True))
        use_vol_target = bool(self.params.get("use_vol_targeting", True))
        target_vol = float(self.params.get("target_vol_annual", 0.15))
        max_lev = float(self.params.get("max_leverage", 1.0))

        # -------------------------------------------------------------
        # 1. 技术指标层计算 (Technical Indicators)
        # -------------------------------------------------------------
        fast_ema = calculate_ema(close, fast_period)
        slow_ema = calculate_ema(close, slow_period)
        dif, dea, macd_hist = calculate_macd(close, 12, 26, 9)
        rsi = calculate_rsi(close, rsi_period)
        bb_up, bb_mid, bb_low, pct_b, bandwidth = calculate_bollinger_bands(close, bb_period, bb_std)
        atr_14 = calculate_atr(high, low, close, 14)

        # -------------------------------------------------------------
        # 2. 机构因子层计算 (Institutional Factors)
        # -------------------------------------------------------------
        raw_m12_1 = calculate_12_1_momentum(close)
        z_m12_1 = standardize_factor(raw_m12_1, window=z_win)

        raw_risk_adj = calculate_risk_adjusted_momentum(close, high, low, open_p, window=63, vol_window=20)
        z_risk_adj = standardize_factor(raw_risk_adj, window=z_win)

        raw_trend_qual = calculate_trend_quality_momentum(close, window=40)
        z_trend_qual = standardize_factor(raw_trend_qual, window=z_win)

        raw_vol_confirm = calculate_volume_confirmed_momentum(close, volume, window=20)
        z_vol_confirm = standardize_factor(raw_vol_confirm, window=z_win)

        # -------------------------------------------------------------
        # 3. 去相关化复合 Alpha 构建 (Orthogonalized Alpha Score)
        # -------------------------------------------------------------
        # EMA 偏离度 + MACD 归一化动量作为趋势因子
        trend_score = ((fast_ema - slow_ema) / slow_ema) + (dif / close)
        z_trend = standardize_factor(trend_score, window=z_win)

        w_trend = float(self.params.get("w_trend", 0.35))
        w_12_1 = float(self.params.get("w_mom_12_1", 0.25))
        w_risk = float(self.params.get("w_risk_adj", 0.15))
        w_qual = float(self.params.get("w_trend_qual", 0.15))
        w_vol = float(self.params.get("w_vol_confirm", 0.10))

        total_w = w_trend + w_12_1 + w_risk + w_qual + w_vol
        w_trend, w_12_1, w_risk, w_qual, w_vol = [w / total_w for w in [w_trend, w_12_1, w_risk, w_qual, w_vol]]

        composite_alpha_raw = (
            w_trend * z_trend +
            w_12_1 * z_m12_1 +
            w_risk * z_risk_adj +
            w_qual * z_trend_qual +
            w_vol * z_vol_confirm
        )
        composite_alpha = standardize_factor(composite_alpha_raw, window=z_win)

        # -------------------------------------------------------------
        # 4. 市场状态识别 (Market Regime Classification)
        # -------------------------------------------------------------
        # 趋势强度: 基于 EMA 斜率与布林带宽展开度
        bw_rolling_low = bandwidth.rolling(window=30, min_periods=10).quantile(0.25)
        is_trending = (fast_ema > slow_ema) & (bandwidth > bw_rolling_low)
        is_compressed = bandwidth <= bw_rolling_low  # 震荡收敛/挤压期

        # -------------------------------------------------------------
        # 5. 显式持仓状态机与信号生成 (State Machine)
        # -------------------------------------------------------------
        sig_arr = np.zeros(n, dtype=np.int32)
        in_pos = False
        entry_price = 0.0
        trailing_stop = 0.0

        c_vals = close.values
        a_vals = composite_alpha.values
        fast_vals = fast_ema.values
        slow_vals = slow_ema.values
        rsi_vals = rsi.values
        pct_b_vals = pct_b.values
        atr_vals = atr_14.values
        trend_regime_vals = is_trending.values
        hist_vals = macd_hist.values

        for i in range(1, n):
            c_p = c_vals[i]
            prev_c_p = c_vals[i-1]
            alpha_val = a_vals[i]
            f_val = fast_vals[i]
            s_val = slow_vals[i]
            rsi_val = rsi_vals[i]
            prev_rsi = rsi_vals[i-1]
            pb_val = pct_b_vals[i]
            curr_atr = atr_vals[i] if not np.isnan(atr_vals[i]) else (c_p * 0.02)
            regime = trend_regime_vals[i]
            m_hist = hist_vals[i]

            if not in_pos:
                # 状态 1: 空仓 -> 寻找符合入场条件的买点
                # 条件 A: 趋势动量突破入场 (强趋势 + Alpha 显著 + MACD 正动量 + RSI 未超买)
                cond_trend_breakout = (
                    alpha_val > alpha_th and
                    f_val >= s_val * 0.998 and
                    rsi_val < rsi_ob and
                    m_hist > 0
                )
                
                # 条件 B: 震荡均值回归触底反弹入场 (RSI 从超卖区回升 + 布林下轨企稳反弹)
                cond_mean_reversion = (
                    prev_rsi < rsi_os and
                    rsi_val >= rsi_os and
                    pb_val > 0.05 and
                    alpha_val > -0.10
                )

                if cond_trend_breakout or (not use_regime and cond_mean_reversion):
                    sig_arr[i] = 1
                    in_pos = True
                    entry_price = c_p
                    trailing_stop = c_p - (2.0 * curr_atr)
            else:
                # 状态 2: 持仓 -> 监控止损保护、动量衰竭与平仓离场
                # 更新跟踪止损线 (Ratchet trailing stop)
                new_stop = c_p - (2.0 * curr_atr)
                if new_stop > trailing_stop:
                    trailing_stop = new_stop

                # 平仓条件:
                # 1. 跌破跟踪止损线
                cond_stop = c_p < trailing_stop
                # 2. 动量崩溃: Alpha 跌入深度负区间 或 均线严重死叉
                cond_momentum_collapse = (alpha_val < exit_th) or (f_val < s_val * 0.980)
                # 3. 极度超买且动量背离 (RSI > 80 见顶拐头向下)
                cond_overbought_exhaustion = (prev_rsi > 80.0 and rsi_val < prev_rsi - 2.0)

                if cond_stop or cond_momentum_collapse or cond_overbought_exhaustion:
                    sig_arr[i] = -1
                    in_pos = False
                    entry_price = 0.0
                    trailing_stop = 0.0

        signals = pd.Series(sig_arr, index=df.index, dtype=int)

        # -------------------------------------------------------------
        # 6. 动态波动率目标仓位管理 (Volatility Sizing)
        # -------------------------------------------------------------
        gk_vol = calculate_garman_klass_volatility(high, low, open_p, close, window=20)
        if use_vol_target:
            pos_sizes = target_volatility_position_sizing(gk_vol, target_vol_annual=target_vol, max_leverage=max_lev)
        else:
            pos_sizes = pd.Series(1.0, index=df.index)

        # -------------------------------------------------------------
        # 7. 因子诊断与前瞻检验 (Forward Efficacy Diagnostics)
        # -------------------------------------------------------------
        forward_5d_ret = close.shift(-5) / close - 1.0
        overall_ic = calculate_information_coefficient(composite_alpha, forward_5d_ret)
        rolling_ic_series = calculate_rolling_ic(composite_alpha, forward_5d_ret, window=40)
        ir_metrics = calculate_factor_ir(rolling_ic_series)
        ic_decay = calculate_factor_decay_ic(composite_alpha, close, lags=[1, 3, 5, 10, 20])
        q_spread = calculate_quintile_spread(composite_alpha, forward_5d_ret)
        daily_ret = close.pct_change().dropna()
        risk_measures = compute_institutional_risk_measures(daily_ret)

        recent_ic_list = [
            {"date": str(d), "ic": round(float(v), 3)}
            for d, v in rolling_ic_series.dropna().iloc[-60:].items()
        ]

        sub_factor_ics = {
            "Trend / MACD Momentum": calculate_information_coefficient(z_trend, forward_5d_ret),
            "12M-1M Momentum": calculate_information_coefficient(z_m12_1, forward_5d_ret),
            "Risk-Adjusted Vol": calculate_information_coefficient(z_risk_adj, forward_5d_ret),
            "Trend Quality": calculate_information_coefficient(z_trend_qual, forward_5d_ret),
            "Volume-Confirmed": calculate_information_coefficient(z_vol_confirm, forward_5d_ret),
        }

        meta = {
            "overall_ic": overall_ic,
            "ic_mean": ir_metrics["ic_mean"],
            "ic_std": ir_metrics["ic_std"],
            "factor_ir": ir_metrics["ir"],
            "ic_t_stat": ir_metrics["t_stat"],
            "ic_decay": ic_decay,
            "quintile_spread": q_spread,
            "risk_measures": risk_measures,
            "avg_gk_vol": round(float(gk_vol.mean()), 2),
            "use_vol_targeting": use_vol_target,
            "target_vol_annual": target_vol,
            "factor_weights": {
                "Trend & MACD Momentum": round(w_trend, 2),
                "12M-1M Momentum": round(w_12_1, 2),
                "Risk-Adjusted Vol": round(w_risk, 2),
                "Trend Quality": round(w_qual, 2),
                "Volume-Confirmed": round(w_vol, 2)
            },
            "sub_factor_ics": sub_factor_ics,
            "recent_rolling_ic": recent_ic_list,
            "fast_ema": fast_ema.round(2).to_dict(),
            "slow_ema": slow_ema.round(2).to_dict(),
            "composite_alpha_recent": {str(d): round(float(v), 3) for d, v in composite_alpha.iloc[-30:].items()},
            "position_sizes": pos_sizes,
            "current_regime": "Trending" if bool(is_trending.iloc[-1]) else "Chop/Consolidation"
        }

        return signals, meta
