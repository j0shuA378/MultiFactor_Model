"""
strategies/chan_strategy.py: 缠中说禅公理化三类买卖点与现代风险预算量化模型
基于 2026 年金融工程专著《缠论的数学结构与量化交易》：
1. 三类买卖点完备触发 (1B 趋势背驰抄底, 2B 右侧企稳确认, 3B 中枢突破主升)
2. 结构性防守止损线 (1B/2B 守 Low(1B), 3B 守 ZG)
3. 现代固定比例风险预算 (Fixed Fractional Risk Budgeting, 单笔最大承受 2% 净值亏损)
4. 三级动态出场防御纪律 (结构硬止损 + 反向卖点强制平仓 + 移动跟踪止盈)
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, Optional, List
from strategies.base_strategy import BaseStrategy
from core.chan_theory import run_chan_analysis, calculate_risk_budget_position


class ChanTheoryStrategy(BaseStrategy):
    """
    缠中说禅公理化三类买卖点与动态风险预算交易模型 (Chan Theory System)
    """

    def __init__(self, params: Optional[Dict[str, Any]] = None) -> None:
        default_params = {
            "use_1b": True,                 # 启用第 1 类买点 (趋势/盘整底背驰极值)
            "use_2b": True,                 # 启用第 2 类买点 (右侧回踩不破底企稳)
            "use_3b": True,                 # 启用第 3 类买点 (中枢突破回抽不破ZG主升浪)
            "risk_per_trade": 0.02,         # 现代风险预算: 单笔最大容忍亏损比例 (2%)
            "max_position_ratio": 0.30,     # 单一标的最大资金占用上限 (30%)
            "use_structural_stop": True,    # 启用结构性防守硬止损 (1B/2B守底, 3B守ZG)
            "use_trailing_stop": True,      # 启用移动跟踪止盈
            "trailing_stop_pct": 0.04,      # 动态移动止盈跟踪回撤阈值 (4%)
            "lot_size": 100                 # 最小整手交易单位
        }
        if params:
            default_params.update(params)

        super().__init__("Chan Theory Quant System", default_params)

    def generate_signals(self, df: pd.DataFrame) -> Tuple[pd.Series, Dict[str, Any]]:
        n = len(df)
        if n < 20:
            return pd.Series(0, index=df.index), {"error": "Insufficient data for Chan Theory"}

        # 1. 运行核心几何形态学与动力学全景分析
        chan_res = run_chan_analysis(df)
        tags = chan_res.get("tags", {})
        active_zs = chan_res.get("active_zhongshu")

        use_1b = bool(self.params.get("use_1b", True))
        use_2b = bool(self.params.get("use_2b", True))
        use_3b = bool(self.params.get("use_3b", True))
        use_structural = bool(self.params.get("use_structural_stop", True))
        use_trailing = bool(self.params.get("use_trailing_stop", True))
        trailing_pct = float(self.params.get("trailing_stop_pct", 0.04))
        risk_per_trade = float(self.params.get("risk_per_trade", 0.02))
        max_pos_ratio = float(self.params.get("max_position_ratio", 0.30))
        lot_size = int(self.params.get("lot_size", 100))

        # 2. 建立买入信号与结构止损映射表
        buy_signals_map: Dict[str, Dict[str, Any]] = {}
        if use_1b:
            for item in tags.get("1B", []):
                buy_signals_map[item["date"]] = item
        if use_2b:
            for item in tags.get("2B", []):
                buy_signals_map[item["date"]] = item
        if use_3b:
            for item in tags.get("3B", []):
                buy_signals_map[item["date"]] = item

        sell_dates = set()
        for item in tags.get("1S", []) + tags.get("2S", []) + tags.get("3S", []):
            sell_dates.add(item["date"])

        signals = pd.Series(0, index=df.index, dtype=int)
        close = df["Close"].values
        low = df["Low"].values
        dates = df.index.astype(str).tolist()

        position = 0
        entry_price = 0.0
        peak_price = 0.0
        structural_stop_price = 0.0
        active_signal_tag: Optional[Dict[str, Any]] = None

        trade_logs: List[Dict[str, Any]] = []

        # 3. 因果时序事件模拟与三级出场防线执行
        for i in range(n):
            cur_date = dates[i]
            cur_close = float(close[i])
            cur_low = float(low[i])

            if position == 0:
                # 检查入场触发
                if cur_date in buy_signals_map:
                    position = 1
                    entry_price = cur_close
                    peak_price = cur_close
                    active_signal_tag = buy_signals_map[cur_date]

                    # 提取结构性防守止损线
                    if use_structural and "stop_loss" in active_signal_tag:
                        structural_stop_price = float(active_signal_tag["stop_loss"])
                    else:
                        structural_stop_price = cur_close * 0.95

                    # 计算风险预算建议仓位 (假设标准 100,000 本金)
                    size_res = calculate_risk_budget_position(
                        account_equity=100000.0,
                        entry_price=entry_price,
                        stop_loss_price=structural_stop_price,
                        risk_per_trade=risk_per_trade,
                        max_position_ratio=max_pos_ratio,
                        lot_size=lot_size
                    )

                    signals.iloc[i] = 1
                    trade_logs.append({
                        "action": "BUY",
                        "date": cur_date,
                        "price": entry_price,
                        "type": active_signal_tag["type"],
                        "stop_loss": structural_stop_price,
                        "shares": size_res.shares,
                        "position_ratio": round(size_res.position_ratio, 3),
                        "desc": active_signal_tag.get("desc", "")
                    })

            elif position == 1:
                peak_price = max(peak_price, cur_close)
                exit_triggered = False
                exit_reason = ""

                # 防线 1: 结构性硬止损 (价格跌破形态极值防守线，市价单立即离场)
                if use_structural and cur_low <= structural_stop_price:
                    exit_triggered = True
                    exit_reason = f"触发结构性硬止损 (${cur_low:.2f} <= 防守线 ${structural_stop_price:.2f})"

                # 防线 2: 遭遇反向形态卖点 (1S 顶背驰 / 2S 受阻 / 3S 破位)
                elif cur_date in sell_dates:
                    exit_triggered = True
                    exit_reason = "触发缠论反向卖点信号形态离场"

                # 防线 3: 移动跟踪止盈 (利润回撤锁定)
                elif use_trailing:
                    trail_stop = peak_price * (1.0 - trailing_pct)
                    if cur_close > entry_price * 1.05 and cur_low <= trail_stop:
                        exit_triggered = True
                        exit_reason = f"触发移动跟踪止盈 (${cur_low:.2f} <= 跟踪线 ${trail_stop:.2f})"

                if exit_triggered:
                    position = 0
                    signals.iloc[i] = -1
                    trade_logs.append({
                        "action": "SELL",
                        "date": cur_date,
                        "price": cur_close,
                        "return_pct": round((cur_close - entry_price) / max(1e-4, entry_price) * 100, 2),
                        "reason": exit_reason
                    })
                    entry_price = 0.0
                    peak_price = 0.0
                    structural_stop_price = 0.0
                    active_signal_tag = None

        info = {
            "strategy_type": "Chan Theory (缠论拓扑中枢与现代风险预算)",
            "merged_bars": chan_res.get("merged_bars_count", 0),
            "fractals": chan_res.get("fractals_count", 0),
            "bis": chan_res.get("bis_count", 0),
            "zhongshus": chan_res.get("zhongshus_count", 0),
            "tags_summary": {k: len(v) for k, v in tags.items()},
            "tags": tags,
            "trade_logs": trade_logs,
            "risk_budget_profile": {
                "risk_per_trade": risk_per_trade,
                "max_position_ratio": max_pos_ratio,
                "use_structural_stop": use_structural,
                "use_trailing_stop": use_trailing
            },
            "active_zhongshu": {
                "zg": active_zs.zg,
                "zd": active_zs.zd,
                "gg": active_zs.gg,
                "dd": active_zs.dd,
                "bi_count": active_zs.bi_count
            } if active_zs else None
        }

        return signals, info
