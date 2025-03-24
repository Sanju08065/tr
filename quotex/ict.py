import numpy as np
from datetime import datetime
import pytz

def analyze_ict(candles, current_time, lookback=50):
    """
    Ultimate ICT calculations focusing on institutional trading concepts.
    Args:
        candles: List of dicts with 'open', 'high', 'low', 'close', 'time'
        current_time: Current timestamp (seconds since epoch)
        lookback: Number of candles to analyze (default 50)
    Returns:
        Dict with ICT metrics
    """
    if len(candles) < lookback:
        return {
            "fair_value_gap": {"level": None, "detected": False, "probability": 0},
            "kill_zone": {"active": False, "confidence": 0},
            "power_of_three": {"pattern": None, "confidence": 0}
        }

    # Extract OHLC data
    highs = np.array([c["high"] for c in candles[-lookback:]])
    lows = np.array([c["low"] for c in candles[-lookback:]])
    closes = np.array([c["close"] for c in candles[-lookback:]])

    # 1. Fair Value Gap (price inefficiency zones)
    fvg_highs = highs[-10:]
    fvg_lows = lows[-10:]
    fvg_closes = closes[-10:]
    for i in range(len(fvg_highs) - 3):
        if fvg_highs[i] < fvg_lows[i + 2] and fvg_closes[i + 2] > fvg_closes[i]:  # Bullish FVG
            fvg_level = (fvg_highs[i] + fvg_lows[i + 2]) / 2
            fvg_detected = True
            fvg_prob = 90
            break
        elif fvg_lows[i] > fvg_highs[i + 2] and fvg_closes[i + 2] < fvg_closes[i]:  # Bearish FVG
            fvg_level = (fvg_lows[i] + fvg_highs[i + 2]) / 2
            fvg_detected = True
            fvg_prob = 90
            break
    else:
        fvg_level, fvg_detected, fvg_prob = None, False, 0

    # 2. Kill Zone (high-probability trading windows)
    tz = pytz.utc
    dt = datetime.fromtimestamp(current_time, tz)
    hour = dt.hour
    if 7 <= hour < 11:  # London Kill Zone: 7-11 UTC
        kill_zone, kill_confidence = "London Kill Zone", 95
    elif 13 <= hour < 17:  # NY Kill Zone: 13-17 UTC
        kill_zone, kill_confidence = "NY Kill Zone", 95
    else:
        kill_zone, kill_confidence = None, 0

    # 3. Power of Three (accumulation, manipulation, distribution)
    pot_closes = closes[-20:]
    pot_highs = highs[-20:]
    pot_lows = lows[-20:]
    if min(pot_lows[-10:]) < min(pot_lows[:-10]) and max(pot_highs[-5:]) > max(pot_highs[:-5]):  # Bullish POT
        pot_pattern, pot_confidence = "Bullish Power of Three", 85
    elif max(pot_highs[-10:]) > max(pot_highs[:-10]) and min(pot_lows[-5:]) < min(pot_lows[:-5]):  # Bearish POT
        pot_pattern, pot_confidence = "Bearish Power of Three", 85
    else:
        pot_pattern, pot_confidence = None, 0

    return {
        "fair_value_gap": {"level": fvg_level, "detected": fvg_detected, "probability": fvg_prob},
        "kill_zone": {"active": kill_zone is not None, "type": kill_zone, "confidence": kill_confidence},
        "power_of_three": {"pattern": pot_pattern, "confidence": pot_confidence}
    }