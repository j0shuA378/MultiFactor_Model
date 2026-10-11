import os
import re
import json
import logging
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger("DataLoader")
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cache")

COMPANY_ALIAS_MAP = {
    # A-Share Benchmark & Index ETFs
    "沪深300": "510300.SS",
    "沪深300etf": "510300.SS",
    "300etf": "510300.SS",
    "510300": "510300.SS",
    "上证50": "510050.SS",
    "上证50etf": "510050.SS",
    "50etf": "510050.SS",
    "510050": "510050.SS",
    "创业板": "159915.SZ",
    "创业板etf": "159915.SZ",
    "159915": "159915.SZ",
    "科创50": "588000.SS",
    "科创50etf": "588000.SS",
    "588000": "588000.SS",
    "中证500": "510500.SS",
    "中证500etf": "510500.SS",
    "500etf": "510500.SS",
    "510500": "510500.SS",
    "中证1000": "512100.SS",
    "1000etf": "512100.SS",
    "512100": "512100.SS",
    "半导体etf": "512480.SS",
    "512480": "512480.SS",
    "证券etf": "512880.SS",
    "512880": "512880.SS",
    "黄金etf": "518880.SS",
    "518880": "518880.SS",

    # A-Share Bluechips & Growth Leaders
    "贵州茅台": "600519.SS",
    "茅台": "600519.SS",
    "600519": "600519.SS",
    "宁德时代": "300750.SZ",
    "宁德": "300750.SZ",
    "300750": "300750.SZ",
    "比亚迪": "002594.SZ",
    "002594": "002594.SZ",
    "平安银行": "000001.SZ",
    "000001": "000001.SZ",
    "中国平安": "601318.SS",
    "601318": "601318.SS",
    "招商银行": "600036.SS",
    "招行": "600036.SS",
    "600036": "600036.SS",
    "五粮液": "000858.SZ",
    "000858": "000858.SZ",
    "中信证券": "600030.SS",
    "600030": "600030.SS",
    "海康威视": "002415.SZ",
    "002415": "002415.SZ",
    "恒瑞医药": "600276.SS",
    "600276": "600276.SS",
    "立讯精密": "002475.SZ",
    "002475": "002475.SZ",
    "东方财富": "300059.SZ",
    "东财": "300059.SZ",
    "300059": "300059.SZ",
    "中芯国际": "688981.SS",
    "688981": "688981.SS",
    "药明康德": "603259.SS",
    "603259": "603259.SS",
    "隆基绿能": "601012.SS",
    "隆基": "601012.SS",
    "601012": "601012.SS",
    "紫金矿业": "601899.SS",
    "紫金": "601899.SS",
    "601899": "601899.SS",
    "长江电力": "600900.SS",
    "长电": "600900.SS",
    "600900": "600900.SS",

    # Hong Kong Stocks
    "腾讯": "0700.HK",
    "腾讯控股": "0700.HK",
    "0700": "0700.HK",
    "0700.hk": "0700.HK",
    "阿里": "9988.HK",
    "阿里巴巴": "9988.HK",
    "9988": "9988.HK",
    "9988.hk": "9988.HK",
    "美团": "3690.HK",
    "3690": "3690.HK",
    "3690.hk": "3690.HK",
    "小米": "1810.HK",
    "小米集团": "1810.HK",
    "1810": "1810.HK",
    "1810.hk": "1810.HK",
    "快手": "1024.HK",
    "1024": "1024.HK",

    # ASE Technology Holding
    "日月光": "ASX",
    "日月光投控": "ASX",
    "日月光半导体": "ASX",
    "ase technology": "ASX",
    "ase": "ASX",
    "asx": "ASX",
    # TSMC
    "台积电": "TSM",
    "台积": "TSM",
    "tsmc": "TSM",
    "tsm": "TSM",
    # Apple
    "苹果": "AAPL",
    "apple": "AAPL",
    "aapl": "AAPL",
    # NVIDIA
    "英伟达": "NVDA",
    "辉达": "NVDA",
    "nvidia": "NVDA",
    "nvda": "NVDA",
    # Microsoft
    "微软": "MSFT",
    "microsoft": "MSFT",
    "msft": "MSFT",
    # Tesla
    "特斯拉": "TSLA",
    "tesla": "TSLA",
    "tsla": "TSLA",
    # Amazon
    "亚马逊": "AMZN",
    "amazon": "AMZN",
    "amzn": "AMZN",
    # Google
    "谷歌": "GOOGL",
    "谷歌a": "GOOGL",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "googl": "GOOGL",
    # Meta
    "脸书": "META",
    "元宇宙": "META",
    "meta": "META",
    "facebook": "META",
    # Goldman Sachs
    "高盛": "GS",
    "高盛集团": "GS",
    "goldman": "GS",
    "gs": "GS",
    # Morgan Stanley
    "摩根士丹利": "MS",
    "大摩": "MS",
    "ms": "MS",
    # JPMorgan Chase
    "摩根大通": "JPM",
    "小摩": "JPM",
    "jpm": "JPM",
    # Alibaba ADR
    "baba": "BABA",
    # Tencent ADR
    "tcehy": "TCEHY",
    # AMD
    "超微": "AMD",
    "超微半导体": "AMD",
    "amd": "AMD",
    # Intel
    "英特尔": "INTC",
    "intel": "INTC",
    # Qualcomm
    "高通": "QCOM",
    "qualcomm": "QCOM",
    # Broadcom
    "博通": "AVGO",
    "broadcom": "AVGO",
    # Palantir
    "palantir": "PLTR",
    # Netflix
    "奈飞": "NFLX",
    "网飞": "NFLX",
    "netflix": "NFLX",
    # Benchmarks
    "标普": "SPY",
    "标普500": "SPY",
    "spy": "SPY",
    "纳指": "QQQ",
    "纳斯达克": "QQQ",
    "纳斯达克100": "QQQ",
    "qqq": "QQQ",
    "黄金": "GLD",
    "gld": "GLD"
}

COMPANY_NAME_LOOKUP = {
    # A-Share
    "510300.SS": "华泰柏瑞沪深300 ETF",
    "510050.SS": "华夏上证50 ETF",
    "159915.SZ": "易方达创业板 ETF",
    "588000.SS": "华夏科创50 ETF",
    "510500.SS": "南方中证500 ETF",
    "600519.SS": "贵州茅台酒股份有限公司",
    "300750.SZ": "宁德时代新能源科技",
    "002594.SZ": "比亚迪股份有限公司",
    "000001.SZ": "平安银行股份有限公司",
    "601318.SS": "中国平安保险集团",
    "600036.SS": "招商银行股份有限公司",
    "000858.SZ": "宜宾五粮液股份有限公司",
    "600030.SS": "中信证券股份有限公司",
    "002415.SZ": "海康威视数字技术",
    "600276.SS": "江苏恒瑞医药",
    "002475.SZ": "立讯精密工业",
    "300059.SZ": "东方财富信息",
    "688981.SS": "中芯国际集成电路",
    # HK
    "0700.HK": "腾讯控股有限公司",
    "9988.HK": "阿里巴巴集团控股",
    "3690.HK": "美团点评",
    "1810.HK": "小米集团",
    # US
    "ASX": "ASE Technology Holding Co., Ltd.",
    "TSM": "Taiwan Semiconductor Manufacturing Co.",
    "AAPL": "Apple Inc.",
    "NVDA": "NVIDIA Corporation",
    "MSFT": "Microsoft Corporation",
    "TSLA": "Tesla, Inc.",
    "AMZN": "Amazon.com, Inc.",
    "GOOGL": "Alphabet Inc.",
    "META": "Meta Platforms, Inc.",
    "GS": "The Goldman Sachs Group, Inc.",
    "MS": "Morgan Stanley",
    "JPM": "JPMorgan Chase & Co.",
    "AMD": "Advanced Micro Devices, Inc.",
    "BABA": "Alibaba Group Holding Ltd.",
    "SPY": "SPDR S&P 500 ETF Trust",
    "QQQ": "Invesco QQQ Trust",
    "GLD": "SPDR Gold Shares ETF",
    "IAUM": "iShares Gold Trust Micro Shares",
    "BITO": "ProShares Bitcoin Strategy ETF",
    "SOXL": "Direxion Daily Semiconductor Bull 3X Shares"
}

def sanitize_ticker(raw_ticker: str) -> str:
    """
    Cleans raw ticker input or company query string.
    Supports:
    - Symbols enclosed in brackets: '贵州茅台 (600519.SS)' -> '600519.SS'
    - Chinese/English company aliases: '贵州茅台' -> '600519.SS', '日月光' -> 'ASX', '高盛' -> 'GS'
    - 6-digit A-share auto-suffix: '600519' -> '600519.SS', '000001' -> '000001.SZ'
    - 4-digit HK auto-suffix: '0700' -> '0700.HK'
    - IME pinyin apostrophes: "a's'x" -> 'ASX'
    """
    if not raw_ticker:
        return "AAPL"
    s = str(raw_ticker).strip()

    # 1. Check if symbol is enclosed in parentheses/brackets () （） [] 【】
    m = re.search(r'[\(（\[【]([A-Za-z0-9\.\-\^]+)[\)）\]】]', s)
    if m:
        sym = m.group(1).upper().strip()
        if len(sym) == 6 and sym.isdigit():
            if sym.startswith(('60', '688', '51', '56', '58')):
                return f"{sym}.SS"
            elif sym.startswith(('00', '30', '15', '16')):
                return f"{sym}.SZ"
            elif sym.startswith(('8', '4', '9')):
                return f"{sym}.BJ"
        return sym

    # 2. Check alias map after removing IME apostrophes
    s_clean = s.replace("'", "").replace("’", "").strip().lower()
    if s_clean in COMPANY_ALIAS_MAP:
        return COMPANY_ALIAS_MAP[s_clean]
    for ch_name, sym in COMPANY_ALIAS_MAP.items():
        if ch_name in s_clean:
            return sym

    # 3. Strip special punctuation and return uppercase
    cleaned = re.sub(r'[\s\'’",\(\)（）]', '', s).upper()

    # 4. Auto-append exchange suffix for 6-digit A-share codes
    if len(cleaned) == 6 and cleaned.isdigit():
        if cleaned.startswith(('60', '688', '51', '56', '58')):
            return f"{cleaned}.SS"
        elif cleaned.startswith(('00', '30', '15', '16')):
            return f"{cleaned}.SZ"
        elif cleaned.startswith(('8', '4', '9')):
            return f"{cleaned}.BJ"

    # 5. Auto-append .HK for 4-digit HK stocks (e.g. 0700, 9988, 3690)
    if (len(cleaned) == 4 or len(cleaned) == 5) and cleaned.isdigit():
        return f"{cleaned.zfill(4)}.HK"

    return cleaned if cleaned else "AAPL"

