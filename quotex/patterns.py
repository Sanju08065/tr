# patterns.py
import numpy as np

def detect_patterns(candles):
    """
    Detect candlestick patterns and assign confidence.
    Args:
        candles: List of dicts with 'open', 'high', 'low', 'close' keys
    Returns:
        Tuple: (pattern_name, confidence) where confidence is 0-100
    """
    if len(candles) < 3:  # Need at least 3 candles for multi-candle patterns
        return "N/A", 0
    
    opens = np.array([c["open"] for c in candles[-3:]])
    highs = np.array([c["high"] for c in candles[-3:]])
    lows = np.array([c["low"] for c in candles[-3:]])
    closes = np.array([c["close"] for c in candles[-3:]])
    body_sizes = np.abs(closes - opens)
    ranges = highs - lows
    
    # Single Candle Patterns
    # Bullish Hammer
    if (closes[-1] > opens[-1] and
        (highs[-1] - closes[-1]) > 2 * body_sizes[-1] and  # Long upper wick
        (opens[-1] - lows[-1]) < body_sizes[-1] * 0.3 and  # Short lower wick
        body_sizes[-1] < ranges[-1] * 0.3):  # Small body
        return "Bullish Hammer", 85
    
    # Bearish Shooting Star
    if (closes[-1] < opens[-1] and
        (highs[-1] - opens[-1]) > 2 * body_sizes[-1] and  # Long upper wick
        (closes[-1] - lows[-1]) < body_sizes[-1] * 0.3 and  # Short lower wick
        body_sizes[-1] < ranges[-1] * 0.3):  # Small body
        return "Bearish Shooting Star", 85
    
    # Multi-Candle Patterns
    # Morning Star (Bullish Reversal)
    if (closes[-3] < opens[-3] and  # Downtrend (bearish candle)
        body_sizes[-2] < ranges[-2] * 0.3 and  # Small body (indecision)
        closes[-1] > opens[-1] and  # Uptrend (bullish candle)
        closes[-1] > (opens[-3] + closes[-3]) / 2 and  # Close above midpoint of first candle
        lows[-2] < lows[-3]):  # Gap down then up
        return "Morning Star", 90
    
    # Evening Star (Bearish Reversal)
    if (closes[-3] > opens[-3] and  # Uptrend (bullish candle)
        body_sizes[-2] < ranges[-2] * 0.3 and  # Small body (indecision)
        closes[-1] < opens[-1] and  # Downtrend (bearish candle)
        closes[-1] < (opens[-3] + closes[-3]) / 2 and  # Close below midpoint of first candle
        highs[-2] > highs[-3]):  # Gap up then down
        return "Evening Star", 90
    
    # Bullish Engulfing
    if len(candles) >= 2 and (closes[-2] < opens[-2] and  # Bearish candle
                              closes[-1] > opens[-1] and  # Bullish candle
                              closes[-1] > opens[-2] and  # Engulfs previous open
                              opens[-1] < closes[-2]):  # Engulfs previous close
        return "Bullish Engulfing", 80
    
    # Bearish Engulfing
    if len(candles) >= 2 and (closes[-2] > opens[-2] and  # Bullish candle
                              closes[-1] < opens[-1] and  # Bearish candle
                              closes[-1] < opens[-2] and  # Engulfs previous open
                              opens[-1] > closes[-2]):  # Engulfs previous close
        return "Bearish Engulfing", 80
    
    return "N/A", 0