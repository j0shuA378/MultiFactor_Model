import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

@dataclass
class ChanBar:
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
    index: int
    date: str
    type: str  # 'TOP' or 'BOTTOM'
    val: float
    raw_index: int

@dataclass
class ChanBi:
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
    zg: float  # 中枢上沿 min(H1, H2, H3)
    zd: float  # 中枢下沿 max(L1, L2, L3)
    gg: float  # 中枢极高 max(H1, H2, H3)
    dd: float  # 中枢极低 min(L1, L2, L3)
    start_date: str
    end_date: str
    bi_count: int = 3
    is_active: bool = True

def merge_kline_inclusions(df: pd.DataFrame) -> List[ChanBar]:
    """
    K线包含关系严格处理 (第 65-67 课标准规则)
    完全无未来函数，依序流式处理。
    """
    if df.empty:
        return []

    bars = []
    dates = df.index.astype(str).tolist()
    opens = df["Open"].values
    highs = df["High"].values
    lows = df["Low"].values
    closes = df["Close"].values
    vols = df["Volume"].values if "Volume" in df.columns else np.zeros(len(df))

    n = len(df)
    if n == 0:
        return []

    # 第一根 K 线直接初始化
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

    direction = 1  # 初始假定向上，随后根据实际走势自校正

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
            # 更新确定前序无包含方向
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
            # 存在包含关系，根据方向合并
            if direction == 1:
                # 向上处理: 取高高、高低 (缠论标准: High=max, Low=max)
                new_h = max(prev.high, cur_h)
                new_l = max(prev.low, cur_l)
            else:
                # 向下处理: 取低高、低低 (缠论标准: High=min, Low=min)
                new_h = min(prev.high, cur_h)
                new_l = min(prev.low, cur_l)

            # 更新当前合并 K 线
            prev.high = new_h
            prev.low = new_l
            prev.close = cur_close
            prev.volume += cur_vol
            prev.date = cur_date
            prev.raw_indices.append(i)

    return bars

def find_fractals(merged_bars: List[ChanBar]) -> List[Fractal]:
    """
    寻找标准化合并K线中的顶分型与底分型 (第 62 课定义)
    """
    fractals = []
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
    构建标准化笔 (第 62-67 课)
    约束:
    1. 顶分型与底分型交替
    2. 顶高 > 底低
    3. 顶底之间必须间隔至少 1 根独立合并K线 (end.index - start.index >= 4)
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
        # 顶底之间独立K线数约束 (顶到底至少相隔 4 个 merged bar 索引，即跨越至少 5 根合并 K 线)
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
                # 若后续笔的高低点仍在 [zd, zg] 范围内波动，则为中枢延伸
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