def ensure_cache_dir():
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR, exist_ok=True)

def generate_synthetic_data(ticker: str, days: int = 500) -> pd.DataFrame:
    """Generates realistic synthetic stock data when external API is unreachable"""
    np.random.seed(abs(hash(ticker)) % (2**32))
    end_date = datetime.now()
    dates = pd.date_range(end=end_date, periods=days, freq='B')
    
    # Base parameters tailored to ticker symbol based on current Yahoo Finance levels
    base_price = 150.0
    if ticker.startswith("600519"): base_price = 1263.0
    elif ticker.startswith("510300"): base_price = 4.39
    elif ticker.startswith("510050"): base_price = 3.12
    elif ticker.startswith("159915"): base_price = 2.45
    elif ticker.startswith("588000"): base_price = 1.08
    elif ticker.startswith("510500"): base_price = 5.82
    elif ticker.startswith("300750"): base_price = 245.0
    elif ticker.startswith("002594"): base_price = 285.0
    elif ticker.startswith("000001"): base_price = 11.59
    elif ticker.startswith("601318"): base_price = 52.80
    elif ticker.startswith("600036"): base_price = 38.60
    elif ticker.startswith("000858"): base_price = 142.0
    elif ticker.startswith("0700"): base_price = 425.0
    elif ticker.startswith("9988"): base_price = 88.5
    elif ticker.startswith("3690"): base_price = 125.0
    elif ticker.startswith("1810"): base_price = 18.2
    elif ticker == "AAPL": base_price = 336.64
    elif ticker == "NVDA": base_price = 229.28
    elif ticker == "TSLA": base_price = 382.70
    elif ticker == "MSFT": base_price = 535.07
    elif ticker == "AMZN": base_price = 262.43
    elif ticker == "GOOGL": base_price = 351.66
    elif ticker == "META": base_price = 718.67
    elif ticker == "TSM": base_price = 453.31
    elif ticker == "SPY": base_price = 778.57
    elif ticker == "QQQ": base_price = 751.27
    elif ticker == "AMD": base_price = 608.10
    elif ticker == "PLTR": base_price = 209.05
    elif ticker == "BABA": base_price = 111.37
    elif ticker == "COIN": base_price = 179.39
    elif ticker == "BRK-B": base_price = 515.62
    elif ticker == "SMCI": base_price = 41.86
    elif ticker == "ASX": base_price = 46.43
    elif ticker == "GLD": base_price = 384.58
    elif ticker == "XOM": base_price = 168.94
    elif ticker == "JPM": base_price = 332.99
    elif ticker == "BAC": base_price = 54.32

    # Geometric Brownian Motion simulation
    dt = 1 / 252
    mu = 0.15 # annual drift
    sigma = 0.28 # annual volatility
    
    returns = np.random.normal((mu - 0.5 * sigma**2) * dt, sigma * np.sqrt(dt), size=len(dates))
    cum_ret = np.cumsum(returns)
    # Anchor to base_price on the latest date
    price_series = base_price * np.exp(cum_ret - cum_ret[-1])
    
    records = []
    for i, date in enumerate(dates):
        close_val = round(float(price_series[i]), 2)
        intraday_var = close_val * np.random.uniform(0.005, 0.025)
        high_val = round(close_val + intraday_var * np.random.uniform(0.3, 1.0), 2)
        low_val = round(close_val - intraday_var * np.random.uniform(0.3, 1.0), 2)
        open_val = round(low_val + (high_val - low_val) * np.random.uniform(0.2, 0.8), 2)
        vol = int(np.random.lognormal(16.5, 0.6))
        
        records.append({
            "Date": date.strftime("%Y-%m-%d"),
            "Open": open_val,
            "High": max(high_val, open_val, close_val),
            "Low": min(low_val, open_val, close_val),
            "Close": close_val,
            "Volume": vol
        })
        
    df = pd.DataFrame(records)
    df.set_index("Date", inplace=True)
    return df

def fetch_stock_data(ticker: str = "AAPL", period: str = "2y", use_cache: bool = True) -> pd.DataFrame:
    """
    Fetches historical OHLCV data for given ticker and period.
    Returns DataFrame with columns: Open, High, Low, Close, Volume, indexed by Date string 'YYYY-MM-DD'.
    """
    ensure_cache_dir()
    ticker = sanitize_ticker(ticker)
    cache_path = os.path.join(CACHE_DIR, f"{ticker}_{period}.json")
    
    # Check cache freshness (cached within 4 hours)
    if use_cache and os.path.exists(cache_path):
        try:
            mtime = os.path.getmtime(cache_path)
            if datetime.now() - datetime.fromtimestamp(mtime) < timedelta(hours=4):
                df = pd.read_json(cache_path)
                if not df.empty and 'Close' in df.columns:
                    df.index = [pd.to_datetime(d).strftime("%Y-%m-%d") for d in df.index]
                    df.index.name = "Date"
                    return df
        except Exception as e:
            logger.warning(f"Failed to read cache for {ticker}: {e}")

    # Fetch from Yahoo Finance
    try:
        t = yf.Ticker(ticker)
        raw_df = t.history(period=period, auto_adjust=True)
        if raw_df is not None and len(raw_df) > 10:
            price_cols = ['Open', 'High', 'Low', 'Close']
            for col in price_cols:
                if col not in raw_df.columns:
                    raise KeyError(f"Missing required price column: {col}")
            df = raw_df[price_cols].copy()
            df['Volume'] = raw_df['Volume'].fillna(1000000) if 'Volume' in raw_df.columns else 1000000
            # Standardize index to YYYY-MM-DD string
            df.index = [pd.to_datetime(d).strftime("%Y-%m-%d") for d in df.index]
            df.index.name = "Date"
            
            # Clean NaN and round
            df = df.dropna()
            df = df.round(4)
            
            # Save cache
            try:
                df.to_json(cache_path, indent=2)
            except Exception as e:
                logger.warning(f"Could not save cache: {e}")
                
            return df
        else:
            raise ValueError(f"No sufficient data returned for ticker {ticker}")
    except Exception as e:
        logger.error(f"Error fetching from yfinance for {ticker}: {e}. Falling back to cached or synthetic data.")
        # If cache exists even if old, use it
        if os.path.exists(cache_path):
            try:
                df = pd.read_json(cache_path)
                df.index = [pd.to_datetime(d).strftime("%Y-%m-%d") for d in df.index]
                df.index.name = "Date"
                return df
            except Exception:
                pass
        # Fallback to realistic synthetic data
        days_map = {"6mo": 130, "1y": 252, "2y": 504, "3y": 756, "5y": 1260, "max": 1500}
        days = days_map.get(period, 504)
        synthetic_df = generate_synthetic_data(ticker, days=days)
        return synthetic_df

def get_preset_tickers():
    """List of popular preset tickers with company profiles"""
    return [
        {"symbol": "AAPL", "name": "Apple Inc.", "sector": "Technology", "badge": "Mega Tech"},
        {"symbol": "NVDA", "name": "NVIDIA Corp.", "sector": "Semiconductors", "badge": "AI Leader"},
        {"symbol": "TSLA", "name": "Tesla, Inc.", "sector": "Automotive / Clean Energy", "badge": "High Volatility"},
        {"symbol": "MSFT", "name": "Microsoft Corp.", "sector": "Software & Cloud", "badge": "Tech Giant"},
        {"symbol": "ASX", "name": "ASE Technology Holding Co.", "sector": "Semiconductors / Packaging", "badge": "OSAT Leader"},
        {"symbol": "TSM", "name": "Taiwan Semiconductor Mfg", "sector": "Semiconductors / Foundry", "badge": "Foundry Giant"},
        {"symbol": "SPY", "name": "SPDR S&P 500 ETF", "sector": "Broad Market ETF", "badge": "Index Benchmark"},
        {"symbol": "QQQ", "name": "Invesco QQQ Trust (Nasdaq 100)", "sector": "Nasdaq 100 ETF", "badge": "Growth Index"},
        {"symbol": "AMZN", "name": "Amazon.com Inc.", "sector": "Consumer / Cloud", "badge": "E-Commerce"},
        {"symbol": "GOOGL", "name": "Alphabet Inc.", "sector": "Internet / Search", "badge": "AI Tech"},
        {"symbol": "AMD", "name": "Advanced Micro Devices", "sector": "Semiconductors", "badge": "Chipmaker"},
        {"symbol": "BABA", "name": "Alibaba Group ADR", "sector": "China E-Commerce", "badge": "ADR"}
    ]

SEARCH_CACHE = {}
PRICE_CACHE = {}

