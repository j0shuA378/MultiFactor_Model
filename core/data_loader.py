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
    # ASE Technology Holding
    "日月光": "ASX",
    "日月光投控": "ASX",
    "日月光半导体": "ASX",
    "ase technology": "ASX",
    "ase technology holding": "ASX",
    "ase technology holding co": "ASX",
    "ase technology holding co., ltd.": "ASX",
    "ase technology holding co., ltd": "ASX",
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
    "goldman sachs": "GS",
    "gs": "GS",
    # Morgan Stanley
    "摩根士丹利": "MS",
    "大摩": "MS",
    "morgan stanley": "MS",
    "ms": "MS",
    # JPMorgan Chase
    "摩根大通": "JPM",
    "小摩": "JPM",
    "jpmorgan": "JPM",
    "jpm": "JPM",
    # Alibaba
    "阿里巴巴": "BABA",
    "阿里": "BABA",
    "alibaba": "BABA",
    "baba": "BABA",
    # Tencent
    "腾讯": "TCEHY",
    "腾讯控股": "TCEHY",
    "tencent": "TCEHY",
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
    "qqq": "QQQ"
}

COMPANY_NAME_LOOKUP = {
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
    "QQQ": "Invesco QQQ Trust"
}

def sanitize_ticker(raw_ticker: str) -> str:
    """
    Cleans raw ticker input or company query string.
    Supports:
    - Symbols enclosed in brackets: 'ASE Technology Holding Co., Ltd. (ASX）' -> 'ASX'
    - Chinese/English company aliases: '日月光' -> 'ASX', '高盛' -> 'GS'
    - IME pinyin apostrophes: "a's'x" -> 'ASX'
    """
    if not raw_ticker:
        return "AAPL"
    s = str(raw_ticker).strip()

    # 1. Check if symbol is enclosed in parentheses/brackets () （） [] 【】
    m = re.search(r'[\(（\[【]([A-Za-z0-9\.\-\^]+)[\)）\]】]', s)
    if m:
        return m.group(1).upper().strip()

    # 2. Check alias map after removing IME apostrophes
    s_clean = s.replace("'", "").replace("’", "").strip().lower()
    if s_clean in COMPANY_ALIAS_MAP:
        return COMPANY_ALIAS_MAP[s_clean]
    for ch_name, sym in COMPANY_ALIAS_MAP.items():
        if ch_name in s_clean:
            return sym

    # 3. Strip special punctuation and return uppercase
    cleaned = re.sub(r'[\s\'’",\(\)（）]', '', s).upper()
    return cleaned if cleaned else "AAPL"

def ensure_cache_dir():
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR, exist_ok=True)

