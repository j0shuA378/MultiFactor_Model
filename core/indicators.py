import numpy as np
import pandas as pd
from typing import Tuple

def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average (SMA)"""
    return series.rolling(window=period, min_periods=period).mean()

def calculate_ema(series: pd.Series, span: int) -> pd.Series:
    """Exponential Moving Average (EMA)"""
    return series.ewm(span=span, adjust=False).mean()

def calculate_macd(
    series: pd.Series, 
    fast: int = 12, 
    slow: int = 26, 
    signal: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Moving Average Convergence Divergence (MACD)
    Returns: (dif, dea, hist)
    - dif: Fast EMA - Slow EMA
    - dea: EMA of dif with signal period
    - hist: (dif - dea) * 2
    """
    ema_fast = calculate_ema(series, fast)
    ema_slow = calculate_ema(series, slow)
    dif = ema_fast - ema_slow
    dea = calculate_ema(dif, signal)
    hist = (dif - dea) * 2
    return dif, dea, hist

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Relative Strength Index (RSI) using authentic J. Welles Wilder's smoothing.
    Wilder Smoothing: alpha = 1 / period.
    Handles division by zero and ensures no lookahead bias in initialization.
    """
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    
    # Exponential weighted moving average with alpha = 1 / period
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    
    # Safe division
    denom = avg_loss.replace(0.0, np.nan)
    rs = avg_gain / denom
    rsi = 100.0 - (100.0 / (1.0 + rs))
    
    # Boundary conditions
    rsi = rsi.where(~((avg_loss == 0.0) & (avg_gain > 0.0)), 100.0)
    rsi = rsi.where(~((avg_gain == 0.0) & (avg_loss >= 0.0)), 0.0)
    rsi = rsi.where(~((avg_gain == 0.0) & (avg_loss == 0.0)), 50.0)
    
    # Fill pre-period warmup with 50.0 (neutral), strictly avoiding bfill future leakage
    return rsi.fillna(50.0)

def calculate_bollinger_bands(
    series: pd.Series, 
    period: int = 20, 
    std_mult: float = 2.0
) -> Tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
    """
    Bollinger Bands
    Returns: (upper, middle, lower, pct_b, bandwidth)
    - middle: SMA(period)
    - upper / lower: middle +/- std_mult * std
    - pct_b: (price - lower) / (upper - lower)
    - bandwidth: (upper - lower) / middle (useful for squeeze detection)
    """
    middle = calculate_sma(series, period)
    std = series.rolling(window=period, min_periods=period).std()
    upper = middle + (std * std_mult)
    lower = middle - (std * std_mult)
    
    band_range = (upper - lower).replace(0.0, np.nan)
    pct_b = ((series - lower) / band_range).fillna(0.5).clip(-0.5, 1.5)
    
    bandwidth = ((upper - lower) / middle.replace(0.0, np.nan)).fillna(0.0)
    return upper, middle, lower, pct_b, bandwidth

def calculate_atr(
    high: pd.Series, 
    low: pd.Series, 
    close: pd.Series, 
    period: int = 14
) -> pd.Series:
    """
    Average True Range (ATR) using Wilder's smoothing.
    TR = max(High - Low, abs(High - prev_Close), abs(Low - prev_Close))
    Warmup is initialized with expanding mean, strictly avoiding bfill future leakage.
    """
    prev_close = close.shift(1)
    # For bar 0 where prev_close is NaN, TR is simply High - Low
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Wilder's smoothing with alpha = 1 / period
    atr = tr.ewm(alpha=1.0 / period, min_periods=1, adjust=False).mean()
    return atr

def calculate_donchian_channel(
    high: pd.Series, 
    low: pd.Series, 
    period: int = 20,
    shift_lag: bool = True
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Donchian Channel (Turtle Breakout Channel)
    If shift_lag=True (Systematic Trading Default):
      - Upper = Highest High of the PRIOR `period` bars (excluding bar t)
      - Lower = Lowest Low of the PRIOR `period` bars (excluding bar t)
      Prevents lookahead leakage where bar t's high/low expands the channel boundary on the same bar.
    """
    raw_upper = high.rolling(window=period, min_periods=period).max()
    raw_lower = low.rolling(window=period, min_periods=period).min()
    
    if shift_lag:
        upper = raw_upper.shift(1)
        lower = raw_lower.shift(1)
    else:
        upper = raw_upper
        lower = raw_lower
        
    mid = (upper + lower) / 2.0
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
    
    data['EMA_10'] = calculate_ema(close, 10)
    data['EMA_12'] = calculate_ema(close, 12)
    data['EMA_26'] = calculate_ema(close, 26)
    data['EMA_30'] = calculate_ema(close, 30)
    
    dif, dea, hist = calculate_macd(close, 12, 26, 9)
    data['MACD_DIF'] = dif
    data['MACD_DEA'] = dea
    data['MACD_HIST'] = hist
    
    data['RSI_14'] = calculate_rsi(close, 14)
    
    bb_up, bb_mid, bb_low, pct_b, bb_width = calculate_bollinger_bands(close, 20, 2.0)
    data['BB_UPPER'] = bb_up
    data['BB_MIDDLE'] = bb_mid
    data['BB_LOWER'] = bb_low
    data['BB_PCT_B'] = pct_b
    data['BB_BANDWIDTH'] = bb_width
    
    data['ATR_14'] = calculate_atr(high, low, close, 14)
    data['ATR_20'] = calculate_atr(high, low, close, 20)
    
    # Donchian channel with shift_lag=True (excludes current bar)
    dc_up, dc_low, dc_mid = calculate_donchian_channel(high, low, 20, shift_lag=True)
    data['DONCHIAN_UP_20'] = dc_up
    data['DONCHIAN_LOW_20'] = dc_low
    data['DONCHIAN_MID_20'] = dc_mid
    
    # System 2 Donchian (55d / 20d)
    dc55_up, dc55_low, _ = calculate_donchian_channel(high, low, 55, shift_lag=True)
    data['DONCHIAN_UP_55'] = dc55_up
    data['DONCHIAN_LOW_55'] = dc55_low
    
    # Volume moving average
    if 'Volume' in data.columns:
        data['VOL_SMA_20'] = calculate_sma(data['Volume'], 20)
        
    return data
