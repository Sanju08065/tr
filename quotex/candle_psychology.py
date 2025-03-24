import numpy as np

def analyze_candle_psychology(candles, lookback=50):
    """
    Ultimate candle psychology calculations focusing on price action behavior.
    Args:
        candles: List of dicts with 'open', 'high', 'low', 'close'
        lookback: Number of candles to analyze (default 50)
    Returns:
        Dict with psychology metrics
    """
    if len(candles) < lookback:
        return {
            "trend_persistence": 0,
            "reversal_strength": 0,
            "volatility_clustering": 0,
            "exhaustion_signal": 0,
            "sentiment": "neutral",
            "sentiment_polarity": 0,
            "fractal_momentum": 0,
            "mtf_correlation": 0,
            "psychological_pressure": 0,
            "candle_entropy": 0
        }

    # Extract OHLC data
    opens = np.array([c["open"] for c in candles[-lookback:]])
    highs = np.array([c["high"] for c in candles[-lookback:]])
    lows = np.array([c["low"] for c in candles[-lookback:]])
    closes = np.array([c["close"] for c in candles[-lookback:]])

    # 1. Trend Persistence (directional consistency)
    returns = np.diff(closes) / closes[:-1] * 100  # Percentage returns
    bullish_count = np.sum(returns > 0)
    bearish_count = np.sum(returns < 0)
    trend_persistence = (bullish_count - bearish_count) / lookback * 100  # -100 to +100

    # 2. Reversal Strength (size of reversal candles)
    body_sizes = np.abs(closes - opens)
    reversal_indices = np.where(np.sign(returns[:-1]) != np.sign(returns[1:]))[0]
    reversal_strength = np.mean(body_sizes[reversal_indices]) / np.mean(body_sizes) * 100 if reversal_indices.size > 0 else 0

    # 3. Volatility Clustering (grouping of large moves)
    volatility = np.std(returns) * np.sqrt(lookback)
    large_moves = np.abs(returns) > volatility
    clustering = np.sum(np.diff(np.where(large_moves)[0]) == 1) / lookback * 100 if large_moves.any() else 0

    # 4. Exhaustion Signal (long wicks after trends)
    wick_sizes = highs - np.maximum(opens, closes)
    lower_wick_sizes = np.minimum(opens, closes) - lows
    exhaustion_signal = np.mean(wick_sizes[-5:] + lower_wick_sizes[-5:]) / np.mean(body_sizes[-5:]) * 100 if trend_persistence > 50 else 0

    # 5. Sentiment and Polarity
    sentiment = "bullish" if trend_persistence > 20 else "bearish" if trend_persistence < -20 else "neutral"
    sentiment_polarity = trend_persistence  # -100 to +100

    # 6. Fractal Momentum (self-similar momentum across scales)
    short_momentum = np.mean(returns[-5:]) * 100
    long_momentum = np.mean(returns[-20:]) * 100
    fractal_momentum = short_momentum / long_momentum if long_momentum != 0 else 0  # Ratio > 1 = acceleration

    # 7. MTF Correlation (alignment with higher timeframe)
    mtf_returns = np.diff(closes[::5]) / closes[:-5:5] * 100  # Simulated 5-min timeframe
    mtf_correlation = np.corrcoef(returns[-len(mtf_returns):], mtf_returns)[0, 1] * 100 if len(mtf_returns) > 1 else 0

    # 8. Psychological Pressure (wick rejection intensity)
    rejection_pressure = np.mean(wick_sizes[-10:] / (highs[-10:] - lows[-10:])) * 100 if np.mean(highs[-10:] - lows[-10:]) != 0 else 0
    psychological_pressure = min(100, rejection_pressure * 2)  # Cap at 100

    # 9. Candle Entropy (unpredictability of price action)
    bin_counts, _ = np.histogram(returns, bins=10)
    probs = bin_counts / bin_counts.sum()
    entropy = -np.sum(probs * np.log2(probs + 1e-10)) / np.log2(10) * 100  # Normalized to 0-100
    candle_entropy = entropy

    return {
        "trend_persistence": trend_persistence,
        "reversal_strength": reversal_strength,
        "volatility_clustering": clustering,
        "exhaustion_signal": exhaustion_signal,
        "sentiment": sentiment,
        "sentiment_polarity": sentiment_polarity,
        "fractal_momentum": fractal_momentum,
        "mtf_correlation": mtf_correlation,
        "psychological_pressure": psychological_pressure,
        "candle_entropy": candle_entropy
    }