def generate_synthetic_data(ticker: str, days: int = 500) -> pd.DataFrame:
    """Generates realistic synthetic stock data when external API is unreachable"""
    np.random.seed(abs(hash(ticker)) % (2**32))
    end_date = datetime.now()
    dates = pd.date_range(end=end_date, periods=days, freq='B')
    
    # Base parameters tailored to ticker symbol
    base_price = 150.0
    if ticker in ["AAPL", "AMZN", "GOOGL"]:
        base_price = 180.0
    elif ticker in ["NVDA", "TSLA"]:
        base_price = 220.0
    elif ticker in ["SPY", "QQQ"]:
        base_price = 450.0
    elif ticker == "MSFT":
        base_price = 400.0
    elif ticker == "ASX":
        base_price = 46.5
    elif ticker == "TSM":
        base_price = 190.0
    elif ticker == "GS":
        base_price = 512.0

    # Geometric Brownian Motion simulation
    dt = 1 / 252
    mu = 0.15 # annual drift
    sigma = 0.28 # annual volatility
    
    returns = np.random.normal((mu - 0.5 * sigma**2) * dt, sigma * np.sqrt(dt), size=len(dates))
    price_series = base_price * np.exp(np.cumsum(returns))
    
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
            df = raw_df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
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
    {"symbol": "ASX", "name": "ASE Technology Holding Co., Ltd.", "exchange": "NYSE", "price": 46.43, "change_pct": 2.04, "type": "Equity"},
    {"symbol": "AAPL", "name": "Apple Inc.", "exchange": "NASDAQ", "price": 336.64, "change_pct": -1.11, "type": "Equity"},
    {"symbol": "NVDA", "name": "NVIDIA Corporation", "exchange": "NASDAQ", "price": 229.28, "change_pct": -0.52, "type": "Equity"},
    {"symbol": "TSLA", "name": "Tesla, Inc.", "exchange": "NASDAQ", "price": 268.45, "change_pct": 2.34, "type": "Equity"},
    {"symbol": "MSFT", "name": "Microsoft Corporation", "exchange": "NASDAQ", "price": 435.10, "change_pct": 0.85, "type": "Equity"},
    {"symbol": "AMZN", "name": "Amazon.com, Inc.", "exchange": "NASDAQ", "price": 185.30, "change_pct": -0.45, "type": "Equity"},
    {"symbol": "GOOGL", "name": "Alphabet Inc.", "exchange": "NASDAQ", "price": 178.90, "change_pct": 1.12, "type": "Equity"},
    {"symbol": "META", "name": "Meta Platforms, Inc.", "exchange": "NASDAQ", "price": 582.40, "change_pct": 1.65, "type": "Equity"},
    {"symbol": "AMD", "name": "Advanced Micro Devices", "exchange": "NASDAQ", "price": 165.20, "change_pct": -1.80, "type": "Equity"},
    {"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust", "exchange": "NYSEArca", "price": 585.10, "change_pct": 0.32, "type": "ETF"},
    {"symbol": "QQQ", "name": "Invesco QQQ Trust", "exchange": "NASDAQ", "price": 492.60, "change_pct": 0.45, "type": "ETF"},
    {"symbol": "BABA", "name": "Alibaba Group Holding", "exchange": "NYSE", "price": 98.40, "change_pct": -0.75, "type": "Equity"},
    {"symbol": "TSM", "name": "Taiwan Semiconductor Mfg", "exchange": "NYSE", "price": 190.50, "change_pct": 1.95, "type": "Equity"},
    {"symbol": "GS", "name": "Goldman Sachs Group, Inc.", "exchange": "NYSE", "price": 512.30, "change_pct": 1.15, "type": "Equity"},
    {"symbol": "MS", "name": "Morgan Stanley", "exchange": "NYSE", "price": 118.40, "change_pct": 0.82, "type": "Equity"},
    {"symbol": "JPM", "name": "JPMorgan Chase & Co.", "exchange": "NYSE", "price": 222.50, "change_pct": 0.65, "type": "Equity"},
    {"symbol": "PLTR", "name": "Palantir Technologies", "exchange": "NYSE", "price": 43.80, "change_pct": 3.45, "type": "Equity"},
    {"symbol": "COIN", "name": "Coinbase Global, Inc.", "exchange": "NASDAQ", "price": 215.30, "change_pct": 4.12, "type": "Equity"},
    {"symbol": "NFLX", "name": "Netflix, Inc.", "exchange": "NASDAQ", "price": 712.50, "change_pct": -0.25, "type": "Equity"}
]