FALLBACK_STOCKS = [
    # A-Share Benchmark & Index ETFs
    {"symbol": "510300.SS", "name": "华泰柏瑞沪深300 ETF", "exchange": "SSE", "price": 4.39, "change_pct": 0.05, "type": "ETF"},
    {"symbol": "510050.SS", "name": "华夏上证50 ETF", "exchange": "SSE", "price": 3.12, "change_pct": -0.12, "type": "ETF"},
    {"symbol": "159915.SZ", "name": "易方达创业板 ETF", "exchange": "SZSE", "price": 2.45, "change_pct": 0.41, "type": "ETF"},
    {"symbol": "588000.SS", "name": "华夏科创50 ETF", "exchange": "SSE", "price": 1.08, "change_pct": 0.85, "type": "ETF"},
    {"symbol": "510500.SS", "name": "南方中证500 ETF", "exchange": "SSE", "price": 5.82, "change_pct": 0.22, "type": "ETF"},
    {"symbol": "512880.SS", "name": "国泰中证全指证券 ETF", "exchange": "SSE", "price": 1.15, "change_pct": 0.35, "type": "ETF"},
    {"symbol": "512480.SS", "name": "国泰CES半导体芯片 ETF", "exchange": "SSE", "price": 0.98, "change_pct": 1.25, "type": "ETF"},

    # A-Share Core Blue Chips & Leaders
    {"symbol": "600519.SS", "name": "贵州茅台 (白酒龙头)", "exchange": "SSE", "price": 1263.00, "change_pct": 0.64, "type": "Equity"},
    {"symbol": "300750.SZ", "name": "宁德时代 (动力电池龙头)", "exchange": "SZSE", "price": 245.50, "change_pct": 1.82, "type": "Equity"},
    {"symbol": "002594.SZ", "name": "比亚迪 (新能源汽车龙头)", "exchange": "SZSE", "price": 285.20, "change_pct": 1.15, "type": "Equity"},
    {"symbol": "000001.SZ", "name": "平安银行 (商业银行标杆)", "exchange": "SZSE", "price": 11.59, "change_pct": -0.42, "type": "Equity"},
    {"symbol": "601318.SS", "name": "中国平安 (金融保险综合龙头)", "exchange": "SSE", "price": 52.80, "change_pct": 0.58, "type": "Equity"},
    {"symbol": "600036.SS", "name": "招商银行 (零售银行标杆)", "exchange": "SSE", "price": 38.60, "change_pct": 0.26, "type": "Equity"},
    {"symbol": "000858.SZ", "name": "五粮液 (高端浓香白酒)", "exchange": "SZSE", "price": 142.30, "change_pct": 0.45, "type": "Equity"},
    {"symbol": "600030.SS", "name": "中信证券 (券商龙头)", "exchange": "SSE", "price": 28.50, "change_pct": 0.71, "type": "Equity"},
    {"symbol": "002415.SZ", "name": "海康威视 (安防与智能视觉)", "exchange": "SZSE", "price": 31.40, "change_pct": -0.32, "type": "Equity"},
    {"symbol": "600276.SS", "name": "恒瑞医药 (创新药龙头)", "exchange": "SSE", "price": 48.90, "change_pct": 0.88, "type": "Equity"},
    {"symbol": "688981.SS", "name": "中芯国际 (晶圆制造龙头)", "exchange": "SSE", "price": 95.60, "change_pct": 2.15, "type": "Equity"},
    {"symbol": "300059.SZ", "name": "东方财富 (互联网券商龙头)", "exchange": "SZSE", "price": 21.80, "change_pct": 1.45, "type": "Equity"},

    # HK Core Stocks
    {"symbol": "0700.HK", "name": "腾讯控股 (社交网络与游戏龙头)", "exchange": "HKEX", "price": 425.20, "change_pct": 1.48, "type": "Equity"},
    {"symbol": "9988.HK", "name": "阿里巴巴 (电商与云计算)", "exchange": "HKEX", "price": 88.50, "change_pct": 0.91, "type": "Equity"},
    {"symbol": "3690.HK", "name": "美团 (本地生活服务龙头)", "exchange": "HKEX", "price": 125.40, "change_pct": 2.12, "type": "Equity"},
    {"symbol": "1810.HK", "name": "小米集团 (消费电子与智能汽车)", "exchange": "HKEX", "price": 18.20, "change_pct": 1.11, "type": "Equity"},

    # US Mega Tech & Benchmarks
    {"symbol": "AAPL", "name": "Apple Inc. (苹果公司)", "exchange": "NASDAQ", "price": 336.64, "change_pct": -1.11, "type": "Equity"},
    {"symbol": "NVDA", "name": "NVIDIA Corporation (英伟达)", "exchange": "NASDAQ", "price": 229.28, "change_pct": -0.52, "type": "Equity"},
    {"symbol": "TSLA", "name": "Tesla, Inc. (特斯拉)", "exchange": "NASDAQ", "price": 382.70, "change_pct": 2.05, "type": "Equity"},
    {"symbol": "MSFT", "name": "Microsoft Corporation (微软)", "exchange": "NASDAQ", "price": 535.07, "change_pct": 2.38, "type": "Equity"},
    {"symbol": "AMZN", "name": "Amazon.com, Inc. (亚马逊)", "exchange": "NASDAQ", "price": 262.43, "change_pct": -0.45, "type": "Equity"},
    {"symbol": "GOOGL", "name": "Alphabet Inc. (谷歌)", "exchange": "NASDAQ", "price": 351.66, "change_pct": 1.12, "type": "Equity"},
    {"symbol": "META", "name": "Meta Platforms, Inc. (元宇宙)", "exchange": "NASDAQ", "price": 718.67, "change_pct": 1.65, "type": "Equity"},
    {"symbol": "TSM", "name": "Taiwan Semiconductor (台积电)", "exchange": "NYSE", "price": 453.31, "change_pct": 1.95, "type": "Equity"},
    {"symbol": "AMD", "name": "Advanced Micro Devices (超微)", "exchange": "NASDAQ", "price": 608.10, "change_pct": -1.80, "type": "Equity"},
    {"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust (标普500)", "exchange": "NYSEArca", "price": 778.57, "change_pct": 0.32, "type": "ETF"},
    {"symbol": "QQQ", "name": "Invesco QQQ Trust (纳斯达克100)", "exchange": "NASDAQ", "price": 751.27, "change_pct": 0.45, "type": "ETF"},
    {"symbol": "GLD", "name": "SPDR Gold Shares (黄金ETF)", "exchange": "NYSEArca", "price": 384.58, "change_pct": 0.65, "type": "ETF"},
    {"symbol": "BABA", "name": "Alibaba Group Holding (阿里巴巴ADR)", "exchange": "NYSE", "price": 111.37, "change_pct": 5.36, "type": "Equity"},
    {"symbol": "PLTR", "name": "Palantir Technologies (大数据与AI)", "exchange": "NYSE", "price": 209.05, "change_pct": 3.45, "type": "Equity"},
    {"symbol": "ASX", "name": "ASE Technology Holding Co., Ltd. (日月光)", "exchange": "NYSE", "price": 46.43, "change_pct": 2.04, "type": "Equity"},
    {"symbol": "IAUM", "name": "iShares Gold Trust Micro Shares", "exchange": "PCX", "price": 41.81, "change_pct": 1.28, "type": "ETF"}
]

TICKER_METADATA_CACHE = {}

def get_ticker_metadata(ticker: str) -> dict:
    """
    Resolves authentic metadata (name, exchange, type, currency) for any ticker or ETF globally.
    Uses layered resolution: Memory Cache -> Preset Map -> Fallback Stocks -> yfinance fast_info.
    """
    ticker = sanitize_ticker(ticker)
    sym_upper = ticker.upper()
    if sym_upper in TICKER_METADATA_CACHE:
        return dict(TICKER_METADATA_CACHE[sym_upper])

    # Preset / local baseline
    resolved_name = COMPANY_NAME_LOOKUP.get(sym_upper)
    resolved_exch = "SSE" if sym_upper.endswith(".SS") else ("SZSE" if sym_upper.endswith(".SZ") else ("HKEX" if sym_upper.endswith(".HK") else "NASDAQ"))
    resolved_type = "ETF" if any(k in sym_upper for k in ["51", "15", "58", "SPY", "QQQ", "GLD", "IAUM", "BITO", "SOXL"]) else "Equity"
    resolved_curr = "CNY" if sym_upper.endswith((".SS", ".SZ")) else ("HKD" if sym_upper.endswith(".HK") else "USD")

    fb = next((item for item in FALLBACK_STOCKS if item["symbol"].upper() == sym_upper), None)
    if fb:
        resolved_name = fb.get("name") or resolved_name
        resolved_exch = fb.get("exchange") or resolved_exch
        resolved_type = fb.get("type") or resolved_type

    # Fast info metadata retrieval
    try:
        t = yf.Ticker(sym_upper)
        fi = t.fast_info
        if hasattr(fi, 'exchange') and fi.exchange:
            resolved_exch = fi.exchange
        if hasattr(fi, 'quote_type') and fi.quote_type:
            qt_map = {'EQUITY': 'Equity', 'ETF': 'ETF', 'MUTUALFUND': 'Fund', 'INDEX': 'Index', 'CURRENCY': 'FX', 'CRYPTOCURRENCY': 'Crypto'}
            resolved_type = qt_map.get(str(fi.quote_type).upper(), str(fi.quote_type).capitalize())
        if hasattr(fi, 'currency') and fi.currency:
            resolved_curr = fi.currency

        if not resolved_name or resolved_name == sym_upper:
            info = getattr(t, 'info', {}) or {}
            short_name = info.get('shortName') or info.get('longName')
            if short_name:
                resolved_name = short_name
    except Exception:
        pass

    if not resolved_name:
        resolved_name = f"{sym_upper} ETF" if resolved_type == "ETF" else f"{sym_upper} Stock"

    meta = {
        "symbol": sym_upper,
        "ticker": sym_upper,
        "name": resolved_name,
        "exchange": resolved_exch,
        "type": resolved_type,
        "currency": resolved_curr
    }
    TICKER_METADATA_CACHE[sym_upper] = meta
    COMPANY_NAME_LOOKUP[sym_upper] = resolved_name
    return meta

