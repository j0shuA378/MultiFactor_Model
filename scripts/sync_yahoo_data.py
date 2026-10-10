#!/usr/bin/env python3
"""
Sync real market data directly from finance.yahoo.com via yfinance
Saves real-time quotes and historical candlestick OHLCV data into static/data/
for both server and GitHub Pages static deployment.
"""

import os
import sys
import json
import logging
from datetime import datetime
import numpy as np
import pandas as pd
import yfinance as yf

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("YahooSync")

STATIC_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "data")
os.makedirs(STATIC_DATA_DIR, exist_ok=True)

PRESET_TICKERS = [
    "AAPL", "NVDA", "TSLA", "MSFT", "AMZN", "GOOGL", "META", "TSM", 
    "SPY", "QQQ", "IWM", "TLT", "GLD", "AMD", "PLTR", "BABA", "COIN", 
    "BRK-B", "SMCI", "ASX", "XOM", "JPM", "BAC", "PDD", "BIDU", "JD", "NIO"
]

COMPANY_NAME_MAP = {
    "AAPL": "Apple Inc. (苹果公司)",
    "NVDA": "NVIDIA Corp. (英伟达)",
    "TSLA": "Tesla Inc. (特斯拉)",
    "MSFT": "Microsoft Corp. (微软)",
    "AMZN": "Amazon.com Inc. (亚马逊)",
    "GOOGL": "Alphabet Inc. (谷歌)",
    "META": "Meta Platforms (元宇宙)",
    "TSM": "TSMC (台积电)",
    "SPY": "SPDR S&P 500 ETF (标普500)",
    "QQQ": "Invesco QQQ Trust (纳斯达克100)",
    "IWM": "iShares Russell 2000 ETF (罗素2000)",
    "TLT": "iShares 20+ Year Treasury Bond ETF (美国国债ETF)",
    "GLD": "SPDR Gold Shares (黄金ETF)",
    "AMD": "Advanced Micro Devices (超威半导体)",
    "PLTR": "Palantir Tech (帕兰提尔)",
    "BABA": "Alibaba Group (阿里巴巴)",
    "COIN": "Coinbase Global (币安)",
    "BRK-B": "Berkshire Hathaway (伯克希尔B)",
    "SMCI": "Super Micro Computer (超微电脑)",
    "ASX": "ASE Technology Holding (日月光半导体)",
    "XOM": "Exxon Mobil Corp. (埃克森美孚)",
    "JPM": "JPMorgan Chase & Co. (摩根大通)",
    "BAC": "Bank of America (美国银行)",
    "PDD": "PDD Holdings Inc. (拼多多)",
    "BIDU": "Baidu Inc. (百度)",
    "JD": "JD.com Inc. (京东)",
    "NIO": "NIO Inc. (蔚来汽车)"
}

def sync_quotes():
    """Fetch live quote snapshots from finance.yahoo.com for all preset tickers"""
    quotes = {}
    logger.info(f"Syncing live quotes from finance.yahoo.com for {len(PRESET_TICKERS)} tickers...")

    for sym in PRESET_TICKERS:
        try:
            t = yf.Ticker(sym)
            fi = t.fast_info
            price = round(float(getattr(fi, 'last_price', 0.0) or 0.0), 2)
            prev_close = round(float(getattr(fi, 'previous_close', 0.0) or 0.0), 2)
            open_p = round(float(getattr(fi, 'open', 0.0) or 0.0), 2)
            high_p = round(float(getattr(fi, 'day_high', 0.0) or 0.0), 2)
            low_p = round(float(getattr(fi, 'day_low', 0.0) or 0.0), 2)
            vol = int(getattr(fi, 'last_volume', 0) or 0)

            # If fast_info is sparse, fetch recent 1d 1m bar
            if price <= 0:
                h = t.history(period="1d", interval="1m")
                if not h.empty:
                    price = round(float(h['Close'].iloc[-1]), 2)
                    open_p = round(float(h['Open'].iloc[0]), 2)
                    high_p = round(float(h['High'].max()), 2)
                    low_p = round(float(h['Low'].min()), 2)
                    vol = int(h['Volume'].sum())

            chg = round(price - prev_close, 2)
            chg_pct = round((chg / prev_close) * 100, 2) if prev_close > 0 else 0.0

            quotes[sym] = {
                "ticker": sym,
                "name": COMPANY_NAME_MAP.get(sym, f"{sym} Common Stock"),
                "price": price,
                "prev_close": prev_close,
                "open": open_p,
                "day_high": high_p,
                "day_low": low_p,
                "volume": vol,
                "change": chg,
                "change_pct": chg_pct,
                "currency": getattr(fi, 'currency', 'USD'),
                "synced_at": datetime.now().isoformat()
            }
            logger.info(f"[{sym}] Price: ${price} ({chg_pct:+.2f}%)")
        except Exception as e:
            logger.warning(f"Error fetching quote for {sym}: {e}")

    out_file = os.path.join(STATIC_DATA_DIR, "quotes.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(quotes, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved live quotes to {out_file}")
    return quotes

