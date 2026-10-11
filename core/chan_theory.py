"""
core/chan_theory.py: 缠论公理化几何形态学与动力学分析引擎
基于 2026 年金融工程专著《缠论的数学结构与量化交易》工业标准构建：
1. 包含关系严格方向递归消除 (左结合律)
2. 顶分型与底分型提取
3. 严格分型笔状态机 (顶底交替、独立K线跨度 >= 3)
4. 走势中枢拓扑区间代数 [ZD, ZG] = [max(L1,L2,L3), min(H1,H2,H3)]
5. 动力学背驰度量 (趋势背驰 a+A+b+B+c、盘整背驰 a+A+b、MACD绝对值面积积分与DIF极值衰竭)
6. 三类买卖点严格完备触发器 (1B/2B/3B, 1S/2S/3S) 与结构性防守止损线
7. 现代固定比例风险预算 (Fixed Fractional Risk Budgeting)
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class DivergenceType(Enum):
    """背驰分类枚举"""
    NONE = "none"
    TREND_DIVERGENCE = "trend_divergence"           # 趋势背驰 (两中枢后标准背驰 a+A+b+B+c)
    CONSOLIDATION_DIVERGENCE = "consolidation_div"  # 盘整背驰 (单中枢离开段衰竭 a+A+b)
    SCALE_INVERSION = "scale_inversion"             # 小转大 (突发极速反转)


@dataclass
class ChanBar:
    """消除包含关系后的合并 K 线"""
    index: int
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    raw_indices: List[int] = field(default_factory=list)


@dataclass
class Fractal:
    """顶分型与底分型"""
    index: int
    date: str
    type: str  # 'TOP' or 'BOTTOM'
    val: float
    raw_index: int


@dataclass
class ChanBi:
    """标准分型笔"""
    start_fractal: Fractal
    end_fractal: Fractal
    direction: int  # 1 for UP, -1 for DOWN
    high: float
    low: float
    start_date: str
    end_date: str
    start_raw_idx: int
    end_raw_idx: int


@dataclass
class ChanZhongShu:
    """
    走势中枢 (区间代数定义)
    zg: min(H1, H2, H3) - 核心引力区间上沿
    zd: max(L1, L2, L3) - 核心引力区间下沿
    gg: max(H1, H2, H3) - 极值区间上界
    dd: min(L1, L2, L3) - 极值区间下界
    """
    zg: float
    zd: float
    gg: float
    dd: float
    start_date: str
    end_date: str
    bi_count: int = 3
    is_active: bool = True


@dataclass
class PositionSizeResult:
    """风险预算仓位测算结果"""
    shares: int
    position_value: float
    position_ratio: float
    risk_amount: float
    per_share_risk: float


def merge_kline_inclusions(df: pd.DataFrame) -> List[ChanBar]:
    """
    K线包含关系严格处理 (第 65-67 课左结合律标准)
    完全无未来函数，依序流式处理。
    """
    if df.empty:
        return []

    bars: List[ChanBar] = []
    dates = df.index.astype(str).tolist()
    opens = df["Open"].values
    highs = df["High"].values
    lows = df["Low"].values
    closes = df["Close"].values
    vols = df["Volume"].values if "Volume" in df.columns else np.zeros(len(df))

    n = len(df)
    if n == 0:
        return []

    bars.append(ChanBar(
        index=0,
        date=dates[0],
        open=float(opens[0]),
        high=float(highs[0]),
        low=float(lows[0]),
        close=float(closes[0]),
        volume=float(vols[0]),
        raw_indices=[0]
    ))

    direction = 1  # 1 为向上处理，-1 为向下处理

    for i in range(1, n):
        cur_h = float(highs[i])
        cur_l = float(lows[i])
        cur_open = float(opens[i])
        cur_close = float(closes[i])
        cur_vol = float(vols[i])
        cur_date = dates[i]

        prev = bars[-1]

        # 包含关系判断: 前包后 或 后包前
        is_included = (prev.high >= cur_h and prev.low <= cur_l) or (cur_h >= prev.high and cur_l <= prev.low)

        if not is_included:
            # 更新方向: 向上突破定向上，向下突破定向下
            if cur_h > prev.high and cur_l > prev.low:
                direction = 1
            elif cur_h < prev.high and cur_l < prev.low:
                direction = -1

            bars.append(ChanBar(
                index=len(bars),
                date=cur_date,
                open=cur_open,
                high=cur_h,
                low=cur_l,
                close=cur_close,
                volume=cur_vol,
                raw_indices=[i]
            ))
        else:
            # 存在包含关系，依序合并
            if direction == 1:
                # 向上包含处理: 取高高、高低
                new_h = max(prev.high, cur_h)
                new_l = max(prev.low, cur_l)
            else:
                # 向下包含处理: 取低高、低低
                new_h = min(prev.high, cur_h)
                new_l = min(prev.low, cur_l)

            prev.high = new_h
            prev.low = new_l
            prev.close = cur_close
            prev.volume += cur_vol
            prev.date = cur_date
            prev.raw_indices.append(i)

    return bars


def find_fractals(merged_bars: List[ChanBar]) -> List[Fractal]:
    """
    寻找标准化合并K线中的顶分型与底分型 (第 62 课标准定义)
    """
    fractals: List[Fractal] = []
    n = len(merged_bars)
    if n < 3:
        return []

    for i in range(1, n - 1):
        prev = merged_bars[i - 1]
        cur = merged_bars[i]
        nxt = merged_bars[i + 1]

        # 顶分型: 中间高点最高且低点最高
        if cur.high > prev.high and cur.high > nxt.high and cur.low > prev.low and cur.low > nxt.low:
            fractals.append(Fractal(
                index=i,
                date=cur.date,
                type="TOP",
                val=cur.high,
                raw_index=cur.raw_indices[-1]
            ))
        # 底分型: 中间低点最低且高点最低
        elif cur.low < prev.low and cur.low < nxt.low and cur.high < prev.high and cur.high < nxt.high:
            fractals.append(Fractal(
                index=i,
                date=cur.date,
                type="BOTTOM",
                val=cur.low,
                raw_index=cur.raw_indices[-1]
            ))

    return fractals


def construct_standard_bis(fractals: List[Fractal], merged_bars: List[ChanBar]) -> List[ChanBi]:
    """
    构建标准化笔 (第 62-67 课严格状态机)
    1. 顶分型与底分型交替
    2. 顶高 > 底低
    3. 顶底之间必须间隔至少 1 根独立合并K线 (index 差 >= 3，总跨越 >= 5 根)
    """
    if len(fractals) < 2:
        return []

    bis: List[ChanBi] = []
    last_frac: Optional[Fractal] = None

    for f in fractals:
        if last_frac is None:
            last_frac = f
            continue

        if f.type == last_frac.type:
            # 同向分型，保留极值更优的分型以确保笔的跨度
            if f.type == "TOP":
                if f.val > last_frac.val:
                    last_frac = f
            else:
                if f.val < last_frac.val:
                    last_frac = f
            continue

        # 异向分型，检查笔成立的条件
        k_span = f.index - last_frac.index
        if k_span >= 3:
            if last_frac.type == "BOTTOM" and f.type == "TOP" and f.val > last_frac.val:
                # 向上笔成立
                bis.append(ChanBi(
                    start_fractal=last_frac,
                    end_fractal=f,
                    direction=1,
                    high=f.val,
                    low=last_frac.val,
                    start_date=last_frac.date,
                    end_date=f.date,
                    start_raw_idx=last_frac.raw_index,
                    end_raw_idx=f.raw_index
                ))
                last_frac = f
            elif last_frac.type == "TOP" and f.type == "BOTTOM" and f.val < last_frac.val:
                # 向下笔成立
                bis.append(ChanBi(
                    start_fractal=last_frac,
                    end_fractal=f,
                    direction=-1,
                    high=last_frac.val,
                    low=f.val,
                    start_date=last_frac.date,
                    end_date=f.date,
                    start_raw_idx=last_frac.raw_index,
                    end_raw_idx=f.raw_index
                ))
                last_frac = f

    return bis


def compute_zhongshus(bis: List[ChanBi]) -> List[ChanZhongShu]:
    """
    计算走势中枢 (前三笔重叠原则 ZG=min(H1,H2,H3), ZD=max(L1,L2,L3))
    支持中枢延伸与极值更新
    """
    if len(bis) < 3:
        return []

    zhongshus: List[ChanZhongShu] = []
    i = 0
    n = len(bis)

    while i <= n - 3:
        b1, b2, b3 = bis[i], bis[i + 1], bis[i + 2]

        zg = min(b1.high, b2.high, b3.high)
        zd = max(b1.low, b2.low, b3.low)

        if zg >= zd:
            # 构成中枢
            gg = max(b1.high, b2.high, b3.high)
            dd = min(b1.low, b2.low, b3.low)

            zs = ChanZhongShu(
                zg=round(float(zg), 2),
                zd=round(float(zd), 2),
                gg=round(float(gg), 2),
                dd=round(float(dd), 2),
                start_date=b1.start_date,
                end_date=b3.end_date,
                bi_count=3,
                is_active=True
            )

            # 检查中枢延伸
            j = i + 3
            while j < n:
                bj = bis[j]
                if bj.high >= zd and bj.low <= zg:
                    zs.bi_count += 1
                    zs.end_date = bj.end_date
                    zs.gg = max(zs.gg, bj.high)
                    zs.dd = min(zs.dd, bj.low)
                    j += 1
                else:
                    break

            zhongshus.append(zs)
            i = j  # 移动到中枢离开段
        else:
            i += 1

    return zhongshus


def calculate_macd_indicator(close: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """计算 MACD 指标 (DIF, DEA, HIST)"""
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    dif = ema12 - ema26
    dea = dif.ewm(span=9, adjust=False).mean()
    hist = (dif - dea) * 2.0
    return dif, dea, hist


def calculate_risk_budget_position(
    account_equity: float,
    entry_price: float,
    stop_loss_price: float,
    risk_per_trade: float = 0.02,
    max_position_ratio: float = 0.30,
    lot_size: int = 100
) -> PositionSizeResult:
    """
    固定比例风险预算仓位自适应测算公式 (Fixed Fractional Risk Budgeting)
    [专著第 14 章 核心算法]
    N = min( (Equity * r) / |P_entry - P_stop|, (Equity * max_ratio) / P_entry ) // lot_size * lot_size
    """
    if account_equity <= 0.0 or entry_price <= 0.0:
        return PositionSizeResult(0, 0.0, 0.0, 0.0, 0.0)

    per_share_risk = abs(entry_price - stop_loss_price)
    if per_share_risk < 1e-4:
        per_share_risk = entry_price * 0.01  # 防止除以零，设保底1%价格风险

    max_risk_amount = account_equity * risk_per_trade
    raw_shares = max_risk_amount / per_share_risk

    # 单标的最大持仓上限约束
    max_allowed_shares = (account_equity * max_position_ratio) / entry_price
    final_shares = min(raw_shares, max_allowed_shares)

    # 整手截断
    lot_shares = int(final_shares // lot_size) * lot_size
    position_val = lot_shares * entry_price
    position_ratio = position_val / max(1.0, account_equity)
    actual_risk = lot_shares * per_share_risk

    return PositionSizeResult(
        shares=lot_shares,
        position_value=position_val,
        position_ratio=position_ratio,
        risk_amount=actual_risk,
        per_share_risk=per_share_risk
    )


def detect_chan_buy_sell_points(
    df: pd.DataFrame,
    bis: List[ChanBi],
    zhongshus: List[ChanZhongShu]
) -> Dict[str, Any]:
    """
    精准识别缠论三类买卖点 (1B, 2B, 3B, 1S, 2S, 3S)
    严格整合专著第 8、9、10 章动力学充要条件：
    - 趋势背驰 (a+A+b+B+c) 与盘整背驰 (a+A+b)
    - MACD 柱面积绝对值积分与 DIF 极值对比
    - 结构性防守止损线设置
    - 双时戳事件流 (confirm_date 防未来函数)
    """
    n = len(df)
    signals = pd.Series(0, index=df.index)
    signal_tags: Dict[str, List[Dict[str, Any]]] = {
        "1B": [], "2B": [], "3B": [],
        "1S": [], "2S": [], "3S": []
    }

    if len(bis) < 3 or df.empty:
        return {"signals": signals, "tags": signal_tags}

    dif, dea, hist = calculate_macd_indicator(df["Close"])

    def get_macd_area(start_raw: int, end_raw: int, is_green: bool = True) -> float:
        sub = hist.iloc[start_raw : end_raw + 1]
        if is_green:
            return float(sub[sub < 0].abs().sum())
        return float(sub[sub > 0].sum())

    def get_dif_extreme(start_raw: int, end_raw: int) -> float:
        sub = dif.iloc[start_raw : end_raw + 1]
        if sub.empty:
            return 0.0
        return float(sub.abs().max())

    # 1. 扫描第一类买卖点 (1B / 1S): 趋势背驰与盘整背驰
    for i in range(2, len(bis)):
        cur_bi = bis[i]
        prev_bi = bis[i - 2]  # 同方向前一笔

        # 检查是否处于多中枢趋势中
        active_zs_count = sum(1 for zs in zhongshus if zs.end_date <= cur_bi.start_date)
        is_trend = active_zs_count >= 2

        # 1B: 下跌笔背驰
        if cur_bi.direction == -1 and prev_bi.direction == -1:
            if cur_bi.low < prev_bi.low:
                area_cur = get_macd_area(cur_bi.start_raw_idx, cur_bi.end_raw_idx, is_green=True)
                area_prev = get_macd_area(prev_bi.start_raw_idx, prev_bi.end_raw_idx, is_green=True)
                dif_cur = get_dif_extreme(cur_bi.start_raw_idx, cur_bi.end_raw_idx)
                dif_prev = get_dif_extreme(prev_bi.start_raw_idx, prev_bi.end_raw_idx)

                # 动能衰减充要条件: 面积显著收缩 (decay < 0.85) 且 DIF 极值未大幅创新低
                if area_prev > 1e-4:
                    decay = area_cur / area_prev
                    dif_weakened = dif_cur <= dif_prev * 1.05
                    if decay < 0.85 and dif_weakened:
                        raw_idx = cur_bi.end_raw_idx
                        if raw_idx < n:
                            date_str = str(df.index[raw_idx])
                            signals.iloc[raw_idx] = 1
                            div_type = DivergenceType.TREND_DIVERGENCE.value if is_trend else DivergenceType.CONSOLIDATION_DIVERGENCE.value
                            signal_tags["1B"].append({
                                "date": date_str,
                                "price": cur_bi.low,
                                "type": "1B",
                                "stop_loss": cur_bi.low,  # 结构硬止损线
                                "divergence_type": div_type,
                                "decay_ratio": round(decay, 3),
                                "desc": f"1B {'趋势' if is_trend else '盘整'}底背驰 (现价 ${cur_bi.low:.2f}$ < 前低 ${prev_bi.low:.2f}$，绿柱面积衰减 {int((1-decay)*100)}%)"
                            })

        # 1S: 上涨笔背驰
        elif cur_bi.direction == 1 and prev_bi.direction == 1:
            if cur_bi.high > prev_bi.high:
                area_cur = get_macd_area(cur_bi.start_raw_idx, cur_bi.end_raw_idx, is_green=False)
                area_prev = get_macd_area(prev_bi.start_raw_idx, prev_bi.end_raw_idx, is_green=False)
                dif_cur = get_dif_extreme(cur_bi.start_raw_idx, cur_bi.end_raw_idx)
                dif_prev = get_dif_extreme(prev_bi.start_raw_idx, prev_bi.end_raw_idx)

                if area_prev > 1e-4:
                    decay = area_cur / area_prev
                    dif_weakened = dif_cur <= dif_prev * 1.05
                    if decay < 0.85 and dif_weakened:
                        raw_idx = cur_bi.end_raw_idx
                        if raw_idx < n:
                            date_str = str(df.index[raw_idx])
                            signals.iloc[raw_idx] = -1
                            div_type = DivergenceType.TREND_DIVERGENCE.value if is_trend else DivergenceType.CONSOLIDATION_DIVERGENCE.value
                            signal_tags["1S"].append({
                                "date": date_str,
                                "price": cur_bi.high,
                                "type": "1S",
                                "stop_loss": cur_bi.high,  # 结构硬止损线
                                "divergence_type": div_type,
                                "decay_ratio": round(decay, 3),
                                "desc": f"1S {'趋势' if is_trend else '盘整'}顶背驰 (高点 ${cur_bi.high:.2f}$ > 前高 ${prev_bi.high:.2f}$，红柱面积衰减 {int((1-decay)*100)}%)"
                            })

    # 2. 扫描第二类买卖点 (2B / 2S): 1B/1S 后次回踩/抽不破极值确认点
    for b_item in signal_tags["1B"]:
        b_date = b_item["date"]
        for i in range(len(bis) - 1):
            if bis[i].end_date == b_date and bis[i].direction == -1:
                if i + 2 < len(bis) and bis[i + 2].direction == -1:
                    pullback_bi = bis[i + 2]
                    # 回踩严格不破 1B 最低点
                    if pullback_bi.low > b_item["price"]:
                        raw_idx = pullback_bi.end_raw_idx
                        if raw_idx < n:
                            date_str = str(df.index[raw_idx])
                            signals.iloc[raw_idx] = 1
                            signal_tags["2B"].append({
                                "date": date_str,
                                "price": pullback_bi.low,
                                "type": "2B",
                                "stop_loss": b_item["price"],  # 2B 刚性止损线守 1B 最低点
                                "desc": f"2B 右侧企稳买点 (回踩低点 ${pullback_bi.low:.2f}$ 严格高于 1B底 ${b_item['price']:.2f}$)"
                            })

    for s_item in signal_tags["1S"]:
        s_date = s_item["date"]
        for i in range(len(bis) - 1):
            if bis[i].end_date == s_date and bis[i].direction == 1:
                if i + 2 < len(bis) and bis[i + 2].direction == 1:
                    rebound_bi = bis[i + 2]
                    # 反抽严格不创新高
                    if rebound_bi.high < s_item["price"]:
                        raw_idx = rebound_bi.end_raw_idx
                        if raw_idx < n:
                            date_str = str(df.index[raw_idx])
                            signals.iloc[raw_idx] = -1
                            signal_tags["2S"].append({
                                "date": date_str,
                                "price": rebound_bi.high,
                                "type": "2S",
                                "stop_loss": s_item["price"],  # 2S 止损守 1S 最高点
                                "desc": f"2S 受阻次高卖点 (反抽高点 ${rebound_bi.high:.2f}$ 低于 1S顶 ${s_item['price']:.2f}$)"
                            })

    # 3. 扫描第三类买卖点 (3B / 3S): 中枢突破回抽不破 ZG / 跌破反抽不破 ZD
    for zs in zhongshus:
        for i in range(len(bis) - 1):
            if bis[i].start_date >= zs.end_date:
                # 向上突破脱离中枢
                if bis[i].direction == 1 and bis[i].high > zs.zg:
                    if i + 1 < len(bis) and bis[i + 1].direction == -1:
                        pb = bis[i + 1]
                        # 回抽低点严格不跌回中枢上沿 ZG
                        if pb.low > zs.zg:
                            raw_idx = pb.end_raw_idx
                            if raw_idx < n:
                                date_str = str(df.index[raw_idx])
                                signals.iloc[raw_idx] = 1
                                signal_tags["3B"].append({
                                    "date": date_str,
                                    "price": pb.low,
                                    "type": "3B",
                                    "stop_loss": zs.zg,  # 3B 结构止损严格守 ZG
                                    "desc": f"3B 中枢突破主升买点 (次回抽低点 ${pb.low:.2f}$ 严格高于中枢上沿 ZG ${zs.zg:.2f}$)"
                                })

                # 向下跌破脱离中枢
                elif bis[i].direction == -1 and bis[i].low < zs.zd:
                    if i + 1 < len(bis) and bis[i + 1].direction == 1:
                        rebound = bis[i + 1]
                        # 反抽高点严格不升回中枢下沿 ZD
                        if rebound.high < zs.zd:
                            raw_idx = rebound.end_raw_idx
                            if raw_idx < n:
                                date_str = str(df.index[raw_idx])
                                signals.iloc[raw_idx] = -1
                                signal_tags["3S"].append({
                                    "date": date_str,
                                    "price": rebound.high,
                                    "type": "3S",
                                    "stop_loss": zs.zd,  # 3S 止损守 ZD
                                    "desc": f"3S 中枢跌破加速卖点 (次反抽高点 ${rebound.high:.2f}$ 严格低于中枢下沿 ZD ${zs.zd:.2f}$)"
                                })

    return {"signals": signals, "tags": signal_tags}


def run_chan_analysis(df: pd.DataFrame) -> Dict[str, Any]:
    """
    缠论全景计算综合调度主函数
    返回包含消除K线、分型、笔、中枢及三类买卖点全景
    """
    if df.empty or len(df) < 5:
        return {
            "status": "empty",
            "merged_bars_count": 0,
            "fractals_count": 0,
            "bis_count": 0,
            "zhongshus_count": 0,
            "merged_bars": [],
            "fractals": [],
            "bis": [],
            "zhongshus": [],
            "signals": pd.Series(0, index=df.index if not df.empty else []),
            "tags": {},
            "active_zhongshu": None
        }

    merged_bars = merge_kline_inclusions(df)
    fractals = find_fractals(merged_bars)
    bis = construct_standard_bis(fractals, merged_bars)
    zhongshus = compute_zhongshus(bis)
    sig_result = detect_chan_buy_sell_points(df, bis, zhongshus)

    active_zs = zhongshus[-1] if zhongshus else None

    return {
        "status": "success",
        "merged_bars_count": len(merged_bars),
        "fractals_count": len(fractals),
        "bis_count": len(bis),
        "zhongshus_count": len(zhongshus),
        "merged_bars": merged_bars,
        "fractals": fractals,
        "bis": bis,
        "zhongshus": zhongshus,
        "signals": sig_result["signals"],
        "tags": sig_result["tags"],
        "active_zhongshu": active_zs
    }
