# indicators.py
import numpy as np

def calculate_ema(candles, period):
    """
    Calculate Exponential Moving Average.
    Args:
        candles: List of dicts with 'close' key
        period: Lookback period for EMA
    Returns:
        Float: Latest EMA value
    """
    if len(candles) < period:
        return 0
    closes = np.array([c["close"] for c in candles])
    alpha = 2 / (period + 1)
    ema = closes[-period:].copy()
    for i in range(1, len(ema)):
        ema[i] = alpha * ema[i] + (1 - alpha) * ema[i-1]
    return ema[-1]

def calculate_rsi(candles, period=14):
    """
    Calculate Relative Strength Index.
    Args:
        candles: List of dicts with 'close' key
        period: Lookback period for RSI (default 14)
    Returns:
        Float: RSI value (0-100)
    """
    if len(candles) < period + 1:  # Need extra candle for diff
        return 50  # Neutral value if insufficient data
    closes = np.array([c["close"] for c in candles])
    deltas = np.diff(closes[-period-1:])
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[1:])  # Skip first diff
    avg_loss = np.mean(losses[1:])
    if avg_loss == 0:
        return 100 if avg_gain > 0 else 50
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_macd(candles, fast=12, slow=26, signal=9):
    """
    Calculate MACD (Moving Average Convergence Divergence).
    Args:
        candles: List of dicts with 'close' key
        fast: Fast EMA period (default 12)
        slow: Slow EMA period (default 26)
        signal: Signal line period (default 9)
    Returns:
        Tuple: (macd_line, signal_line, histogram)
    """
    if len(candles) < slow:
        return 0, 0, 0
    closes = np.array([c["close"] for c in candles])
    ema_fast = calculate_ema(candles[-fast:], fast)
    ema_slow = calculate_ema(candles[-slow:], slow)
    macd_line = ema_fast - ema_slow
    
    # Calculate signal line (EMA of MACD line)
    if len(candles) >= slow + signal - 1:
        macd_values = [calculate_ema(candles[:i+1], fast) - calculate_ema(candles[:i+1], slow) 
                       for i in range(slow-1, slow-1+signal)]
        alpha = 2 / (signal + 1)
        signal_line = macd_values[0]
        for i in range(1, len(macd_values)):
            signal_line = alpha * macd_values[i] + (1 - alpha) * signal_line
    else:
        signal_line = 0
    
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calculate_bollinger_bands(candles, period=20, std_dev=2):
    """
    Calculate Bollinger Bands.
    Args:
        candles: List of dicts with 'close' key
        period: Lookback period for SMA (default 20)
        std_dev: Standard deviation multiplier (default 2)
    Returns:
        Tuple: (upper_bb, sma, lower_bb, bandwidth)
    """
    if len(candles) < period:
        return 0, 0, 0, 0
    closes = np.array([c["close"] for c in candles[-period:]])
    sma = np.mean(closes)
    std = np.std(closes)
    upper_bb = sma + std_dev * std
    lower_bb = sma - std_dev * std
    bandwidth = (upper_bb - lower_bb) / sma if sma != 0 else 0
    return upper_bb, sma, lower_bb, bandwidth

def calculate_atr(candles, period=14):
    """
    Calculate Average True Range.
    Args:
        candles: List of dicts with 'high', 'low', 'close' keys
        period: Lookback period for ATR (default 14)
    Returns:
        Float: ATR value
    """
    if len(candles) < period + 1:  # Need extra candle for previous close
        return 0
    highs = np.array([c["high"] for c in candles[-period-1:]])
    lows = np.array([c["low"] for c in candles[-period-1:]])
    closes = np.array([c["close"] for c in candles[-period-1:]])
    tr = np.maximum(highs[1:] - lows[1:], 
                    np.abs(highs[1:] - closes[:-1]), 
                    np.abs(lows[1:] - closes[:-1]))
    return np.mean(tr)

def calculate_adx(candles, period=14):
    """
    Calculate Average Directional Index.
    Args:
        candles: List of dicts with 'high', 'low', 'close' keys
        period: Lookback period for ADX (default 14)
    Returns:
        Float: ADX value (0-100)
    """
    if len(candles) < period + 1:
        return 0
    highs = np.array([c["high"] for c in candles[-period-1:]])
    lows = np.array([c["low"] for c in candles[-period-1:]])
    dm_plus = np.zeros(period)
    dm_minus = np.zeros(period)
    tr = np.zeros(period)
    
    for i in range(period):
        up_move = highs[i+1] - highs[i]
        down_move = lows[i] - lows[i+1]
        dm_plus[i] = up_move if up_move > down_move and up_move > 0 else 0
        dm_minus[i] = down_move if down_move > up_move and down_move > 0 else 0
        tr[i] = max(highs[i+1] - lows[i+1], 
                    abs(highs[i+1] - candles[i]["close"]), 
                    abs(lows[i+1] - candles[i]["close"]))
    
    atr = np.mean(tr)
    if atr == 0:
        return 0
    di_plus = 100 * np.mean(dm_plus) / atr
    di_minus = 100 * np.mean(dm_minus) / atr
    dx = 100 * abs(di_plus - di_minus) / (di_plus + di_minus) if (di_plus + di_minus) != 0 else 0
    return dx