def sync_history(periods=["1y"]):
    """Fetch historical candlestick data from finance.yahoo.com and save to static/data/"""
    logger.info(f"Syncing historical data from finance.yahoo.com...")

    for sym in PRESET_TICKERS:
        t = yf.Ticker(sym)
        for period in periods:
            try:
                hist = t.history(period=period, auto_adjust=True)
                if hist.empty or len(hist) < 5:
                    continue

                candles = []
                hist['SMA_20'] = hist['Close'].rolling(window=20).mean()
                hist['SMA_50'] = hist['Close'].rolling(window=50).mean()
                std20 = hist['Close'].rolling(window=20).std()
                hist['BB_UPPER'] = hist['SMA_20'] + 2 * std20
                hist['BB_LOWER'] = hist['SMA_20'] - 2 * std20

                # RSI 14
                delta = hist['Close'].diff()
                gain = delta.clip(lower=0)
                loss = -delta.clip(upper=0)
                avg_gain = gain.rolling(window=14).mean()
                avg_loss = loss.rolling(window=14).mean()
                rs = avg_gain / avg_loss.replace(0, np.nan)
                hist['RSI_14'] = 100 - (100 / (1 + rs))

                for dt, row in hist.iterrows():
                    d_str = dt.strftime("%Y-%m-%d") if hasattr(dt, 'strftime') else str(dt)[:10]
                    def _v(val):
                        return round(float(val), 2) if pd.notna(val) else None

                    candles.append({
                        "date": d_str,
                        "open": round(float(row['Open']), 2),
                        "high": round(float(row['High']), 2),
                        "low": round(float(row['Low']), 2),
                        "close": round(float(row['Close']), 2),
                        "volume": int(row['Volume']),
                        "sma_20": _v(row.get('SMA_20')),
                        "sma_50": _v(row.get('SMA_50')),
                        "bb_upper": _v(row.get('BB_UPPER')),
                        "bb_lower": _v(row.get('BB_LOWER')),
                        "rsi_14": _v(row.get('RSI_14'))
                    })

                latest_price = candles[-1]['close'] if candles else 0.0
                prev_price = candles[-2]['close'] if len(candles) > 1 else latest_price
                change_pct = round(((latest_price - prev_price) / prev_price) * 100.0, 2) if prev_price > 0 else 0.0

                result = {
                    "status": "success",
                    "source": "finance.yahoo.com",
                    "ticker": sym,
                    "period": period,
                    "total_bars": len(candles),
                    "latest_price": latest_price,
                    "change_pct": change_pct,
                    "candles": candles
                }

                out_file = os.path.join(STATIC_DATA_DIR, f"{sym}_{period}.json")
                with open(out_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                logger.info(f"Saved {sym}_{period}.json ({len(candles)} bars, latest=${latest_price})")
            except Exception as e:
                logger.warning(f"Error fetching {sym} {period}: {e}")

if __name__ == "__main__":
    periods = sys.argv[1:] if len(sys.argv) > 1 else ["6mo", "1y", "2y"]
    sync_quotes()
    sync_history(periods)
    logger.info("Sync complete!")
