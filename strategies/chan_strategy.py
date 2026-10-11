import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, Optional
from strategies.base_strategy import BaseStrategy
from core.chan_theory import run_chan_analysis

class ChanTheoryStrategy(BaseStrategy):
    """
    缠中说禅三类买卖点与中枢动力学量化交易模型 (Chan Theory System)
    
    1. 形态学基础 (Morphology Layer):
       - 包含关系消除 (Merge Inclusions)
       - 严格顶分型与底分型提取 (Fractals)
       - 标准笔划分 (Standard Bis)
       - 三笔重叠确定走势中枢 [ZD, ZG] (ZhongShu Pivots)
    
    2. 动力学信号层 (Dynamics & Signals):
       - 第一类买点 (1B): 下跌趋势底背驰 (MACD 绿柱面积收缩 + 创前低底分型)
       - 第二类买点 (2B): 1B 之后第一波次级别反弹后的次回抽，不破 1B 最低点企稳
       - 第三类买点 (3B): 向上脱离中枢后，次回抽低点完全高于中枢上沿 ZG (主升浪起爆)
       - 对称的一二三类卖点 (1S, 2S, 3S) 作为严格止盈离场信号
    
    3. 动态风控与中枢防守 (Risk Management):
       - 初始止损位锚定买点所在底分型低点或最近中枢下沿 ZD
       - 遭遇 1S/2S/3S 立即止盈离场，杜绝主观贪婪
    """
    def __init__(self, params: Dict[str, Any] = None):
        default_params = {
            "use_1b": True,              # 启用第 1 类买点 (抄底背驰)
            "use_2b": True,              # 启用第 2 类买点 (二次确认)
            "use_3b": True,              # 启用第 3 类买点 (突破主升浪)
            "stop_loss_pct": 0.05,       # 兜底最大止损百分比 (5%)
            "take_profit_pct": 0.15,     # 目标止盈百分比 (15%)
            "trailing_stop_pct": 0.04    # 动态移动止盈回撤阈值 (4%)
        }
        if params:
            default_params.update(params)

        super().__init__("Chan Theory Quant System", default_params)

    def generate_signals(self, df: pd.DataFrame) -> Tuple[pd.Series, Dict[str, Any]]:
        n = len(df)
        if n < 20:
            return pd.Series(0, index=df.index), {"error": "Insufficient data for Chan Theory"}

        # 执行核心形态学与动力学分析
        chan_res = run_chan_analysis(df)
        tags = chan_res.get("tags", {})
        active_zs = chan_res.get("active_zhongshu")

        use_1b = bool(self.params.get("use_1b", True))
        use_2b = bool(self.params.get("use_2b", True))
        use_3b = bool(self.params.get("use_3b", True))
        max_sl_pct = float(self.params.get("stop_loss_pct", 0.05))
        max_tp_pct = float(self.params.get("take_profit_pct", 0.15))
        trailing_sl_pct = float(self.params.get("trailing_stop_pct", 0.04))

        # 整理买卖点日期索引映射
        buy_dates = set()
        if use_1b:
            for item in tags.get("1B", []):
                buy_dates.add(item["date"])
        if use_2b:
            for item in tags.get("2B", []):
                buy_dates.add(item["date"])
        if use_3b:
            for item in tags.get("3B", []):
                buy_dates.add(item["date"])

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
        stop_loss_price = 0.0

        for i in range(n):
            cur_date = dates[i]
            cur_close = float(close[i])
            cur_low = float(low[i])

            if position == 0:
                # 检查入场买点
                if cur_date in buy_dates:
                    position = 1
                    entry_price = cur_close
                    peak_price = cur_close
                    # 动态止损: 锚定中枢下沿或固定比例
                    if active_zs and cur_close > active_zs.zd:
                        stop_loss_price = max(active_zs.zd, cur_close * (1.0 - max_sl_pct))
                    else:
                        stop_loss_price = cur_close * (1.0 - max_sl_pct)

                    signals.iloc[i] = 1

            elif position == 1:
                peak_price = max(peak_price, cur_close)
                # 动态跟踪止盈
                trail_stop = peak_price * (1.0 - trailing_sl_pct)
                effective_stop = max(stop_loss_price, trail_stop)

                exit_triggered = False

                # 1. 遭遇缠论卖点 (1S/2S/3S)
                if cur_date in sell_dates:
                    exit_triggered = True

                # 2. 触及刚性或移动止损
                elif cur_low <= effective_stop:
                    exit_triggered = True

                # 3. 达到大级别止盈目标
                elif cur_close >= entry_price * (1.0 + max_tp_pct):
                    exit_triggered = True

                if exit_triggered:
                    position = 0
                    signals.iloc[i] = -1
                    entry_price = 0.0
                    peak_price = 0.0
                    stop_loss_price = 0.0

        info = {
            "strategy_type": "Chan Theory (缠中说禅形态动力学)",
            "merged_bars": chan_res.get("merged_bars_count", 0),
            "fractals": chan_res.get("fractals_count", 0),
            "bis": chan_res.get("bis_count", 0),
            "zhongshus": chan_res.get("zhongshus_count", 0),
            "tags_summary": {k: len(v) for k, v in tags.items()},
            "active_zhongshu": {
                "zg": active_zs.zg,
                "zd": active_zs.zd,
                "gg": active_zs.gg,
                "dd": active_zs.dd,
                "bi_count": active_zs.bi_count
            } if active_zs else None
        }

        return signals, info