def search_yahoo_tickers(query: str, max_results: int = 6):
    """
    Search Yahoo Finance and Institutional Catalog for matching tickers.
    Fetches official Yahoo Finance search suggestions in <0.5s for any global stock or ETF.
    Supports A-Share, HK Stocks, US Equities & ETFs.
    """
    if not query or not str(query).strip():
        return []

    raw_query = str(query).strip()
    clean_q = raw_query.replace("'", "").replace("’", "").strip()

    # 1. Bracket extraction: e.g. "贵州茅台 (600519.SS)" -> "600519.SS"
    bracket_match = re.search(r'[\(（\[【]([A-Za-z0-9\.\-\^]+)[\)）\]】]', clean_q)
    extracted_sym = bracket_match.group(1).upper() if bracket_match else None

    # 2. Chinese/English company alias check
    q_lower = clean_q.lower()
    alias_sym = COMPANY_ALIAS_MAP.get(q_lower)
    if not alias_sym:
        for k, v in COMPANY_ALIAS_MAP.items():
            if k in q_lower or q_lower in k:
                alias_sym = v
                break

    primary_sym = extracted_sym or alias_sym
    if not primary_sym and len(clean_q) == 6 and clean_q.isdigit():
        primary_sym = sanitize_ticker(clean_q)

    search_term = primary_sym if primary_sym else clean_q

    cache_key = (search_term.lower(), max_results)
    now = datetime.now()
    if cache_key in SEARCH_CACHE:
        cached_t, cached_data = SEARCH_CACHE[cache_key]
        if (now - cached_t).total_seconds() < 120:
            return cached_data

    # 3. Check local catalog first
    local_matches = []
    if primary_sym:
        for stock in FALLBACK_STOCKS:
            if stock['symbol'].upper() == primary_sym:
                local_matches.append(dict(stock))
                break

    for stock in FALLBACK_STOCKS:
        if any(m['symbol'] == stock['symbol'] for m in local_matches):
            continue
        s_sym = stock['symbol'].lower()
        s_name = stock['name'].lower()
        if q_lower in s_sym or s_sym.startswith(q_lower) or q_lower in s_name:
            local_matches.append(dict(stock))
        if len(local_matches) >= max_results:
            break

    results = []

    # 4. Fetch directly from Yahoo Finance official search API
    try:
        encoded_term = urllib.parse.quote(search_term)
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={encoded_term}&quotesCount=10&newsCount=0"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        )
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        raw_quotes = data.get("quotes", []) or []
        for q in raw_quotes:
            sym = str(q.get("symbol", "")).upper().strip()
            if not sym:
                continue

            # Filter out derivative options (e.g. BITO261218C00011000)
            if q.get("quoteType") == "OPTION" or (len(sym) > 8 and any(c.isdigit() for c in sym) and not sym.endswith((".SS", ".SZ", ".HK", ".TO", ".L", ".NE", ".MX"))):
                continue

            qtype = str(q.get("quoteType", "")).upper()
            type_map = {
                "EQUITY": "Equity",
                "ETF": "ETF",
                "MUTUALFUND": "Fund",
                "INDEX": "Index",
                "CURRENCY": "FX",
                "CRYPTOCURRENCY": "Crypto"
            }
            disp_type = type_map.get(qtype, q.get("typeDisp") or qtype.capitalize() or "Stock")
            disp_name = q.get("shortname") or q.get("longname") or sym
            disp_exch = q.get("exchDisp") or q.get("exchange") or ""

            # Check cached price
            price, chg_pct = None, None
            if sym in PRICE_CACHE:
                cached_time, c_price, c_chg = PRICE_CACHE[sym]
                if (now - cached_time).total_seconds() < 300:
                    price, chg_pct = c_price, c_chg

            # Store in metadata cache
            TICKER_METADATA_CACHE[sym] = {
                "symbol": sym,
                "ticker": sym,
                "name": disp_name,
                "exchange": disp_exch,
                "type": disp_type,
                "currency": q.get("currency", "USD")
            }
            COMPANY_NAME_LOOKUP[sym] = disp_name

            results.append({
                "symbol": sym,
                "name": disp_name,
                "exchange": disp_exch,
                "type": disp_type,
                "price": price,
                "change_pct": chg_pct
            })

            if len(results) >= max_results:
                break
    except Exception as e:
        logger.warning(f"Yahoo Finance search endpoint request failed for '{search_term}': {e}")

    # Merge local matches (especially Chinese-annotated blue chips)
    merged = []
    seen = set()
    # If user searched Chinese alias, prefer local matched Chinese name
    if any('\u4e00' <= char <= '\u9fff' for char in raw_query):
        for lm in local_matches:
            if lm['symbol'] not in seen:
                merged.append(lm)
                seen.add(lm['symbol'])

    for r in results:
        if r['symbol'] not in seen:
            merged.append(r)
            seen.add(r['symbol'])

    for lm in local_matches:
        if lm['symbol'] not in seen:
            merged.append(lm)
            seen.add(lm['symbol'])

    final_results = merged[:max_results]
    SEARCH_CACHE[cache_key] = (now, final_results)
    return final_results

def fetch_realtime_quote(ticker: str = "AAPL") -> dict:
    """
    Grabs real-time market quote directly from finance.yahoo.com via yfinance.
    Returns dictionary with latest price, prev_close, change, change_pct, open, high, low, volume, name, exchange, type.
    """
    ticker = sanitize_ticker(ticker)
    meta = get_ticker_metadata(ticker)
    try:
        t = yf.Ticker(ticker)
        fi = t.fast_info
        last_price = float(getattr(fi, 'last_price', 0.0) or 0.0)
        prev_close = float(getattr(fi, 'previous_close', 0.0) or 0.0)
        open_price = float(getattr(fi, 'open', 0.0) or 0.0)
        day_high = float(getattr(fi, 'day_high', 0.0) or 0.0)
        day_low = float(getattr(fi, 'day_low', 0.0) or 0.0)
        volume = int(getattr(fi, 'last_volume', 0) or 0)

        # Fallback to recent 1m bar if fast_info is sparse
        if last_price <= 0:
            h = t.history(period="1d", interval="1m")
            if not h.empty:
                last_price = float(h['Close'].iloc[-1])
                open_price = float(h['Open'].iloc[0])
                day_high = float(h['High'].max())
                day_low = float(h['Low'].min())
                volume = int(h['Volume'].sum())

        chg = round(last_price - prev_close, 2)
        chg_pct = round((chg / prev_close) * 100, 2) if prev_close > 0 else 0.0

        exch = getattr(fi, 'exchange', None) or meta.get('exchange') or ''
        qtype = getattr(fi, 'quote_type', None) or meta.get('type') or 'Stock'
        cur = getattr(fi, 'currency', None) or meta.get('currency') or 'USD'

        quote_dict = {
            "status": "success",
            "source": "finance.yahoo.com",
            "ticker": ticker,
            "name": meta.get('name', ticker),
            "exchange": exch,
            "type": qtype,
            "price": round(last_price, 2),
            "prev_close": round(prev_close, 2),
            "open": round(open_price, 2),
            "high": round(day_high, 2),
            "low": round(day_low, 2),
            "volume": volume,
            "change": chg,
            "change_pct": chg_pct,
            "currency": cur,
            "timestamp": datetime.now().isoformat()
        }
        PRICE_CACHE[ticker.upper()] = (datetime.now(), round(last_price, 2), chg_pct)
        return quote_dict
    except Exception as e:
        logger.error(f"Error fetching quote from finance.yahoo.com for {ticker}: {e}")
        return {
            "status": "error",
            "message": str(e),
            "ticker": ticker,
            "name": meta.get('name', ticker),
            "exchange": meta.get('exchange', ''),
            "type": meta.get('type', 'Stock')
        }

FUNDAMENTALS_CACHE = {}

def format_metric_currency(val, currency_prefix="$"):
    if val is None or val == 0:
        return "N/A"
    try:
        val = float(val)
        abs_v = abs(val)
        sign = "-" if val < 0 else ""
        if abs_v >= 1e12:
            return f"{sign}{currency_prefix}{abs_v / 1e12:.2f}T"
        elif abs_v >= 1e9:
            return f"{sign}{currency_prefix}{abs_v / 1e9:.2f}B"
        elif abs_v >= 1e6:
            return f"{sign}{currency_prefix}{abs_v / 1e6:.2f}M"
        elif abs_v >= 1e3:
            return f"{sign}{currency_prefix}{abs_v / 1e3:.2f}K"
        return f"{sign}{currency_prefix}{abs_v:.2f}"
    except Exception:
        return "N/A"

