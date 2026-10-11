import os
import re
import json
import logging
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
    "GLD": "SPDR Gold Shares ETF"
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
    {"symbol": "ASX", "name": "ASE Technology Holding Co., Ltd. (日月光)", "exchange": "NYSE", "price": 46.43, "change_pct": 2.04, "type": "Equity"}
]

def search_yahoo_tickers(query: str, max_results: int = 5):
    """
    Search Yahoo Finance and Local Institutional Catalog for matching tickers.
    Supports A-Share (e.g. 600519.SS, 510300.SS, 茅台, 比亚迪), HK Stocks, and US Tickers.
    Retrieves latest price and percentage change with sub-second hybrid performance.
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
    # Check if clean_q is 6-digit A-share code directly (e.g. 600519 -> 600519.SS)
    if not primary_sym and len(clean_q) == 6 and clean_q.isdigit():
        primary_sym = sanitize_ticker(clean_q)

    search_term = primary_sym if primary_sym else clean_q

    cache_key = (search_term.lower(), max_results)
    now = datetime.now()
    if cache_key in SEARCH_CACHE:
        cached_t, cached_data = SEARCH_CACHE[cache_key]
        if (now - cached_t).total_seconds() < 90:
            return cached_data

    # 3. Local catalog fast resolution (instant sub-millisecond response)
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

    # If local matches found and sufficient, enrich prices and return immediately
    if local_matches:
        def enrich_price(item):
            sym = item['symbol'].upper()
            if sym in PRICE_CACHE:
                cached_time, c_price, c_chg = PRICE_CACHE[sym]
                if (now - cached_time).total_seconds() < 300:
                    item['price'] = c_price
                    item['change_pct'] = c_chg
                    return item
            try:
                t = yf.Ticker(sym)
                fi = t.fast_info
                last = getattr(fi, 'last_price', None)
                prev = getattr(fi, 'previous_close', None)
                if last is not None and not np.isnan(last):
                    item['price'] = round(float(last), 2)
                    if prev is not None and not np.isnan(prev) and prev > 0:
                        item['change_pct'] = round(((float(last) - float(prev)) / float(prev)) * 100.0, 2)
                    PRICE_CACHE[sym] = (now, item['price'], item.get('change_pct', 0.0))
            except Exception:
                pass
            return item

        with ThreadPoolExecutor(max_workers=min(4, len(local_matches))) as executor:
            futures = [executor.submit(enrich_price, m) for m in local_matches[:max_results]]
            results = []
            for f in futures:
                try:
                    res_item = f.result(timeout=1.2)
                    results.append(res_item)
                except Exception:
                    pass

        if results:
            SEARCH_CACHE[cache_key] = (now, results)
            return results

    # 4. Fallback to external yfinance Search for uncatalogued symbols
    results = []
    try:
        s = yf.Search(search_term, max_results=max(8, max_results * 2))
        raw_quotes = getattr(s, 'quotes', []) or []

        filtered_quotes = []
        for q in raw_quotes:
            sym = q.get('symbol', '').upper()
            if not sym or (len(sym) > 8 and any(c.isdigit() for c in sym) and not sym.startswith('^') and not ('.SS' in sym or '.SZ' in sym or '.HK' in sym)):
                continue
            filtered_quotes.append(q)

        if primary_sym and not any(q.get('symbol', '').upper() == primary_sym for q in filtered_quotes):
            filtered_quotes.insert(0, {
                'symbol': primary_sym,
                'shortname': COMPANY_NAME_LOOKUP.get(primary_sym, primary_sym),
                'exchDisp': 'SSE' if primary_sym.endswith('.SS') else ('SZSE' if primary_sym.endswith('.SZ') else 'NYSE'),
                'typeDisp': 'ETF' if ('51' in primary_sym or '15' in primary_sym or '58' in primary_sym) else 'Equity'
            })

        quotes_to_fetch = filtered_quotes[:max_results]

        def fetch_single_quote(q_item):
            sym = q_item.get('symbol', '').upper()
            price, chg_pct = None, None
            if sym in PRICE_CACHE:
                cached_time, c_price, c_chg = PRICE_CACHE[sym]
                if (now - cached_time).total_seconds() < 300:
                    return {
                        "symbol": sym,
                        "name": q_item.get('shortname') or q_item.get('longname') or sym,
                        "exchange": q_item.get('exchDisp') or q_item.get('exchange') or '',
                        "type": q_item.get('typeDisp') or q_item.get('quoteType') or 'Stock',
                        "price": c_price,
                        "change_pct": c_chg
                    }

            fb = next((item for item in FALLBACK_STOCKS if item["symbol"].upper() == sym), None)
            try:
                t = yf.Ticker(sym)
                fi = t.fast_info
                last = getattr(fi, 'last_price', None)
                prev = getattr(fi, 'previous_close', None)
                if last is not None and not np.isnan(last):
                    price = round(float(last), 2)
                    if prev is not None and not np.isnan(prev) and prev > 0:
                        chg_pct = round(((float(last) - float(prev)) / float(prev)) * 100.0, 2)
                elif fb:
                    price = fb.get("price")
                    chg_pct = fb.get("change_pct")
            except Exception:
                if fb:
                    price = fb.get("price")
                    chg_pct = fb.get("change_pct")

            if price is not None:
                PRICE_CACHE[sym] = (now, price, chg_pct or 0.0)

            return {
                "symbol": sym,
                "name": q_item.get('shortname') or q_item.get('longname') or (fb.get('name') if fb else sym),
                "exchange": q_item.get('exchDisp') or q_item.get('exchange') or (fb.get('exchange') if fb else ''),
                "type": q_item.get('typeDisp') or q_item.get('quoteType') or 'Stock',
                "price": price or (fb.get('price') if fb else 100.0),
                "change_pct": chg_pct if chg_pct is not None else (fb.get('change_pct', 0.0) if fb else 0.0)
            }

        with ThreadPoolExecutor(max_workers=min(5, max(1, len(quotes_to_fetch)))) as executor:
            futures = [executor.submit(fetch_single_quote, q) for q in quotes_to_fetch]
            for f in futures:
                try:
                    res_item = f.result(timeout=1.5)
                    results.append(res_item)
                except Exception:
                    pass

    except Exception as e:
        logger.warning(f"Error querying yf.Search for '{query}': {e}. Using local fallback search.")

    # 5. Last resort fallback
    if not results and local_matches:
        results = local_matches[:max_results]

    SEARCH_CACHE[cache_key] = (now, results)
    return results

def fetch_realtime_quote(ticker: str = "AAPL") -> dict:
    """
    Grabs real-time market quote directly from finance.yahoo.com via yfinance.
    Returns dictionary with latest price, prev_close, change, change_pct, open, high, low, volume.
    """
    ticker = sanitize_ticker(ticker)
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

        return {
            "status": "success",
            "source": "finance.yahoo.com",
            "ticker": ticker,
            "price": round(last_price, 2),
            "prev_close": round(prev_close, 2),
            "open": round(open_price, 2),
            "high": round(day_high, 2),
            "low": round(day_low, 2),
            "volume": volume,
            "change": chg,
            "change_pct": chg_pct,
            "currency": getattr(fi, 'currency', 'USD'),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error fetching quote from finance.yahoo.com for {ticker}: {e}")
        return {"status": "error", "message": str(e), "ticker": ticker}


