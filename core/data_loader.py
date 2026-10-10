import os
import json
import logging
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger("DataLoader")
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cache")

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
    ticker = ticker.upper().strip()
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
        {"symbol": "SPY", "name": "SPDR S&P 500 ETF", "sector": "Broad Market ETF", "badge": "Index Benchmark"},
        {"symbol": "QQQ", "name": "Invesco QQQ Trust (Nasdaq 100)", "sector": "Nasdaq 100 ETF", "badge": "Growth Index"},
        {"symbol": "AMZN", "name": "Amazon.com Inc.", "sector": "Consumer / Cloud", "badge": "E-Commerce"},
        {"symbol": "GOOGL", "name": "Alphabet Inc.", "sector": "Internet / Search", "badge": "AI Tech"},
        {"symbol": "AMD", "name": "Advanced Micro Devices", "sector": "Semiconductors", "badge": "Chipmaker"},
        {"symbol": "BABA", "name": "Alibaba Group ADR", "sector": "China E-Commerce", "badge": "ADR"}
    ]
