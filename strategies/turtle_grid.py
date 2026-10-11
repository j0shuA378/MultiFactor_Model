import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, Optional
from strategies.base_strategy import BaseStrategy
from core.indicators import calculate_donchian_channel, calculate_atr
from core.institutional_data import calculate_garman_klass_volatility, target_volatility_position_sizing

class TurtleGridStrategy(BaseStrategy):
    """
    经典海龟趋势跟踪与多层金字塔加仓模型 (Institutional Turtle Trend & CTA Pyramiding System)
    
    1. 经典双通道突破体系 (Dual Donchian Channel Systems):
       - 系统 1 (System 1): 20 日突破入场，10 日反向低点离场
       - 系统 2 (System 2): 55 日长周期突破入场，20 日反向低点离场
       - 严格排除当前未完成 K 线 (通过 shift(1) 锚定历史高低点，杜绝未来函数)
    2. 波动率 N (Wilder ATR) 头寸单位与风险预算:
       - 1 个交易单位 (Unit) 对应账户 1% 的风险暴露
    3. 金字塔分层加仓机制 (Pyramid Adding Rules):
       - 盈利顺势加仓：每顺向推进 0.5 × N 增加 1 个 Unit
       - 最大持仓上限限制为 4 个 Units (防范单一趋势过度集中)
    4. 刚性防线与分层止损管理 (Hierarchical Risk Controls):
       - 初始止损线：入场价 - 2.0 × N
       - 加仓同步抬升：每加仓 1 个 Unit，所有既有持仓止损线同步上移至 (最新加仓价 - 2.0 × N)
       - 动态棘轮跟踪止损 (Ratchet Trailing Stop): 锁定趋势大幅推进后的浮盈
       - 通道离场 (Channel Exit): 跌破 10日/20日 最低价无条件止盈离场
    5. 明确执行优先级 (Execution Precedence):
       - 止损保护 -> 通道离场 -> 顺势加仓 -> 突破初始建仓
    """
    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            "system_type": "s1",          # 's1' (20D/10D) 或 's2' (55D/20D)
            "entry_period": 20,
            "exit_period": 10,
            "atr_period": 20,
            "risk_pct_per_unit": 0.01,    # 单个 Unit 的风险预算 (1%)
            "stop_loss_n": 2.0,           # 止损距离 (2.0 * N)
            "pyramid_step_n": 0.5,        # 金字塔加仓间隔 (0.5 * N)
            "max_units": 4,               # 最大持仓层数 (4 个 Units)
            "target_vol_annual": 0.15,    # 组合目标年化波动率
            "max_leverage": 1.0           # 最大杠杆
        }
        if params:
            default_params.update(params)

        super().__init__("Institutional Turtle Trend System", default_params)

    def generate_signals(self, df: pd.DataFrame) -> Tuple[pd.Series, Dict[str, Any]]:
        n = len(df)
        if n < 30:
            return pd.Series(0, index=df.index), {"error": "Insufficient data"}

        high = df['High']
        low = df['Low']
        close = df['Close']
        open_p = df['Open']

        sys_type = str(self.params.get("system_type", "s1")).lower()
        if sys_type == "s2":
            entry_window = 55
            exit_window = 20
        else:
            entry_window = int(self.params.get("entry_period", 20))
            exit_window = int(self.params.get("exit_period", 10))

        atr_window = int(self.params.get("atr_period", 20))
        stop_n_mult = float(self.params.get("stop_loss_n", 2.0))
        pyramid_step_n = float(self.params.get("pyramid_step_n", 0.5))
        max_units = int(self.params.get("max_units", 4))
        target_vol = float(self.params.get("target_vol_annual", 0.15))
        max_lev = float(self.params.get("max_leverage", 1.0))

        # -------------------------------------------------------------
        # 1. 唐奇安通道 (严格 shift(1) 排除当前 bar)
        # -------------------------------------------------------------
        entry_upper, _, _ = calculate_donchian_channel(high, low, entry_window, shift_lag=True)
        _, exit_lower, _ = calculate_donchian_channel(high, low, exit_window, shift_lag=True)

        # 2. ATR (N) 波动率
        atr_n_series = calculate_atr(high, low, close, atr_window)
        gk_vol = calculate_garman_klass_volatility(high, low, open_p, close, window=atr_window)

        # -------------------------------------------------------------
        # 3. 海龟系统状态机与执行顺序 (Execution Order & State Machine)
        # -------------------------------------------------------------
        c_vals = close.values
        h_vals = high.values
        l_vals = low.values
        up_vals = entry_upper.values
        exit_vals = exit_lower.values
        atr_vals = atr_n_series.values

        sig_arr = np.zeros(n, dtype=np.int32)
        unit_arr = np.zeros(n, dtype=np.int32)
        pos_size_arr = np.zeros(n, dtype=np.float64)

        current_units = 0
        last_fill_price = 0.0
        stop_loss_price = 0.0
        highest_high_since_entry = 0.0

        for i in range(1, n):
            c_p = c_vals[i]
            h_p = h_vals[i]
            l_p = l_vals[i]
            up_p = up_vals[i]
            dn_p = exit_vals[i]
            curr_n = atr_vals[i] if not np.isnan(atr_vals[i]) else (c_p * 0.02)

            # --- 状态 A: 持仓状态检查 (优先级 1: 止损 -> 优先级 2: 通道离场 -> 优先级 3: 加仓) ---
            if current_units > 0:
                highest_high_since_entry = max(highest_high_since_entry, h_p)

                # 动态跟踪止损上移 (Ratchet)
                ratchet_stop = highest_high_since_entry - (stop_n_mult * curr_n)
                if ratchet_stop > stop_loss_price:
                    stop_loss_price = ratchet_stop

                # 优先级 1: 触发止损防线 (Low 跌破止损线)
                if l_p <= stop_loss_price or c_p <= stop_loss_price:
                    sig_arr[i] = -1
                    current_units = 0
                    last_fill_price = 0.0
                    stop_loss_price = 0.0
                    highest_high_since_entry = 0.0

                # 优先级 2: 触发通道离场 (Low 跌破前 exit_window 日最低价)
                elif not np.isnan(dn_p) and (l_p < dn_p or c_p < dn_p):
                    sig_arr[i] = -1
                    current_units = 0
                    last_fill_price = 0.0
                    stop_loss_price = 0.0
                    highest_high_since_entry = 0.0

                # 优先级 3: 顺势金字塔加仓 (顺向推进 0.5 * N)
                elif current_units < max_units and h_p >= (last_fill_price + pyramid_step_n * curr_n):
                    current_units += 1
                    last_fill_price = last_fill_price + pyramid_step_n * curr_n
                    # 所有持仓止损线统一抬升至最新加仓点 - 2N
                    stop_loss_price = last_fill_price - (stop_n_mult * curr_n)
                    sig_arr[i] = 1  # 加仓信号

            # --- 状态 B: 空仓状态检查 (优先级 4: 突破入场) ---
            else:
                if not np.isnan(up_p) and (h_p > up_p or c_p > up_p):
                    current_units = 1
                    last_fill_price = max(c_p, up_p)
                    stop_loss_price = last_fill_price - (stop_n_mult * curr_n)
                    highest_high_since_entry = h_p
                    sig_arr[i] = 1  # 初始建仓信号

            unit_arr[i] = current_units
            # 仓位比例: 根据当前持有的 Units 数量动态映射资金暴露
            pos_size_arr[i] = min(max_lev, current_units * 0.25)

        signals = pd.Series(sig_arr, index=df.index, dtype=int)
        position_sizes = pd.Series(pos_size_arr, index=df.index, dtype=float)

        meta = {
            "system_type": "System 1 (20D/10D)" if sys_type == "s1" else "System 2 (55D/20D)",
            "entry_upper": entry_upper.round(2).to_dict(),
            "exit_lower": exit_lower.round(2).to_dict(),
            "target_vol_annual": f"{target_vol*100:.1f}%",
            "avg_realized_vol": f"{gk_vol.mean():.1f}%",
            "max_units": max_units,
            "pyramid_step_n": f"{pyramid_step_n} × N",
            "stop_loss_n": f"{stop_n_mult} × N",
            "active_units_held": int(unit_arr[-1]),
            "cta_rules": [
                f"机构入场：唐奇安通道前 {entry_window} 日突破严格触发初始建仓 (排除当前bar)",
                f"金字塔加仓：每顺势推进 {pyramid_step_n}N 加仓 1 个 Unit，上限 {max_units} Units",
                f"分层止损同步：每次加仓所有头寸止损线同步上移至最新加仓价 - {stop_n_mult}N",
                f"机构离场：跌破前 {exit_window} 日低点严格触发平仓止盈"
            ],
            "position_sizes": position_sizes
        }

        return signals, meta