def search_yahoo_tickers(query: str, max_results: int = 5):
    """
    Search Yahoo Finance for matching tickers by ticker symbol or company name.
    Retrieves latest price and percentage change (涨跌幅度) for up to max_results matches.
    Resilient to parentheses, IME pinyin, Chinese company names, and network timeouts.
    """
    if not query or not str(query).strip():
        return []

    raw_query = str(query).strip()
    clean_q = raw_query.replace("'", "").replace("’", "").strip()

    # 1. Bracket extraction: e.g. "ASE Technology Holding Co., Ltd. (ASX）" -> "ASX"
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
    search_term = primary_sym if primary_sym else clean_q

    cache_key = (search_term.lower(), max_results)
    now = datetime.now()
    if cache_key in SEARCH_CACHE:
        cached_t, cached_data = SEARCH_CACHE[cache_key]
        if (now - cached_t).total_seconds() < 90:
            return cached_data

    results = []
    try:
        s = yf.Search(search_term, max_results=max(8, max_results * 2))
        raw_quotes = getattr(s, 'quotes', []) or []

        # Filter out option chain symbols like ASSX270319C00035000
        filtered_quotes = []
        for q in raw_quotes:
            sym = q.get('symbol', '').upper()
            if not sym:
                continue
            if len(sym) > 8 and any(c.isdigit() for c in sym) and not sym.startswith('^'):
                continue
            filtered_quotes.append(q)

        # Prioritize primary symbol (e.g. ASX) to index 0
        has_primary = any(q.get('symbol', '').upper() == primary_sym for q in filtered_quotes) if primary_sym else False
        if primary_sym and not has_primary:
            fb = next((x for x in FALLBACK_STOCKS if x['symbol'].upper() == primary_sym), None)
            filtered_quotes.insert(0, {
                'symbol': primary_sym,
                'shortname': fb.get('name') if fb else COMPANY_NAME_LOOKUP.get(primary_sym, primary_sym),
                'exchDisp': fb.get('exchange') if fb else 'NYSE',
                'typeDisp': fb.get('type') if fb else 'Equity'
            })
        elif primary_sym:
            filtered_quotes.sort(key=lambda x: 0 if x.get('symbol', '').upper() == primary_sym else 1)

        quotes_to_fetch = filtered_quotes[:max_results]

        def fetch_single_quote(q_item):
            sym = q_item.get('symbol', '').upper()
            price, chg_pct = None, None

            # Check price memory cache first (5 min TTL)
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

            fallback_match = next((item for item in FALLBACK_STOCKS if item["symbol"].upper() == sym), None)

            try:
                t = yf.Ticker(sym)
                fi = t.fast_info
                last = getattr(fi, 'last_price', None)
                prev = getattr(fi, 'previous_close', None)
                if last is not None and prev is not None and prev > 0:
                    chg_pct = round(((last - prev) / prev) * 100.0, 2)
                    price = round(float(last), 2)
                elif last is not None:
                    price = round(float(last), 2)
                    chg_pct = 0.0
                elif fallback_match:
                    price = fallback_match.get("price")
                    chg_pct = fallback_match.get("change_pct")
            except Exception:
                if fallback_match:
                    price = fallback_match.get("price")
                    chg_pct = fallback_match.get("change_pct")

            if price is not None:
                PRICE_CACHE[sym] = (now, price, chg_pct)

            return {
                "symbol": sym,
                "name": q_item.get('shortname') or q_item.get('longname') or (fallback_match.get('name') if fallback_match else sym),
                "exchange": q_item.get('exchDisp') or q_item.get('exchange') or (fallback_match.get('exchange') if fallback_match else ''),
                "type": q_item.get('typeDisp') or q_item.get('quoteType') or 'Stock',
                "price": price,
                "change_pct": chg_pct
            }

        with ThreadPoolExecutor(max_workers=min(5, max(1, len(quotes_to_fetch)))) as executor:
            futures = [executor.submit(fetch_single_quote, q) for q in quotes_to_fetch]
            for f in futures:
                try:
                    res_item = f.result(timeout=2.0)
                    results.append(res_item)
                except Exception as ex:
                    logger.warning(f"Fetch quote timeout or error: {ex}")

    except Exception as e:
        logger.warning(f"Error querying yf.Search for '{query}': {e}. Using local fallback search.")

    # Fallback to local catalog if results are empty or search failed
    if not results:
        matched = []
        if primary_sym:
            for stock in FALLBACK_STOCKS:
                if stock['symbol'].upper() == primary_sym:
                    matched.append(stock)
                    break
        q_lower = clean_q.lower()
        for stock in FALLBACK_STOCKS:
            if stock not in matched and (q_lower in stock['symbol'].lower() or q_lower in stock['name'].lower()):
                matched.append(stock)
            if len(matched) >= max_results:
                break
        results = matched

    # Save to memory cache
    SEARCH_CACHE[cache_key] = (now, results)
    return results

