import numpy as np

def analyze_smc(candles, lookback=50):
    """
    Ultimate SMC calculations focusing on institutional price action.
    Args:
        candles: List of dicts with 'open', 'high', 'low', 'close'
        lookback: Number of candles to analyze (default 50)
    Returns:
        Dict with SMC metrics
    """
    if len(candles) < lookback:
        return {
            "order_block": {"level": None, "type": None, "confidence": 0},
            "liquidity_grab": {"direction": None, "confidence": 0},
            "imbalance": {"direction": None, "level": None, "confidence": 0}
        }

    # Extract OHLC data
    opens = np.array([c["open"] for c in candles[-lookback:]])
    highs = np.array([c["high"] for c in candles[-lookback:]])
    lows = np.array([c["low"] for c in candles[-lookback:]])
    closes = np.array([c["close"] for c in candles[-lookback:]])

    # 1. Order Block (significant support/resistance zones)
    trend = np.mean(np.diff(closes[-20:-1]))  # Trend over last 19 candles
    latest_close = closes[-1]
    if trend > 0:  # Bullish trend
        ob_idx = np.argmin(lows[-5:])  # Strong rejection low in last 5
        if latest_close > lows[-5:][ob_idx]:
            ob_level = lows[-5:][ob_idx]
            ob_confidence = min(100, 75 + abs(trend) * 1000)
            ob_type = "bullish"
        else:
            ob_level, ob_type, ob_confidence = None, None, 0
    elif trend < 0:  # Bearish trend
        ob_idx = np.argmax(highs[-5:])  # Strong rejection high
        if latest_close < highs[-5:][ob_idx]:
            ob_level = highs[-5:][ob_idx]
            ob_confidence = min(100, 75 + abs(trend) * 1000)
            ob_type = "bearish"
        else:
            ob_level, ob_type, ob_confidence = None, None, 0
    else:
        ob_level, ob_type, ob_confidence = None, None, 0

    # 2. Liquidity Grab (stop-loss hunting)
    liq_highs = highs[-10:]
    liq_lows = lows[-10:]
    liq_closes = closes[-10:]
    if liq_highs[-1] > max(liq_highs[:-1]) and liq_closes[-1] < liq_closes[-2]:  # Sweep highs, close lower
        liq_direction, liq_confidence = "bearish", 80
    elif liq_lows[-1] < min(liq_lows[:-1]) and liq_closes[-1] > liq_closes[-2]:  # Sweep lows, close higher
        liq_direction, liq_confidence = "bullish", 80
    else:
        liq_direction, liq_confidence = None, 0

    # 3. Imbalance (unfilled price gaps)
    imb_highs = highs[-10:]
    imb_lows = lows[-10:]
    for i in range(len(imb_highs) - 3):
        if imb_highs[i] < imb_lows[i + 2]:  # Gap up
            imb_direction = "bullish"
            imb_level = (imb_highs[i] + imb_lows[i + 2]) / 2
            imb_confidence = 85
            break
        elif imb_lows[i] > imb_highs[i + 2]:  # Gap down
            imb_direction = "bearish"
            imb_level = (imb_lows[i] + imb_highs[i + 2]) / 2
            imb_confidence = 85
            break
    else:
        imb_direction, imb_level, imb_confidence = None, None, 0

    return {
        "order_block": {"level": ob_level, "type": ob_type, "confidence": ob_confidence},
        "liquidity_grab": {"direction": liq_direction, "confidence": liq_confidence},
        "imbalance": {"direction": imb_direction, "level": imb_level, "confidence": imb_confidence}
    }