# Institutional Baseline Profiles for Instant High-Speed Fallback
PRESET_FUNDAMENTALS_FALLBACK = {
    "AAPL": {
        "sector": "科技与消费电子 (Technology)", "industry": "智能硬件与消费电子 (Consumer Electronics)",
        "market_cap": 4912984883200, "enterprise_value": 4980000000000,
        "trailing_pe": 38.61, "forward_pe": 35.11, "price_to_book": 45.74, "price_to_sales": 10.52,
        "trailing_eps": 8.72, "forward_eps": 9.59, "beta": 1.07,
        "fifty_two_week_high": 345.50, "fifty_two_week_low": 220.10,
        "total_revenue": 466822987776, "net_income": 128900000000,
        "gross_margins_pct": 48.65, "operating_margins_pct": 32.10, "profit_margins_pct": 27.62,
        "return_on_equity_pct": 148.50, "debt_to_equity": 78.45,
        "operating_cashflow": 122000000000, "free_cashflow": 108000000000,
        "revenue_growth_pct": 6.10, "earnings_growth_pct": 10.40,
        "target_mean_price": 328.09, "target_high_price": 405.00, "target_low_price": 215.00,
        "recommendation_key": "buy", "recommendation_display": "买入 (Buy)", "number_of_analysts": 39,
        "dividend_rate": 1.08, "dividend_yield_pct": 0.32, "ex_dividend_date": "2026-08-10", "payout_ratio_pct": 14.80,
        "website": "https://www.apple.com", "employees": 161000, "city": "Cupertino", "country": "United States",
        "summary": "苹果公司（Apple Inc.）是全球领先的个人消费电子与软件服务巨头，主营 iPhone、Mac、iPad、可穿戴设备以及 App Store、Apple Pay、iCloud 等生态订阅服务。"
    },
    "NVDA": {
        "sector": "半导体与人工智能 (Technology)", "industry": "图形处理器与AI计算加速芯片 (Semiconductors)",
        "market_cap": 5536424132608, "enterprise_value": 5490000000000,
        "trailing_pe": 28.99, "forward_pe": 14.41, "price_to_book": 38.20, "price_to_sales": 18.40,
        "trailing_eps": 7.91, "forward_eps": 15.92, "beta": 1.68,
        "fifty_two_week_high": 242.00, "fifty_two_week_low": 85.00,
        "total_revenue": 130490000000, "net_income": 72880000000,
        "gross_margins_pct": 75.12, "operating_margins_pct": 62.40, "profit_margins_pct": 55.85,
        "return_on_equity_pct": 115.20, "debt_to_equity": 18.25,
        "operating_cashflow": 65000000000, "free_cashflow": 60500000000,
        "revenue_growth_pct": 122.40, "earnings_growth_pct": 168.00,
        "target_mean_price": 328.72, "target_high_price": 400.00, "target_low_price": 200.00,
        "recommendation_key": "strong_buy", "recommendation_display": "强力买入 (Strong Buy)", "number_of_analysts": 59,
        "dividend_rate": 0.04, "dividend_yield_pct": 0.44, "ex_dividend_date": "2026-09-10", "payout_ratio_pct": 1.20,
        "website": "https://www.nvidia.com", "employees": 29600, "city": "Santa Clara", "country": "United States",
        "summary": "英伟达（NVIDIA Corporation）是全球生成式 AI 计算加速与全栈算力架构的垄断级先锋，提供 Blackwell/Hopper 架构 GPU、CUDA 生态系统及端到端网络互联方案。"
    },
    "TSLA": {
        "sector": "新能源汽车与清洁能源 (Consumer Cyclical)", "industry": "智能电动汽车与自主AI机器人 (Auto Manufacturers)",
        "market_cap": 1215000000000, "enterprise_value": 1180000000000,
        "trailing_pe": 72.50, "forward_pe": 58.20, "price_to_book": 16.40, "price_to_sales": 10.80,
        "trailing_eps": 5.28, "forward_eps": 6.58, "beta": 2.34,
        "fifty_two_week_high": 420.00, "fifty_two_week_low": 138.80,
        "total_revenue": 97650000000, "net_income": 12580000000,
        "gross_margins_pct": 18.20, "operating_margins_pct": 8.50, "profit_margins_pct": 12.88,
        "return_on_equity_pct": 21.40, "debt_to_equity": 11.20,
        "operating_cashflow": 14200000000, "free_cashflow": 7800000000,
        "revenue_growth_pct": 8.50, "earnings_growth_pct": 12.30,
        "target_mean_price": 340.00, "target_high_price": 500.00, "target_low_price": 120.00,
        "recommendation_key": "hold", "recommendation_display": "持有 (Hold)", "number_of_analysts": 45,
        "dividend_rate": 0.0, "dividend_yield_pct": 0.0, "ex_dividend_date": "暂无分红记录", "payout_ratio_pct": 0.0,
        "website": "https://www.tesla.com", "employees": 140000, "city": "Austin", "country": "United States",
        "summary": "特斯拉（Tesla, Inc.）主营智能电动汽车（Model 3/Y/CyberTruck）、FSD 全自动驾驶技术、Megapack 储能系统及人形机器人 Optimus。"
    },
    "MSFT": {
        "sector": "企业软件与云计算 (Technology)", "industry": "云端算力与生产力软件 (Software - Infrastructure)",
        "market_cap": 3980000000000, "enterprise_value": 3920000000000,
        "trailing_pe": 36.20, "forward_pe": 30.50, "price_to_book": 12.80, "price_to_sales": 13.90,
        "trailing_eps": 14.78, "forward_eps": 17.54, "beta": 1.12,
        "fifty_two_week_high": 550.00, "fifty_two_week_low": 385.00,
        "total_revenue": 245120000000, "net_income": 88140000000,
        "gross_margins_pct": 69.80, "operating_margins_pct": 44.60, "profit_margins_pct": 35.96,
        "return_on_equity_pct": 38.50, "debt_to_equity": 32.50,
        "operating_cashflow": 118000000000, "free_cashflow": 74000000000,
        "revenue_growth_pct": 15.20, "earnings_growth_pct": 18.40,
        "target_mean_price": 560.00, "target_high_price": 650.00, "target_low_price": 460.00,
        "recommendation_key": "strong_buy", "recommendation_display": "强力买入 (Strong Buy)", "number_of_analysts": 52,
        "dividend_rate": 3.32, "dividend_yield_pct": 0.62, "ex_dividend_date": "2026-08-20", "payout_ratio_pct": 24.50,
        "website": "https://www.microsoft.com", "employees": 228000, "city": "Redmond", "country": "United States",
        "summary": "微软（Microsoft Corporation）是全球最大的企业软件提供商与 Azure 公共云巨头，依托 OpenAI 深度赋能 Copilot 生态与企业智能。"
    },
    "SPY": {
        "sector": "大盘宽基指数 (ETF)", "industry": "标普500基准指数基金 (Broad Market ETF)",
        "market_cap": 612000000000, "enterprise_value": 612000000000,
        "trailing_pe": 26.80, "forward_pe": 22.40, "price_to_book": 4.85, "price_to_sales": 2.95,
        "trailing_eps": 29.05, "forward_eps": 34.75, "beta": 1.00,
        "fifty_two_week_high": 782.00, "fifty_two_week_low": 540.00,
        "total_revenue": 0, "net_income": 0,
        "gross_margins_pct": 0.0, "operating_margins_pct": 0.0, "profit_margins_pct": 0.0,
        "return_on_equity_pct": 19.80, "debt_to_equity": 0.0,
        "operating_cashflow": 0, "free_cashflow": 0,
        "revenue_growth_pct": 0.0, "earnings_growth_pct": 0.0,
        "target_mean_price": 820.00, "target_high_price": 880.00, "target_low_price": 720.00,
        "recommendation_key": "buy", "recommendation_display": "适度看多 (Benchmark Buy)", "number_of_analysts": 500,
        "dividend_rate": 7.12, "dividend_yield_pct": 1.18, "ex_dividend_date": "2026-09-18", "payout_ratio_pct": 98.0,
        "website": "https://www.ssga.com", "employees": 0, "city": "Boston", "country": "United States",
        "summary": "SPDR S&P 500 ETF Trust（代码：SPY）是全球规模最大、流动性最高的交易所交易基金，追踪标普500指数500家美国核心大型上市企业表现。"
    },
    "IAUM": {
        "sector": "贵金属与大宗商品 (ETF)", "industry": "物理实物黄金信托 (Physical Gold Trust)",
        "market_cap": 7949300736, "enterprise_value": 7949300736,
        "trailing_pe": None, "forward_pe": None, "price_to_book": None, "price_to_sales": None,
        "trailing_eps": None, "forward_eps": None, "beta": 0.12,
        "fifty_two_week_high": 55.27, "fifty_two_week_low": 39.02,
        "total_revenue": 0, "net_income": 0,
        "gross_margins_pct": 0.0, "operating_margins_pct": 0.0, "profit_margins_pct": 0.0,
        "return_on_equity_pct": 0.0, "debt_to_equity": 0.0,
        "operating_cashflow": 0, "free_cashflow": 0,
        "revenue_growth_pct": 0.0, "earnings_growth_pct": 0.0,
        "target_mean_price": 48.50, "target_high_price": 56.00, "target_low_price": 38.00,
        "recommendation_key": "buy", "recommendation_display": "防守避险 (Safe-Haven Buy)", "number_of_analysts": 25,
        "dividend_rate": 0.0, "dividend_yield_pct": 0.0, "ex_dividend_date": "暂无分红记录", "payout_ratio_pct": 0.0,
        "website": "https://www.ishares.com", "employees": 0, "city": "San Francisco", "country": "United States",
        "summary": "iShares Gold Trust Micro（代码：IAUM）是由贝莱德 BlackRock 发行的超低费率实物黄金信托ETF（管理费率仅0.09%），紧密跟踪国际现货黄金价格走势。"
    },
    "600519.SS": {
        "sector": "食品饮料与高端白酒 (Consumer Defensive)", "industry": "白酒酿造与高端消费品 (Distillers & Vintners)",
        "market_cap": 1586500000000, "enterprise_value": 1420000000000,
        "trailing_pe": 21.50, "forward_pe": 18.80, "price_to_book": 7.45, "price_to_sales": 10.20,
        "trailing_eps": 58.74, "forward_eps": 67.20, "beta": 0.65,
        "fifty_two_week_high": 1780.00, "fifty_two_week_low": 1205.00,
        "total_revenue": 147690000000, "net_income": 74730000000,
        "gross_margins_pct": 91.80, "operating_margins_pct": 68.50, "profit_margins_pct": 50.60,
        "return_on_equity_pct": 34.80, "debt_to_equity": 0.0,
        "operating_cashflow": 66500000000, "free_cashflow": 62000000000,
        "revenue_growth_pct": 15.80, "earnings_growth_pct": 18.20,
        "target_mean_price": 1850.00, "target_high_price": 2200.00, "target_low_price": 1500.00,
        "recommendation_key": "strong_buy", "recommendation_display": "强力买入 (Strong Buy)", "number_of_analysts": 48,
        "dividend_rate": 30.80, "dividend_yield_pct": 3.25, "ex_dividend_date": "2026-06-25", "payout_ratio_pct": 75.0,
        "website": "https://www.moutaichina.com", "employees": 32000, "city": "仁怀市 (Renhuai)", "country": "中国 (China)",
        "summary": "贵州茅台（600519.SS）是中国白酒第一龙头及A股市值标杆，主营飞天茅台等酱香型白酒，具备极高的品牌壁垒、强劲的自由现金流与极高毛利率。"
    },
    "0700.HK": {
        "sector": "互联网与数字科技 (Communication Services)", "industry": "社交平台、网络游戏与金融科技 (Interactive Media)",
        "market_cap": 4010000000000, "enterprise_value": 3850000000000,
        "trailing_pe": 22.50, "forward_pe": 18.40, "price_to_book": 4.10, "price_to_sales": 6.20,
        "trailing_eps": 18.90, "forward_eps": 23.10, "beta": 1.15,
        "fifty_two_week_high": 485.00, "fifty_two_week_low": 260.00,
        "total_revenue": 609000000000, "net_income": 157000000000,
        "gross_margins_pct": 53.20, "operating_margins_pct": 36.40, "profit_margins_pct": 25.78,
        "return_on_equity_pct": 21.50, "debt_to_equity": 36.20,
        "operating_cashflow": 220000000000, "free_cashflow": 168000000000,
        "revenue_growth_pct": 10.40, "earnings_growth_pct": 22.80,
        "target_mean_price": 485.00, "target_high_price": 560.00, "target_low_price": 390.00,
        "recommendation_key": "strong_buy", "recommendation_display": "强力买入 (Strong Buy)", "number_of_analysts": 55,
        "dividend_rate": 3.40, "dividend_yield_pct": 0.80, "ex_dividend_date": "2026-05-18", "payout_ratio_pct": 18.0,
        "website": "https://www.tencent.com", "employees": 105000, "city": "深圳 (Shenzhen)", "country": "中国香港 (Hong Kong)",
        "summary": "腾讯控股（0700.HK）是亚洲市值最大的综合互联网科技航母，拥有微信/QQ超级流量生态、全球顶尖数字娱乐与游戏自研体系、腾讯云与金融支付网络。"
    }
}

