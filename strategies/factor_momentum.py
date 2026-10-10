import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple
from strategies.base_strategy import BaseStrategy
from core.indicators import calculate_ema, calculate_sma, calculate_macd, calculate_rsi
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
    机构级多因子 Alpha 预测与动态配置模型 (Barra / AQR Style)
    - 12M-1M 经典截面/时序动量 (Jegadeesh & Titman, 剥离近1个月反转噪声)
    - 特质波动率风险调整动量 (Barroso & Santa-Clara, 规避动量崩溃)
    - 市场 Beta 中性化残差动量 (Blitz et al., 剥离大盘系统性风险)
    - 动量路径质量与连续性因子 (Da et al. Frog-in-the-Pan, R^2 * Slope 稳健爬升)
    - 价量协同与成交量验证 (Lee & Swaminathan, 机构资金放量确认)
    - MAD 极值截断与滚动时序标准化 (Rolling Z-Score Pipeline)
    - 动态波动率目标仓位管理 (Volatility-Targeted Sizing, AQR/全天候平抑回撤)
    - 机构级因子有效性诊断体系 (Rank IC, Factor IR, IC Decay, Quintile Spread)
    """
    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            "w_mom_12_1": 0.30,         # 12M-1M 动量权重
            "w_risk_adj": 0.25,         # 风险调整/低波缩放动量权重
            "w_residual": 0.20,         # Beta 中性化残差动量权重
            "w_trend_qual": 0.15,       # 趋势平滑与质量动量权重
            "w_vol_confirm": 0.10,      # 量价协同动量权重
            "fast_ma": 10,              # 快线 EMA 周期
            "slow_ma": 30,              # 慢线 EMA 周期
            "zscore_window": 30,        # 因子时序标准化窗口
            "alpha_threshold": 0.30,    # 开仓复合 Alpha 阈值
            "exit_threshold": -0.20,    # 平仓复合 Alpha 阈值
            "use_vol_targeting": True,  # 是否启用动态波动率目标仓位管理
            "target_vol_annual": 0.15,  # 目标年化波动率 (15%)
            "max_leverage": 1.0         # 最大持仓杠杆上限
        }
        if params:
            # Backward compatibility with legacy parameter names
            if "momentum_weight" in params and "w_mom_12_1" not in params:
                leg_m = float(params["momentum_weight"])
                params["w_mom_12_1"] = round(leg_m * 0.6, 2)
                params["w_trend_qual"] = round(leg_m * 0.4, 2)
            if "vol_penalty_weight" in params and "w_risk_adj" not in params:
                params["w_risk_adj"] = float(params["vol_penalty_weight"])
            if "reversion_weight" in params and "w_residual" not in params:
                params["w_residual"] = float(params["reversion_weight"])
            if "use_vol_target" in params and "use_vol_targeting" not in params:
                params["use_vol_targeting"] = bool(params["use_vol_target"])
            if "target_vol" in params and "target_vol_annual" not in params:
                tv = float(params["target_vol"])
                params["target_vol_annual"] = (tv / 100.0) if tv > 1.0 else tv
            if "z_win" in params and "zscore_window" not in params:
                params["zscore_window"] = int(params["z_win"])
            if "alpha_th" in params and "alpha_threshold" not in params:
                params["alpha_threshold"] = float(params["alpha_th"])
            if "exit_th" in params and "exit_threshold" not in params:
                params["exit_threshold"] = float(params["exit_th"])
            default_params.update(params)

        super().__init__("Multi-Factor Alpha Momentum", default_params)

    def generate_signals(self, df: pd.DataFrame) -> Tuple[pd.Series, Dict[str, Any]]:
        close = df['Close']
        high = df['High']
        low = df['Low']
        open_p = df['Open']
        volume = df['Volume'] if 'Volume' in df.columns else pd.Series(1.0, index=df.index)

        fast_period = int(self.params.get("fast_ma", 10))
        slow_period = int(self.params.get("slow_ma", 30))
        z_win = int(self.params.get("zscore_window", 30))

        w_12_1 = float(self.params.get("w_mom_12_1", 0.30))
        w_risk = float(self.params.get("w_risk_adj", 0.25))
        w_res = float(self.params.get("w_residual", 0.20))
        w_qual = float(self.params.get("w_trend_qual", 0.15))
        w_vol = float(self.params.get("w_vol_confirm", 0.10))

        alpha_th = float(self.params.get("alpha_threshold", 0.30))
        exit_th = float(self.params.get("exit_threshold", -0.20))
        use_vol_target = bool(self.params.get("use_vol_targeting", True))
        target_vol = float(self.params.get("target_vol_annual", 0.15))
        max_lev = float(self.params.get("max_leverage", 1.0))

        # Normalize factor weights
        sum_w = w_12_1 + w_risk + w_res + w_qual + w_vol
        if sum_w > 0:
            w_12_1 /= sum_w
            w_risk /= sum_w
            w_res /= sum_w
            w_qual /= sum_w
            w_vol /= sum_w

        # 1. 12M-1M 经典中长周期动量 (Jegadeesh & Titman, Novy-Marx)
        raw_m12_1 = calculate_12_1_momentum(close)
        z_m12_1 = standardize_factor(raw_m12_1, window=z_win)

        # 2. 特质/日内高频波动率风险调整动量 (Barroso & Santa-Clara)
        raw_risk_adj = calculate_risk_adjusted_momentum(close, high, low, open_p, window=63, vol_window=20)
        z_risk_adj = standardize_factor(raw_risk_adj, window=z_win)

        # 3. 剥离大盘系统性风险的 Beta 中性化残差动量 (Blitz et al.)
        raw_residual = calculate_residual_momentum(close, window=60, mom_window=20)
        z_residual = standardize_factor(raw_residual, window=z_win)

        # 4. 动量路径平滑度与趋势质量因子 (Da et al. Frog-in-the-Pan, R^2 * Slope)
        raw_trend_qual = calculate_trend_quality_momentum(close, window=40)
        z_trend_qual = standardize_factor(raw_trend_qual, window=z_win)

        # 5. 价量协同与成交量确认动量 (Lee & Swaminathan)
        raw_vol_confirm = calculate_volume_confirmed_momentum(close, volume, window=20)
        z_vol_confirm = standardize_factor(raw_vol_confirm, window=z_win)

        # 6. 机构复合 Alpha 评分 (Composite Momentum Alpha Score)
        composite_alpha_raw = (
            w_12_1 * z_m12_1 +
            w_risk * z_risk_adj +
            w_res * z_residual +
            w_qual * z_trend_qual +
            w_vol * z_vol_confirm
        )
        composite_alpha = standardize_factor(composite_alpha_raw, window=z_win)

        # 7. 辅助均线趋势验证
        fast_ema = calculate_ema(close, fast_period)
        slow_ema = calculate_ema(close, slow_period)

        # 8. 信号生成: Alpha 触发 + 趋势过滤
        signals = pd.Series(0, index=df.index, dtype=int)
        buy_condition = (composite_alpha > alpha_th) & (fast_ema >= slow_ema * 0.995)
        sell_condition = (composite_alpha < exit_th) | (fast_ema < slow_ema * 0.985)
        signals[buy_condition] = 1
        signals[sell_condition] = -1

        # 9. 动态波动率目标仓位管理 (Volatility-Targeted Sizing)
        gk_vol = calculate_garman_klass_volatility(high, low, open_p, close, window=20)
        if use_vol_target:
            pos_sizes = target_volatility_position_sizing(gk_vol, target_vol_annual=target_vol, max_leverage=max_lev)
        else:
            pos_sizes = pd.Series(1.0, index=df.index)

        # 10. 因子有效性前瞻检验 (Forward 5-Day Return & IC Analytics)
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

        # Individual sub-factor IC evaluation
        sub_factor_ics = {
            "12M-1M Momentum": calculate_information_coefficient(z_m12_1, forward_5d_ret),
            "Risk-Adjusted Vol": calculate_information_coefficient(z_risk_adj, forward_5d_ret),
            "Residual Alpha": calculate_information_coefficient(z_residual, forward_5d_ret),
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
                "12M-1M Momentum": round(w_12_1, 2),
                "Risk-Adjusted Vol Sizing": round(w_risk, 2),
                "Residual Alpha (Beta-Neutral)": round(w_res, 2),
                "Trend Quality (Frog-in-the-Pan)": round(w_qual, 2),
                "Volume-Confirmed Momentum": round(w_vol, 2)
            },
            "sub_factor_ics": sub_factor_ics,
            "recent_rolling_ic": recent_ic_list,
            "fast_ema": fast_ema.round(2).to_dict(),
            "slow_ema": slow_ema.round(2).to_dict(),
            "composite_alpha_recent": {str(d): round(float(v), 3) for d, v in composite_alpha.iloc[-30:].items()},
            "position_sizes": pos_sizes
        }

        return signals, meta
