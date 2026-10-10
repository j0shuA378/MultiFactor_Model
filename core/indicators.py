import numpy as np
import pandas as pd

def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average (SMA)"""
    return series.rolling(window=period).mean()

def calculate_ema(series: pd.Series, span: int) -> pd.Series:
    """Exponential Moving Average (EMA)"""
    return series.ewm(span=span, adjust=False).mean()

def calculate_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """
    Moving Average Convergence Divergence (MACD)
    Returns: (dif, dea, hist)
    """
    ema_fast = calculate_ema(series, fast)
    ema_slow = calculate_ema(series, slow)
    dif = ema_fast - ema_slow
    dea = calculate_ema(dif, signal)
    hist = (dif - dea) * 2
    return dif, dea, hist

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index (RSI) using Wilder's smoothing"""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    # Exponential weighted moving average with alpha = 1 / period
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def calculate_bollinger_bands(series: pd.Series, period: int = 20, std_mult: float = 2.0):
    """
    Bollinger Bands
    Returns: (upper, middle, lower, pct_b)
    """
    middle = calculate_sma(series, period)
    std = series.rolling(window=period).std()
    upper = middle + (std * std_mult)
    lower = middle - (std * std_mult)
    pct_b = (series - lower) / (upper - lower).replace(0, np.nan)
    return upper, middle, lower, pct_b

def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range (ATR)"""
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    return atr

def calculate_donchian_channel(high: pd.Series, low: pd.Series, period: int = 20):
    """
    Donchian Channel (Turtle Breakout Channel)
    Returns: (upper, lower, mid)
    """
    upper = high.rolling(window=period).max()
    lower = low.rolling(window=period).min()
    mid = (upper + lower) / 2
    return upper, lower, mid

def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Adds standard technical indicators to stock OHLCV DataFrame"""
    data = df.copy()
    close = data['Close']
    high = data['High']
    low = data['Low']
    
    data['SMA_5'] = calculate_sma(close, 5)
    data['SMA_10'] = calculate_sma(close, 10)
    data['SMA_20'] = calculate_sma(close, 20)
    data['SMA_50'] = calculate_sma(close, 50)
    data['SMA_200'] = calculate_sma(close, 200)
    
    data['EMA_12'] = calculate_ema(close, 12)
    data['EMA_26'] = calculate_ema(close, 26)
    
    dif, dea, hist = calculate_macd(close, 12, 26, 9)
    data['MACD_DIF'] = dif
    data['MACD_DEA'] = dea
    data['MACD_HIST'] = hist
    
    data['RSI_14'] = calculate_rsi(close, 14)
    
    bb_up, bb_mid, bb_low, pct_b = calculate_bollinger_bands(close, 20, 2.0)
    data['BB_UPPER'] = bb_up
    data['BB_MIDDLE'] = bb_mid
    data['BB_LOWER'] = bb_low
    data['BB_PCT_B'] = pct_b
    
    data['ATR_14'] = calculate_atr(high, low, close, 14)
    
    dc_up, dc_low, dc_mid = calculate_donchian_channel(high, low, 20)
    data['DONCHIAN_UP_20'] = dc_up
    data['DONCHIAN_LOW_20'] = dc_low
    
    # Volume moving average
    if 'Volume' in data.columns:
        data['VOL_SMA_20'] = calculate_sma(data['Volume'], 20)
        
    return data