def fetch_stock_fundamentals(ticker: str = "AAPL") -> dict:
    """
    Retrieves complete institutional fundamentals, financials, valuation multiples,
    Wall Street analyst target consensus, and dividend schedule.
    Features 10-minute cache and multi-layered fallback for 100% availability.
    """
    ticker = sanitize_ticker(ticker)
    sym_upper = ticker.upper()
    now = datetime.now()

    # Check Memory Cache
    if sym_upper in FUNDAMENTALS_CACHE:
        cached_time, cached_data = FUNDAMENTALS_CACHE[sym_upper]
        if (now - cached_time).total_seconds() < 600:
            return cached_data

    # Load baseline metadata & fallback profile
    meta = get_ticker_metadata(sym_upper)
    fb = PRESET_FUNDAMENTALS_FALLBACK.get(sym_upper, {})

    curr_p = 0.0
    prev_close = 0.0
    day_high = 0.0
    day_low = 0.0
    vol = 0
    mkt_cap = fb.get("market_cap", 0)

    # First attempt real-time quote for live price
    quote = fetch_realtime_quote(sym_upper)
    if quote.get("status") == "success":
        curr_p = float(quote.get("price", 0.0))
        prev_close = float(quote.get("prev_close", 0.0))
        day_high = float(quote.get("high", 0.0))
        day_low = float(quote.get("low", 0.0))
        vol = int(quote.get("volume", 0))

    info = {}
    try:
        t = yf.Ticker(sym_upper)
        info = getattr(t, 'info', {}) or {}
        fast = getattr(t, 'fast_info', None)
        if curr_p <= 0 and fast:
            curr_p = float(getattr(fast, 'last_price', 0.0) or 0.0)
            prev_close = float(getattr(fast, 'previous_close', 0.0) or 0.0)
    except Exception as e:
        logger.warning(f"yfinance info query fallback for {sym_upper}: {e}")

    # Fallback to local historical data if price still 0
    if curr_p <= 0:
        hist_df = fetch_stock_data(sym_upper, "1y", use_cache=True)
        if not hist_df.empty:
            curr_p = float(hist_df['Close'].iloc[-1])
            prev_close = float(hist_df['Close'].iloc[-2]) if len(hist_df) > 1 else curr_p
            day_high = float(hist_df['High'].iloc[-1])
            day_low = float(hist_df['Low'].iloc[-1])
            vol = int(hist_df['Volume'].iloc[-1])

    # Price dynamics
    chg = round(curr_p - prev_close, 2)
    chg_pct = round((chg / prev_close) * 100, 2) if prev_close > 0 else 0.0

    # Sector & Profile
    sector = info.get("sector") or fb.get("sector") or "综合行业 (Diversified)"
    industry = info.get("industry") or fb.get("industry") or meta.get("type", "Equity")
    country = info.get("country") or fb.get("country") or "United States"
    city = info.get("city") or fb.get("city") or "N/A"
    website = info.get("website") or fb.get("website") or ""
    employees = int(info.get("fullTimeEmployees") or fb.get("employees") or 0)
    summary = info.get("longBusinessSummary") or fb.get("summary") or f"{meta.get('name', sym_upper)} 是该领域的代表性上市企业。"

    # Valuation
    mkt_cap = info.get("marketCap") or fb.get("market_cap") or (curr_p * (info.get("sharesOutstanding") or 1e9))
    ent_val = info.get("enterpriseValue") or fb.get("enterprise_value") or mkt_cap
    trailing_pe = info.get("trailingPE") or fb.get("trailing_pe")
    forward_pe = info.get("forwardPE") or fb.get("forward_pe")
    pb = info.get("priceToBook") or fb.get("price_to_book")
    ps = info.get("priceToSalesTrailing12Months") or fb.get("price_to_sales")
    trailing_eps = info.get("trailingEps") or fb.get("trailing_eps")
    forward_eps = info.get("forwardEps") or fb.get("forward_eps")
    beta = info.get("beta") or fb.get("beta") or 1.0
    h_52 = info.get("fiftyTwoWeekHigh") or fb.get("fifty_two_week_high") or (curr_p * 1.15)
    l_52 = info.get("fiftyTwoWeekLow") or fb.get("fifty_two_week_low") or (curr_p * 0.85)

    pos_52 = 50.0
    if h_52 and l_52 and h_52 > l_52:
        pos_52 = round(max(0.0, min(100.0, ((curr_p - l_52) / (h_52 - l_52)) * 100)), 1)

    # Financials
    rev = info.get("totalRevenue") or fb.get("total_revenue")
    net_inc = info.get("netIncomeToCommon") or fb.get("net_income")
    gross_m = info.get("grossMargins")
    gross_m_pct = round(gross_m * 100, 2) if gross_m is not None else fb.get("gross_margins_pct", 0.0)
    op_m = info.get("operatingMargins")
    op_m_pct = round(op_m * 100, 2) if op_m is not None else fb.get("operating_margins_pct", 0.0)
    prof_m = info.get("profitMargins")
    prof_m_pct = round(prof_m * 100, 2) if prof_m is not None else fb.get("profit_margins_pct", 0.0)
    roe = info.get("returnOnEquity")
    roe_pct = round(roe * 100, 2) if roe is not None else fb.get("return_on_equity_pct", 0.0)
    debt_eq = info.get("debtToEquity") or fb.get("debt_to_equity")
    op_cf = info.get("operatingCashflow") or fb.get("operating_cashflow")
    f_cf = info.get("freeCashflow") or fb.get("free_cashflow")
    rev_growth = info.get("revenueGrowth")
    rev_growth_pct = round(rev_growth * 100, 2) if rev_growth is not None else fb.get("revenue_growth_pct", 0.0)
    earn_growth = info.get("earningsGrowth")
    earn_growth_pct = round(earn_growth * 100, 2) if earn_growth is not None else fb.get("earnings_growth_pct", 0.0)

    # Analyst consensus & Target Price
    target_mean = float(info.get("targetMeanPrice") or fb.get("target_mean_price") or 0.0)
    target_high = float(info.get("targetHighPrice") or fb.get("target_high_price") or 0.0)
    target_low = float(info.get("targetLowPrice") or fb.get("target_low_price") or 0.0)
    target_med = float(info.get("targetMedianPrice") or target_mean)

    upside_pct = round(((target_mean - curr_p) / curr_p) * 100, 2) if (curr_p > 0 and target_mean > 0) else 0.0
    rec_key = info.get("recommendationKey") or fb.get("recommendation_key") or "hold"
    rec_display_map = {
        "strong_buy": "强力买入 (Strong Buy)",
        "buy": "买入 (Buy)",
        "hold": "持有 / 中性 (Hold)",
        "underperform": "减持 (Underperform)",
        "sell": "卖出 (Sell)"
    }
    rec_display = rec_display_map.get(rec_key.lower(), fb.get("recommendation_display", "中性配置"))
    analysts_count = int(info.get("numberOfAnalystOpinions") or fb.get("number_of_analysts") or 0)

    # Dividends
    div_rate = float(info.get("dividendRate") or fb.get("dividend_rate") or 0.0)
    div_yield = info.get("dividendYield")
    if div_yield is not None:
        div_yield = float(div_yield)
        # If given as small decimal like 0.0032, convert to percent; if already 0.32, keep as 0.32
        if div_rate > 0 and curr_p > 0:
            calc_yield = (div_rate / curr_p) * 100
            div_yield_pct = round(calc_yield, 2)
        elif div_yield < 0.05 and div_yield > 0:
            div_yield_pct = round(div_yield * 100, 2)
        else:
            div_yield_pct = round(div_yield, 2)
    elif div_rate > 0 and curr_p > 0:
        div_yield_pct = round((div_rate / curr_p) * 100, 2)
    else:
        div_yield_pct = fb.get("dividend_yield_pct", 0.0)

    payout_r = info.get("payoutRatio")
    payout_pct = round(float(payout_r) * 100, 2) if (payout_r is not None and float(payout_r) < 1.0) else (round(float(payout_r), 2) if payout_r is not None else fb.get("payout_ratio_pct", 0.0))

    ex_ts = info.get("exDividendDate")
    if ex_ts:
        try:
            ex_date_str = datetime.fromtimestamp(ex_ts).strftime("%Y-%m-%d")
        except Exception:
            ex_date_str = fb.get("ex_dividend_date", "暂无分红记录")
    else:
        ex_date_str = fb.get("ex_dividend_date", "暂无分红记录")

    currency_sym = "¥" if meta.get("currency") == "CNY" else ("HK$" if meta.get("currency") == "HKD" else "$")

    result = {
        "status": "success",
        "ticker": sym_upper,
        "currency": meta.get("currency", "USD"),
        "currency_symbol": currency_sym,
        "profile": {
            "symbol": sym_upper,
            "name": meta.get("name", sym_upper),
            "exchange": meta.get("exchange", ""),
            "currency": meta.get("currency", "USD"),
            "sector": sector,
            "industry": industry,
            "quote_type": meta.get("type", "Equity"),
            "country": country,
            "city": city,
            "website": website,
            "employees": employees,
            "summary": summary
        },
        "price_overview": {
            "current_price": round(curr_p, 2),
            "prev_close": round(prev_close, 2),
            "change": chg,
            "change_pct": chg_pct,
            "day_high": round(day_high, 2),
            "day_low": round(day_low, 2),
            "volume": vol,
            "market_cap": mkt_cap,
            "market_cap_fmt": format_metric_currency(mkt_cap, currency_sym),
            "enterprise_value": ent_val,
            "enterprise_value_fmt": format_metric_currency(ent_val, currency_sym)
        },
        "valuation": {
            "trailing_pe": round(float(trailing_pe), 2) if trailing_pe else None,
            "forward_pe": round(float(forward_pe), 2) if forward_pe else None,
            "price_to_book": round(float(pb), 2) if pb else None,
            "price_to_sales": round(float(ps), 2) if ps else None,
            "trailing_eps": round(float(trailing_eps), 2) if trailing_eps else None,
            "forward_eps": round(float(forward_eps), 2) if forward_eps else None,
            "beta": round(float(beta), 2) if beta else 1.0,
            "fifty_two_week_high": round(float(h_52), 2) if h_52 else round(curr_p * 1.15, 2),
            "fifty_two_week_low": round(float(l_52), 2) if l_52 else round(curr_p * 0.85, 2),
            "range_52w_position_pct": pos_52
        },
        "financials": {
            "total_revenue": rev,
            "revenue_fmt": format_metric_currency(rev, currency_sym),
            "net_income": net_inc,
            "net_income_fmt": format_metric_currency(net_inc, currency_sym),
            "gross_margins_pct": gross_m_pct,
            "operating_margins_pct": op_m_pct,
            "profit_margins_pct": prof_m_pct,
            "return_on_equity_pct": roe_pct,
            "debt_to_equity": round(float(debt_eq), 2) if debt_eq else None,
            "operating_cashflow_fmt": format_metric_currency(op_cf, currency_sym),
            "free_cashflow_fmt": format_metric_currency(f_cf, currency_sym),
            "revenue_growth_pct": rev_growth_pct,
            "earnings_growth_pct": earn_growth_pct
        },
        "analyst": {
            "target_mean_price": round(target_mean, 2) if target_mean > 0 else None,
            "target_high_price": round(target_high, 2) if target_high > 0 else None,
            "target_low_price": round(target_low, 2) if target_low > 0 else None,
            "target_median_price": round(target_med, 2) if target_med > 0 else None,
            "upside_potential_pct": upside_pct,
            "recommendation_key": rec_key,
            "recommendation_display": rec_display,
            "number_of_analysts": analysts_count
        },
        "dividends": {
            "dividend_rate": round(div_rate, 2),
            "dividend_yield_pct": div_yield_pct,
            "ex_dividend_date": ex_date_str,
            "payout_ratio_pct": payout_pct
        }
    }

    FUNDAMENTALS_CACHE[sym_upper] = (now, result)
    return result