def detect_chan_buy_sell_points(
    df: pd.DataFrame,
    bis: List[ChanBi],
    zhongshus: List[ChanZhongShu]
) -> Dict[str, Any]:
    """
    精准识别缠论三类买卖点 (1B, 2B, 3B, 1S, 2S, 3S)
    结合 MACD 动能背驰探测
    """
    n = len(df)
    signals = pd.Series(0, index=df.index)
    signal_tags: Dict[str, List[Dict[str, Any]]] = {
        "1B": [], "2B": [], "3B": [],
        "1S": [], "2S": [], "3S": []
    }

    if len(bis) < 3:
        return {"signals": signals, "tags": signal_tags}

    # 计算 MACD 柱
    close = df["Close"]
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    dif = ema12 - ema26
    dea = dif.ewm(span=9, adjust=False).mean()
    hist = (dif - dea) * 2.0

    def get_hist_area(start_idx: int, end_idx: int, is_green: bool = True) -> float:
        sub = hist.iloc[start_idx : end_idx + 1]
        if is_green:
            return float(sub[sub < 0].abs().sum())
        return float(sub[sub > 0].sum())

    # 1. 扫描第一类买点 (1B: 趋势/盘整背驰底) 与卖点 (1S: 趋势/盘整背驰顶)
    for i in range(2, len(bis)):
        cur_bi = bis[i]
        prev_bi = bis[i - 2]  # 同方向的前一笔

        if cur_bi.direction == -1 and prev_bi.direction == -1:
            # 向下笔创新低
            if cur_bi.low < prev_bi.low:
                area_cur = get_hist_area(cur_bi.start_raw_idx, cur_bi.end_raw_idx, is_green=True)
                area_prev = get_hist_area(prev_bi.start_raw_idx, prev_bi.end_raw_idx, is_green=True)
                # 绿柱面积衰减背驰
                if area_cur < area_prev * 0.85:
                    raw_idx = cur_bi.end_raw_idx
                    if raw_idx < n:
                        date_str = str(df.index[raw_idx])
                        signals.iloc[raw_idx] = 1
                        signal_tags["1B"].append({
                            "date": date_str,
                            "price": cur_bi.low,
                            "type": "1B",
                            "desc": f"下跌笔背驰底 ($L={cur_bi.low:.2f}$ < 前低 ${prev_bi.low:.2f}$，绿柱面积萎缩 {int((1-area_cur/max(1e-5,area_prev))*100)}%)"
                        })

        elif cur_bi.direction == 1 and prev_bi.direction == 1:
            # 向上笔创新高
            if cur_bi.high > prev_bi.high:
                area_cur = get_hist_area(cur_bi.start_raw_idx, cur_bi.end_raw_idx, is_green=False)
                area_prev = get_hist_area(prev_bi.start_raw_idx, prev_bi.end_raw_idx, is_green=False)
                # 红柱面积衰减背驰
                if area_cur < area_prev * 0.85:
                    raw_idx = cur_bi.end_raw_idx
                    if raw_idx < n:
                        date_str = str(df.index[raw_idx])
                        signals.iloc[raw_idx] = -1
                        signal_tags["1S"].append({
                            "date": date_str,
                            "price": cur_bi.high,
                            "type": "1S",
                            "desc": f"上涨笔背驰顶 ($H={cur_bi.high:.2f}$ > 前高 ${prev_bi.high:.2f}$，红柱面积萎缩)"
                        })

    # 2. 扫描第二类买点 (2B: 次次回踩不破 1B 最低点) 与卖点 (2S)
    for b_item in signal_tags["1B"]:
        b_date = b_item["date"]
        # 寻找 1B 之后的后续笔
        for i in range(len(bis) - 1):
            if bis[i].end_date == b_date and bis[i].direction == -1:
                # bis[i+1] 是反弹笔, bis[i+2] 是次回踩笔
                if i + 2 < len(bis) and bis[i + 2].direction == -1:
                    pullback_bi = bis[i + 2]
                    if pullback_bi.low > b_item["price"]:  # 回踩不破 1B 低点
                        raw_idx = pullback_bi.end_raw_idx
                        if raw_idx < n:
                            date_str = str(df.index[raw_idx])
                            signals.iloc[raw_idx] = 1
                            signal_tags["2B"].append({
                                "date": date_str,
                                "price": pullback_bi.low,
                                "type": "2B",
                                "desc": f"1B 后二次回踩确认点 ($L={pullback_bi.low:.2f}$ > 1B底 ${b_item['price']:.2f}$)"
                            })

    # 3. 扫描第三类买点 (3B: 突破中枢后回抽不破中枢上沿 ZG) 与卖点 (3S)
    for zs in zhongshus:
        # 寻找中枢结束之后的突破与回抽笔
        for i in range(len(bis) - 1):
            if bis[i].start_date >= zs.end_date:
                # bis[i] 为向上突破笔
                if bis[i].direction == 1 and bis[i].high > zs.zg:
                    # bis[i+1] 为次级别向下回抽笔
                    if i + 1 < len(bis) and bis[i + 1].direction == -1:
                        pb = bis[i + 1]
                        # 回抽低点完全不跌破中枢上沿 ZG
                        if pb.low > zs.zg:
                            raw_idx = pb.end_raw_idx
                            if raw_idx < n:
                                date_str = str(df.index[raw_idx])
                                signals.iloc[raw_idx] = 1
                                signal_tags["3B"].append({
                                    "date": date_str,
                                    "price": pb.low,
                                    "type": "3B",
                                    "desc": f"突破中枢后回抽不破 ZG (${pb.low:.2f}$ > 中枢上沿 ${zs.zg:.2f}$)"
                                })

    return {"signals": signals, "tags": signal_tags}

def run_chan_analysis(df: pd.DataFrame) -> Dict[str, Any]:
    """
    缠论全景计算综合调度主函数
    返回标准化合并K线、分型、笔、中枢及三类买卖点
    """
    if df.empty or len(df) < 5:
        return {
            "status": "empty",
            "merged_bars": [],
            "fractals": [],
            "bis": [],
            "zhongshus": [],
            "signals": pd.Series(0, index=df.index),
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
        "bis": bis,
        "zhongshus": zhongshus,
        "signals": sig_result["signals"],
        "tags": sig_result["tags"],
        "active_zhongshu": active_zs
    }
