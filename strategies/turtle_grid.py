import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple
from strategies.base_strategy import BaseStrategy
from core.indicators import calculate_donchian_channel, calculate_atr
from core.institutional_data import calculate_garman_klass_volatility, target_volatility_position_sizing

class TurtleGridStrategy(BaseStrategy):
    """
    机构级 CTA 趋势跟踪与波动率目标化模型 (Institutional CTA Trend & Vol-Targeting)
    - 多周期唐奇安通道突破体系 (Dual Donchian Channel: System 1: 20日, System 2: 55日)
    - 机构波动率目标化仓位 (Volatility Targeting: 动态恒定投资组合年化风险敞口)
    - ATR(N) 风险单元分配阶梯 (Unit Risk Sizing)
    - 动态棘轮追踪止损 (Trailing Ratchet Stop Loss)
    """
    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            "system_type": "s1",      # 's1' (20d entry, 10d exit) or 's2' (55d entry, 20d exit)
            "entry_period": 20,
            "exit_period": 10,
            "atr_period": 20,
            "stop_loss_n": 2.0,
            "target_vol_annual": 0.15, # 机构目标年化波动率 15%
            "max_leverage": 1.2        # 最大头寸杠杆上限
        }
        if params:
            default_params.update(params)
        super().__init__("Institutional CTA Vol-Targeting", default_params)

    def generate_signals(self, df: pd.DataFrame) -> Tuple[pd.Series, Dict[str, Any]]:
        high = df['High']
        low = df['Low']
        close = df['Close']
        open_p = df['Open']

        sys_type = self.params.get("system_type", "s1")
        if sys_type == "s2":
            entry_window = 55
            exit_window = 20
        else:
            entry_window = int(self.params.get("entry_period", 20))
            exit_window = int(self.params.get("exit_period", 10))

        atr_window = int(self.params.get("atr_period", 20))
        stop_n_mult = float(self.params.get("stop_loss_n", 2.0))
        target_vol = float(self.params.get("target_vol_annual", 0.15))
        max_lev = float(self.params.get("max_leverage", 1.2))

        # Donchian Channels
        entry_upper = high.rolling(window=entry_window).max().shift(1)
        exit_lower = low.rolling(window=exit_window).min().shift(1)

        # ATR & Garman-Klass Volatility
        atr_series = calculate_atr(high, low, close, atr_window)
        gk_vol = calculate_garman_klass_volatility(high, low, open_p, close, window=atr_window)

        # Volatility Targeting Sizing Weights
        target_weights = target_volatility_position_sizing(gk_vol, target_vol_annual=target_vol, max_leverage=max_lev)

        signals = pd.Series(0, index=df.index, dtype=int)
        
        in_position = False
        entry_price = 0.0
        stop_price = 0.0

        for i in range(len(df)):
            date = df.index[i]
            c_price = close.iloc[i]
            h_upper = entry_upper.iloc[i]
            l_exit = exit_lower.iloc[i]
            curr_atr = atr_series.iloc[i] if not pd.isna(atr_series.iloc[i]) else (c_price * 0.02)

            if not in_position:
                if not pd.isna(h_upper) and c_price > h_upper:
                    signals.iloc[i] = 1
                    in_position = True
                    entry_price = c_price
                    stop_price = entry_price - (curr_atr * stop_n_mult)
            else:
                if c_price < stop_price or (not pd.isna(l_exit) and c_price < l_exit):
                    signals.iloc[i] = -1
                    in_position = False
                    entry_price = 0.0
                    stop_price = 0.0
                else:
                    new_stop = c_price - (curr_atr * stop_n_mult)
                    if new_stop > stop_price:
                        stop_price = new_stop

        meta = {
            "system_type": "System 1 (20D/10D)" if sys_type == "s1" else "System 2 (55D/20D)",
            "entry_upper": entry_upper.round(2).to_dict(),
            "exit_lower": exit_lower.round(2).to_dict(),
            "target_vol_annual": f"{target_vol*100:.1f}%",
            "avg_realized_vol": f"{gk_vol.mean():.1f}%",
            "avg_target_leverage": round(float(target_weights.mean()), 2),
            "cta_rules": [
                f"机构入场：唐奇安通道前 {entry_window} 日突破即触发开仓",
                f"机构离场：跌破前 {exit_window} 日低点严格触发平仓止盈",
                f"波动率目标化：组合年化目标波动率锚定 {target_vol*100:.1f}%",
                f"动态棘轮防线：{stop_n_mult} × ATR(N) 移动保护锁定利润"
            ]
        }

        return signals, meta