def get_screener_catalog(category: str = "all") -> list:
    """
    Returns curated, multi-market stock universe for Step 1 选股大厅 (Screener).
    Supports category filtering: 'all', 'us_tech', 'etf_gold', 'china_hk', 'a_shares', 'high_dividend'.
    """
    catalog = [
        # US Tech & AI Leaders
        {"symbol": "NVDA", "name": "NVIDIA Corporation (英伟达)", "category": "us_tech", "category_label": "美股科技与AI", "sector": "半导体 / AI计算", "price": 229.28, "change_pct": -0.52, "market_cap_fmt": "$5.54T", "pe": 28.99, "analyst_rating": "强力买入", "target_upside_pct": 43.37, "div_yield_pct": 0.44, "badge": "AI总龙头"},
        {"symbol": "AAPL", "name": "Apple Inc. (苹果公司)", "category": "us_tech", "category_label": "美股科技与AI", "sector": "消费电子 / 生态", "price": 336.64, "change_pct": -1.11, "market_cap_fmt": "$4.91T", "pe": 38.61, "analyst_rating": "买入", "target_upside_pct": -2.54, "div_yield_pct": 0.32, "badge": "消费电子标杆"},
        {"symbol": "MSFT", "name": "Microsoft Corp. (微软)", "category": "us_tech", "category_label": "美股科技与AI", "sector": "云计算 / 企服", "price": 535.07, "change_pct": 2.38, "market_cap_fmt": "$3.98T", "pe": 36.20, "analyst_rating": "强力买入", "target_upside_pct": 4.66, "div_yield_pct": 0.62, "badge": "企业云软件"},
        {"symbol": "TSLA", "name": "Tesla, Inc. (特斯拉)", "category": "us_tech", "category_label": "美股科技与AI", "sector": "新能源车 / 自动驾驶", "price": 382.70, "change_pct": 2.05, "market_cap_fmt": "$1.21T", "pe": 72.50, "analyst_rating": "持有", "target_upside_pct": -11.16, "div_yield_pct": 0.0, "badge": "高波动进攻"},
        {"symbol": "AMZN", "name": "Amazon.com, Inc. (亚马逊)", "category": "us_tech", "category_label": "美股科技与AI", "sector": "电商 / AWS云", "price": 262.43, "change_pct": -0.45, "market_cap_fmt": "$2.72T", "pe": 44.10, "analyst_rating": "强力买入", "target_upside_pct": -0.93, "div_yield_pct": 0.0, "badge": "电商与算力"},
        {"symbol": "GOOGL", "name": "Alphabet Inc. (谷歌)", "category": "us_tech", "category_label": "美股科技与AI", "sector": "搜索广告 / 模型", "price": 351.66, "change_pct": 1.12, "market_cap_fmt": "$4.30T", "pe": 26.40, "analyst_rating": "买入", "target_upside_pct": -33.17, "div_yield_pct": 0.45, "badge": "搜索与AI底层"},
        {"symbol": "META", "name": "Meta Platforms (元宇宙)", "category": "us_tech", "category_label": "美股科技与AI", "sector": "社交媒体 / 广告", "price": 718.67, "change_pct": 1.65, "market_cap_fmt": "$1.82T", "pe": 28.50, "analyst_rating": "买入", "target_upside_pct": -5.38, "div_yield_pct": 0.35, "badge": "社交广告现金牛"},
        {"symbol": "PLTR", "name": "Palantir Tech (大数据AI)", "category": "us_tech", "category_label": "美股科技与AI", "sector": "国防军工 / 企业AI", "price": 209.05, "change_pct": 3.45, "market_cap_fmt": "$185.0B", "pe": 115.0, "analyst_rating": "持有", "target_upside_pct": -33.03, "div_yield_pct": 0.0, "badge": "AI企业平台"},
        {"symbol": "AMD", "name": "Advanced Micro Devices", "category": "us_tech", "category_label": "美股科技与AI", "sector": "CPU/GPU芯片", "price": 608.10, "change_pct": -1.80, "market_cap_fmt": "$295.0B", "pe": 48.20, "analyst_rating": "买入", "target_upside_pct": -70.40, "div_yield_pct": 0.0, "badge": "芯片第二梯队"},
        {"symbol": "TSM", "name": "Taiwan Semiconductor (台积电)", "category": "us_tech", "category_label": "美股科技与AI", "sector": "晶圆代工制造", "price": 453.31, "change_pct": 1.95, "market_cap_fmt": "$1.15T", "pe": 28.50, "analyst_rating": "强力买入", "target_upside_pct": -45.95, "div_yield_pct": 1.25, "badge": "先进制程垄断"},

        # Global ETFs, Broad Market & Gold
        {"symbol": "SPY", "name": "SPDR S&P 500 ETF (标普500)", "category": "etf_gold", "category_label": "全球ETF与黄金", "sector": "全美大盘宽基", "price": 778.57, "change_pct": 0.32, "market_cap_fmt": "$612.0B", "pe": 26.80, "analyst_rating": "适度看多", "target_upside_pct": 5.32, "div_yield_pct": 1.18, "badge": "美股基准核心"},
        {"symbol": "QQQ", "name": "Invesco QQQ (纳斯达克100)", "category": "etf_gold", "category_label": "全球ETF与黄金", "sector": "纳指成长科技", "price": 751.27, "change_pct": 0.45, "market_cap_fmt": "$310.0B", "pe": 32.40, "analyst_rating": "适度看多", "target_upside_pct": 6.45, "div_yield_pct": 0.58, "badge": "成长科技核心"},
        {"symbol": "GLD", "name": "SPDR Gold Shares (黄金ETF)", "category": "etf_gold", "category_label": "全球ETF与黄金", "sector": "大宗贵金属避险", "price": 384.58, "change_pct": 0.65, "market_cap_fmt": "$78.0B", "pe": None, "analyst_rating": "看多避险", "target_upside_pct": 10.20, "div_yield_pct": 0.0, "badge": "硬通货大宗"},
        {"symbol": "IAUM", "name": "iShares Gold Trust Micro", "category": "etf_gold", "category_label": "全球ETF与黄金", "sector": "超低费率实物黄金", "price": 41.81, "change_pct": 1.28, "market_cap_fmt": "$7.95B", "pe": None, "analyst_rating": "看多避险", "target_upside_pct": 15.98, "div_yield_pct": 0.0, "badge": "低费率黄金首选"},
        {"symbol": "IWM", "name": "iShares Russell 2000 ETF", "category": "etf_gold", "category_label": "全球ETF与黄金", "sector": "美股中小盘成长", "price": 245.00, "change_pct": 0.85, "market_cap_fmt": "$72.0B", "pe": 22.10, "analyst_rating": "中性持有", "target_upside_pct": 7.20, "div_yield_pct": 1.35, "badge": "中小盘成长"},
        {"symbol": "TLT", "name": "iShares 20+ Year Treasury", "category": "etf_gold", "category_label": "全球ETF与黄金", "sector": "美国长期国债", "price": 96.50, "change_pct": -0.42, "market_cap_fmt": "$58.0B", "pe": None, "analyst_rating": "利率敏感", "target_upside_pct": 8.50, "div_yield_pct": 3.85, "badge": "长久期避险债券"},

        # China HK & Concept Leaders
        {"symbol": "0700.HK", "name": "腾讯控股 (社交网络龙头)", "category": "china_hk", "category_label": "港股与中概龙头", "sector": "社交娱乐 / 游戏", "price": 425.20, "change_pct": 1.48, "market_cap_fmt": "HK$4.01T", "pe": 22.50, "analyst_rating": "强力买入", "target_upside_pct": 14.06, "div_yield_pct": 0.80, "badge": "互联网现金流之王"},
        {"symbol": "9988.HK", "name": "阿里巴巴 (电商与阿里云)", "category": "china_hk", "category_label": "港股与中概龙头", "sector": "核心商业 / 云计算", "price": 88.50, "change_pct": 0.91, "market_cap_fmt": "$240.0B", "pe": 14.80, "analyst_rating": "买入", "target_upside_pct": 41.24, "div_yield_pct": 1.85, "badge": "低估值云转型"},
        {"symbol": "3690.HK", "name": "美团 (本地生活服务龙头)", "category": "china_hk", "category_label": "港股与中概龙头", "sector": "本地生活 / 外卖", "price": 125.40, "change_pct": 2.12, "market_cap_fmt": "HK$780.0B", "pe": 26.00, "analyst_rating": "买入", "target_upside_pct": 23.60, "div_yield_pct": 0.0, "badge": "本地消费生态"},
        {"symbol": "1810.HK", "name": "小米集团 (消费电子与智能车)", "category": "china_hk", "category_label": "港股与中概龙头", "sector": "智能硬件 / 新能源汽车", "price": 18.20, "change_pct": 1.11, "market_cap_fmt": "HK$460.0B", "pe": 24.50, "analyst_rating": "买入", "target_upside_pct": 31.87, "div_yield_pct": 0.0, "badge": "人车家全生态"},
        {"symbol": "PDD", "name": "拼多多 (PDD Holdings ADR)", "category": "china_hk", "category_label": "港股与中概龙头", "sector": "国内电商 / Temu出海", "price": 118.50, "change_pct": 2.85, "market_cap_fmt": "$160.0B", "pe": 11.80, "analyst_rating": "强力买入", "target_upside_pct": 39.24, "div_yield_pct": 0.0, "badge": "全球出海爆发"},
        {"symbol": "JD", "name": "京东集团 (JD.com ADR)", "category": "china_hk", "category_label": "港股与中概龙头", "sector": "自营电商 / 仓储物流", "price": 35.80, "change_pct": 1.25, "market_cap_fmt": "$45.0B", "pe": 10.50, "analyst_rating": "买入", "target_upside_pct": 17.32, "div_yield_pct": 2.65, "badge": "自营供应链"},

        # A-Share Core Industry Leaders
        {"symbol": "600519.SS", "name": "贵州茅台 (白酒第一龙头)", "category": "a_shares", "category_label": "A股核心资产", "sector": "高端消费 / 酱香白酒", "price": 1263.00, "change_pct": 0.64, "market_cap_fmt": "¥1.59T", "pe": 21.50, "analyst_rating": "强力买入", "target_upside_pct": 46.48, "div_yield_pct": 3.25, "badge": "A股市值定海神针"},
        {"symbol": "300750.SZ", "name": "宁德时代 (动力电池与储能)", "category": "a_shares", "category_label": "A股核心资产", "sector": "电池能源 / 储能系统", "price": 245.50, "change_pct": 1.82, "market_cap_fmt": "¥1.08T", "pe": 19.80, "analyst_rating": "强力买入", "target_upside_pct": 30.35, "div_yield_pct": 1.65, "badge": "全球电池一哥"},
        {"symbol": "002594.SZ", "name": "比亚迪 (新能源汽车制造)", "category": "a_shares", "category_label": "A股核心资产", "sector": "整车制造 / 垂直整合", "price": 285.20, "change_pct": 1.15, "market_cap_fmt": "¥830.0B", "pe": 21.20, "analyst_rating": "强力买入", "target_upside_pct": 26.23, "div_yield_pct": 1.10, "badge": "电车销冠龙头"},
        {"symbol": "601318.SS", "name": "中国平安 (金融保险综合龙头)", "category": "a_shares", "category_label": "A股核心资产", "sector": "寿险财险 / 资产管理", "price": 52.80, "change_pct": 0.58, "market_cap_fmt": "¥960.0B", "pe": 8.50, "analyst_rating": "买入", "target_upside_pct": 28.79, "div_yield_pct": 5.20, "badge": "综合金融巨头"},
        {"symbol": "600036.SS", "name": "招商银行 (零售银行业标杆)", "category": "a_shares", "category_label": "A股核心资产", "sector": "商业银行 / 财富管理", "price": 38.60, "change_pct": 0.26, "market_cap_fmt": "¥970.0B", "pe": 6.80, "analyst_rating": "买入", "target_upside_pct": 19.17, "div_yield_pct": 5.60, "badge": "零售之王"},
        {"symbol": "300059.SZ", "name": "东方财富 (互联网券商龙头)", "category": "a_shares", "category_label": "A股核心资产", "sector": "互联网金融 / 证券", "price": 21.80, "change_pct": 1.45, "market_cap_fmt": "¥340.0B", "pe": 32.00, "analyst_rating": "买入", "target_upside_pct": 28.44, "div_yield_pct": 0.45, "badge": "牛市旗手"},
        {"symbol": "688981.SS", "name": "中芯国际 (晶圆制造龙头)", "category": "a_shares", "category_label": "A股核心资产", "sector": "集成电路 / 芯片制造", "price": 95.60, "change_pct": 2.15, "market_cap_fmt": "¥380.0B", "pe": 65.00, "analyst_rating": "持有", "target_upside_pct": 20.29, "div_yield_pct": 0.0, "badge": "自主可控核心"},
        {"symbol": "510300.SS", "name": "华泰柏瑞沪深300 ETF", "category": "a_shares", "category_label": "A股核心资产", "sector": "A股核心大盘宽基", "price": 4.39, "change_pct": 0.05, "market_cap_fmt": "¥320.0B", "pe": 12.80, "analyst_rating": "基准买入", "target_upside_pct": 12.50, "div_yield_pct": 2.45, "badge": "A股核心基准"},

        # High Dividend Value
        {"symbol": "XOM", "name": "Exxon Mobil Corp. (埃克森美孚)", "category": "high_dividend", "category_label": "高股息与稳健价值", "sector": "石油天然气 / 传统能源", "price": 122.40, "change_pct": 0.45, "market_cap_fmt": "$480.0B", "pe": 13.50, "analyst_rating": "买入", "target_upside_pct": 14.38, "div_yield_pct": 3.42, "badge": "传统能源分红牛"},
        {"symbol": "JNJ", "name": "Johnson & Johnson (强生公司)", "category": "high_dividend", "category_label": "高股息与稳健价值", "sector": "制药 / 医疗器械", "price": 162.50, "change_pct": -0.15, "market_cap_fmt": "$385.0B", "pe": 22.00, "analyst_rating": "持有", "target_upside_pct": 10.77, "div_yield_pct": 3.12, "badge": "医疗防御贵族"},
        {"symbol": "KO", "name": "Coca-Cola Co. (可口可乐)", "category": "high_dividend", "category_label": "高股息与稳健价值", "sector": "非酒精饮料 / 软饮", "price": 68.20, "change_pct": 0.35, "market_cap_fmt": "$285.0B", "pe": 24.50, "analyst_rating": "买入", "target_upside_pct": 12.90, "div_yield_pct": 2.95, "badge": "股神长期重仓"}
    ]

    if category and category != "all":
        return [item for item in catalog if item["category"] == category]
    return catalog



