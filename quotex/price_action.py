# price_action.py
import numpy as np

def analyze_price_action(candles, lookback=50, short_lookback=10):
    """
    Ultimate price action analysis with advanced metrics.
    Args:
        candles: List of dicts with 'open', 'high', 'low', 'close' keys
        lookback: Long-term analysis period (default 50)
        short_lookback: Short-term analysis period (default 10)
    Returns:
        Dict with advanced price action metrics
    """
    if len(candles) < lookback:
        return {
            "supply_zone": {"level": 0, "strength": 0},
            "demand_zone": {"level": 0, "strength": 0},
            "breakout_power": 0,
            "trendline_dynamics": {"slope": 0, "strength": 0, "acceleration": 0},
            "liquidity_sweep": {"level": 0, "type": "none", "confidence": 0},
            "price_rejection_intensity": 0,
            "consolidation_breakout_potential": 0,
            "impulse_wave_strength": 0,
            "fibonacci_confluence": 0,
            "volatility_adjusted_pivot": 0,
            "momentum_divergence": 0
        }

    opens = np.array([c["open"] for c in candles[-lookback:]])
    highs = np.array([c["high"] for c in candles[-lookback:]])
    lows = np.array([c["low"] for c in candles[-lookback:]])
    closes = np.array([c["close"] for c in candles[-lookback:]])
    latest_close = closes[-1]
    short_closes = closes[-short_lookback:]

    # 1. Supply and Demand Zones (dynamic zones based on reversal points)
    returns = np.diff(closes) / closes[:-1] * 100
    reversal_indices = np.where(np.sign(returns[:-1]) != np.sign(returns[1:]))[0] + 1
    supply_level = np.mean(highs[reversal_indices[highs[reversal_indices] > closes[reversal_indices]]]) if np.any(highs[reversal_indices] > closes[reversal_indices]) else max(highs)
    demand_level = np.mean(lows[reversal_indices[lows[reversal_indices] < closes[reversal_indices]]]) if np.any(lows[reversal_indices] < closes[reversal_indices]) else min(lows)
    supply_strength = len(reversal_indices[highs[reversal_indices] > closes[reversal_indices]]) / lookback * 100
    demand_strength = len(reversal_indices[lows[reversal_indices] < closes[reversal_indices]]) / lookback * 100

    # 2. Breakout Power (momentum + volume proxy via range expansion)
    ranges = highs - lows
    breakout_power = 0
    if latest_close > supply_level:
        breakout_power = ((latest_close - supply_level) / supply_level * 100) * (np.mean(ranges[-5:]) / np.mean(ranges) if np.mean(ranges) != 0 else 1)
    elif latest_close < demand_level:
        breakout_power = ((demand_level - latest_close) / demand_level * 100) * (np.mean(ranges[-5:]) / np.mean(ranges) if np.mean(ranges) != 0 else 1)

    # 3. Trendline Dynamics (slope, strength, acceleration)
    x = np.arange(lookback)
    slope, intercept = np.polyfit(x, closes, 1)
    trendline_slope = slope * 1000  # Scaled for readability
    residuals = closes - (slope * x + intercept)
    trendline_strength = 100 - (np.std(residuals) / np.mean(closes) * 100)
    short_slope, _ = np.polyfit(np.arange(short_lookback), short_closes, 1)
    trendline_acceleration = (short_slope - slope) * 1000  # Change in slope

    # 4. Liquidity Sweep (extreme wick zones indicating stop hunts)
    wick_sizes = highs - np.maximum(opens, closes)
    lower_wick_sizes = np.minimum(opens, closes) - lows
    wick_total = wick_sizes + lower_wick_sizes
    wick_mean, wick_std = np.mean(wick_total), np.std(wick_total)
    liq_threshold = wick_mean + 2.5 * wick_std
    liq_indices = np.where(wick_total > liq_threshold)[0]
    if liq_indices.size > 0:
        liq_level = np.mean((highs[liq_indices] + lows[liq_indices]) / 2)
        liq_type = "bullish" if latest_close > liq_level else "bearish"
        liq_confidence = min(100, len(liq_indices) / lookback * 300)
        liquidity_sweep = {"level": liq_level, "type": liq_type, "confidence": liq_confidence}
    else:
        liquidity_sweep = {"level": 0, "type": "none", "confidence": 0}

    # 5. Price Rejection Intensity (wick rejection with momentum context)
    rejection_intensity = np.mean(wick_total[-5:] / ranges[-5:]) * 100 if np.mean(ranges[-5:]) != 0 else 0
    if abs(returns[-1]) > np.std(returns) * 1.5:
        rejection_intensity *= 1.5  # Boost if recent move is impulsive

    # 6. Consolidation Breakout Potential (range contraction + volatility)
    consolidation_volatility = np.std(ranges[-short_lookback:]) / np.mean(ranges[-short_lookback:]) if np.mean(ranges[-short_lookback:]) != 0 else 0
    consolidation_breakout_potential = 100 - (consolidation_volatility * 100) + (np.max(ranges[-3:]) / np.mean(ranges) * 50 if np.mean(ranges) != 0 else 0)

    # 7. Impulse Wave Strength (magnitude of consecutive directional moves)
    consecutive_returns = np.cumsum(returns * (np.sign(returns) == np.sign(np.roll(returns, 1))))
    impulse_wave_strength = np.max(np.abs(consecutive_returns[-short_lookback:])) if len(consecutive_returns) >= short_lookback else 0

    # 8. Fibonacci Confluence (proximity to key Fib levels)
    price_range = max(highs) - min(lows)
    fib_levels = [min(lows) + price_range * level for level in [0.236, 0.382, 0.5, 0.618, 0.786]]
    fib_distances = np.abs(latest_close - np.array(fib_levels))
    fib_confluence = 100 - (min(fib_distances) / price_range * 100) if price_range != 0 else 0

    # 9. Volatility-Adjusted Pivot (dynamic pivot with ATR weighting)
    atr = np.mean([max(h - l, abs(h - c_prev), abs(l - c_prev)) 
                   for h, l, c_prev in zip(highs[1:], lows[1:], closes[:-1])])
    pivots = (highs + lows + closes) / 3
    volatility_adjusted_pivot = np.mean(pivots[-short_lookback:] * (1 + atr / np.mean(closes)))

    # 10. Momentum Divergence (price vs. momentum divergence)
    momentum = np.diff(closes[-short_lookback:]) / closes[-short_lookback:-1] * 100
    price_trend = short_closes[-1] - short_closes[0]
    momentum_trend = np.sum(momentum)
    momentum_divergence = abs(price_trend - momentum_trend) / np.std(closes) * 100 if np.std(closes) != 0 else 0

    return {
        "supply_zone": {"level": supply_level, "strength": supply_strength},
        "demand_zone": {"level": demand_level, "strength": demand_strength},
        "breakout_power": breakout_power,
        "trendline_dynamics": {"slope": trendline_slope, "strength": trendline_strength, "acceleration": trendline_acceleration},
        "liquidity_sweep": liquidity_sweep,
        "price_rejection_intensity": rejection_intensity,
        "consolidation_breakout_potential": consolidation_breakout_potential,
        "impulse_wave_strength": impulse_wave_strength,
        "fibonacci_confluence": fib_confluence,
        "volatility_adjusted_pivot": volatility_adjusted_pivot,
        "momentum_divergence": momentum_divergence
    }