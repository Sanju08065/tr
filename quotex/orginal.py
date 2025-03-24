import os
import sys
import json
import time
import random
import asyncio
import itertools
from quotexapi.stable_api import Quotex
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

console = Console()
trade_count = 0
log = []

# User Input for Credentials and Trading Parameters
def get_user_input():
    email = console.input("[bold green]Enter Quotex Email: [/]")
    password = console.input("[bold green]Enter Quotex Password: [/]")
    base_bet = float(console.input("[bold yellow]Enter Base Bet ($): [/]"))
    martingale = float(console.input("[bold yellow]Enter Martingale Multiplier (e.g., 2.0): [/]"))
    stop_loss = float(console.input("[bold red]Enter Stop Loss ($): [/]"))
    stop_profit = float(console.input("[bold green]Enter Stop Profit ($): [/]"))
    return email, password, base_bet, martingale, stop_loss, stop_profit

# High-Quality Signal UI with Colored Lines
def update_ui(status, asset, analysis, log_entry, spinner="", confidence=0, balance=0):
    signal_bar = "█" * int(confidence / 10) + "░" * (10 - int(confidence / 10))
    signal_color = "green" if confidence >= 90 else "yellow" if confidence >= 70 else "red"
    content = (
        f"[bold white on #1e1e1e] 🚀 [green]Status[/]: [/] [cyan]{status}[/] "
        f"[bold white on #1e1e1e] | [magenta]Asset[/]: [/] [magenta]{asset}[/] "
        f"[bold white on #1e1e1e] | [yellow]Signal[/]: [/] [{signal_color}]{signal_bar} {confidence:.1f}%[/] "
        f"[bold white on #1e1e1e] | [yellow]Analysis[/]: [/] [yellow]{analysis}[/] "
        f"[bold white on #1e1e1e] | [blue]Log[/]: [/] [blue]{log_entry} {spinner}[/] "
        f"[bold white on #1e1e1e] | [cyan]Balance[/]: [/] [cyan]${balance:.2f}[/]"
    )
    return Panel(
        Text(content, justify="left"),
        border_style="bold #00ff00",
        box=rich.box.ROUNDED,
        height=3,
        padding=(0, 1),
        style="on #1e1e1e"
    )

# Trading Logic
async def login_and_fetch_assets(client, live):
    check_connect, reason = await client.connect()
    if not check_connect:
        log.append(f"Connection failed: {reason}")
        live.update(update_ui("Failed", "None", "N/A", log[-1]))
        return None
    
    log.append("Logged in successfully!")
    client.change_account("PRACTICE")
    
    with Progress(
        SpinnerColumn(),
        "[progress.description]{task.description}",
        BarColumn(),
        "[progress.percentage]{task.percentage:>3.0f}%",
        console=console
    ) as progress:
        all_assets = await client.get_all_assets()
        task = progress.add_task("[cyan]Fetching Institutional Signals...", total=len(all_assets))
        open_assets = {}
        for i, (asset_code, _) in enumerate(all_assets.items()):
            asset_name, asset_info = await client.get_available_asset(asset_code, force_open=True)
            if asset_info[2]:
                payout = client.get_payout_by_asset(asset_code)
                if payout and "turbo" in payout:
                    open_assets[asset_name] = payout["turbo"]["profit"]
            progress.update(task, advance=1)
            log.append(f"Scanning assets ({i+1}/{len(all_assets)})")
            live.update(update_ui("Fetching", "None", "N/A", log[-1]))
            await asyncio.sleep(0.05)
        
        log.append(f"Assets Loaded: {len(open_assets)} found")
        live.update(update_ui("Idle", "None", "N/A", log[-1]))
    return open_assets

def select_high_profit_asset(open_assets, live):
    if not open_assets:
        log.append("No institutional-grade assets detected.")
        live.update(update_ui("Idle", "None", "N/A", log[-1]))
        return None
    high_profit_asset = max(open_assets, key=open_assets.get)
    log.append(f"Locked: {high_profit_asset} @ {open_assets[high_profit_asset]}% payout")
    live.update(update_ui("Idle", high_profit_asset, "N/A", log[-1]))
    return high_profit_asset

# SMC/ICT Indicators
def identify_order_block(candles):
    for i in range(len(candles) - 1, 1, -1):
        if candles[i]["close"] > candles[i]["open"] and candles[i-1]["close"] < candles[i-1]["open"]:
            return candles[i]["high"], "bullish"
        elif candles[i]["close"] < candles[i]["open"] and candles[i-1]["close"] > candles[i-1]["open"]:
            return candles[i]["low"], "bearish"
    return None, None

def detect_fair_value_gap(candles):
    for i in range(len(candles) - 2, 1, -1):
        if (candles[i]["high"] < candles[i-1]["low"] and candles[i]["low"] > candles[i+1]["high"]) or \
           (candles[i]["low"] > candles[i-1]["high"] and candles[i]["high"] < candles[i+1]["low"]):
            return (candles[i]["high"] + candles[i]["low"]) / 2, True
    return None, False

def check_liquidity_grab(candles):
    recent_high = max(c["high"] for c in candles[-10:])
    recent_low = min(c["low"] for c in candles[-10:])
    latest = candles[-1]
    if latest["high"] > recent_high and latest["close"] < recent_high:
        return "bearish", 85
    elif latest["low"] < recent_low and latest["close"] > recent_low:
        return "bullish", 85
    return None, 0

def calculate_sma(candles, period=50):
    closes = [c["close"] for c in candles[-period:]]
    return sum(closes) / len(closes)

def calculate_macd(candles, fast=12, slow=26, signal=9):
    closes = [c["close"] for c in candles[-(slow + signal):]]
    ema_fast = sum(closes[-fast:]) / fast
    ema_slow = sum(closes[-slow:]) / slow
    macd_line = ema_fast - ema_slow
    signal_line = sum([calculate_sma(candles[-(i+signal):-i or None], fast) - calculate_sma(candles[-(i+signal):-i or None], slow) for i in range(signal)]) / signal
    histogram = macd_line - ema_slow
    return macd_line, signal_line, histogram

def calculate_bollinger_bands(candles, period=20, std_dev=2):
    closes = [c["close"] for c in candles[-period:]]
    sma = sum(closes) / period
    variance = sum((x - sma) ** 2 for x in closes) / period
    std = variance ** 0.5
    upper_band = sma + std_dev * std
    lower_band = sma - std_dev * std
    return upper_band, sma, lower_band

def calculate_stochastic(candles, period=14):
    highs = [c["high"] for c in candles[-period:]]
    lows = [c["low"] for c in candles[-period:]]
    close = candles[-1]["close"]
    highest_high = max(highs)
    lowest_low = min(lows)
    k = 100 * (close - lowest_low) / (highest_high - lowest_low) if highest_high != lowest_low else 50
    return k

# Candlestick Psychology
def analyze_candle_psychology(candles):
    if len(candles) < 3:
        return "Neutral", 50
    
    latest = candles[-1]
    prev = candles[-2]
    prev2 = candles[-3]
    body = abs(latest["close"] - latest["open"])
    range = latest["high"] - latest["low"]
    upper_wick = latest["high"] - max(latest["open"], latest["close"])
    lower_wick = min(latest["open"], latest["close"]) - latest["low"]
    
    if body < range * 0.1:
        return "Doji", 65
    elif lower_wick > body * 2 and upper_wick < body * 0.2 and latest["close"] > latest["open"]:
        return "Hammer", 85
    elif upper_wick > body * 2 and lower_wick < body * 0.2 and latest["close"] < latest["open"]:
        return "Shooting Star", 85
    elif (prev["close"] < prev["open"] and latest["close"] > latest["open"] and 
          latest["open"] <= prev["close"] and latest["close"] >= prev["open"]):
        return "Bullish Engulfing", 90
    elif (prev["close"] > prev["open"] and latest["close"] < latest["open"] and 
          latest["open"] >= prev["close"] and latest["close"] <= prev["open"]):
        return "Bearish Engulfing", 90
    elif (prev2["close"] < prev2["open"] and prev["close"] > prev["open"] and 
          prev["open"] < prev2["close"] and latest["close"] > latest["open"] and 
          latest["close"] > prev2["open"]):
        return "Morning Star", 95
    elif (prev2["close"] > prev2["open"] and prev["close"] < prev["open"] and 
          prev["open"] > prev2["close"] and latest["close"] < latest["open"] and 
          latest["close"] < prev2["open"]):
        return "Evening Star", 95
    elif (latest["close"] < latest["open"] and prev["close"] < prev["open"] and 
          prev2["close"] < prev2["open"] and latest["close"] < prev["open"] < prev2["open"]):
        return "Three Black Crows", 93
    elif (latest["close"] > latest["open"] and prev["close"] > prev["open"] and 
          prev2["close"] > prev2["open"] and latest["close"] > prev["open"] > prev2["open"]):
        return "Three White Soldiers", 93
    
    return "Neutral", 50

async def analyze_asset(client, asset, live):
    candles = await client.get_candles(asset, time.time(), 3600, 60)
    if len(candles) < 50:
        log.append("Insufficient data for institutional analysis.")
        live.update(update_ui("Idle", asset, "N/A", log[-1]))
        return None, 0
    
    sma = calculate_sma(candles)
    macd_line, signal_line, histogram = calculate_macd(candles)
    upper_bb, mid_bb, lower_bb = calculate_bollinger_bands(candles)
    stochastic_k = calculate_stochastic(candles)
    latest_close = candles[-1]["close"]
    psych_pattern, psych_confidence = analyze_candle_psychology(candles)
    
    ob_level, ob_type = identify_order_block(candles)
    fvg_level, fvg_detected = detect_fair_value_gap(candles)
    liq_direction, liq_confidence = check_liquidity_grab(candles)
    
    confidence = 0
    direction = None
    
    if latest_close > sma:
        confidence += 20
        direction = "call"
    elif latest_close < sma:
        confidence += 20
        direction = "put"
    
    if macd_line > signal_line and histogram > 0:
        confidence += 25 if direction == "call" else confidence
    elif macd_line < signal_line and histogram < 0:
        confidence += 25 if direction == "put" else confidence
    
    if latest_close < upper_bb and direction == "call":
        confidence += 15
    elif latest_close > lower_bb and direction == "put":
        confidence += 15
    
    if stochastic_k < 80 and direction == "call":
        confidence += 10
    elif stochastic_k > 20 and direction == "put":
        confidence += 10
    
    if ob_level and ob_type == "bullish" and direction == "call" and abs(latest_close - ob_level) < 0.001:
        confidence += 20
    elif ob_level and ob_type == "bearish" and direction == "put" and abs(latest_close - ob_level) < 0.001:
        confidence += 20
    
    if fvg_detected and direction == "call" and latest_close < fvg_level:
        confidence += 15
    elif fvg_detected and direction == "put" and latest_close > fvg_level:
        confidence += 15
    
    if liq_direction == "bullish" and direction == "call":
        confidence += liq_confidence * 0.2
    elif liq_direction == "bearish" and direction == "put":
        confidence += liq_confidence * 0.2
    
    if "bullish" in psych_pattern.lower() or "hammer" in psych_pattern.lower() or "morning" in psych_pattern.lower() or "soldiers" in psych_pattern.lower():
        if direction == "call":
            confidence += psych_confidence * 0.25
    elif "bearish" in psych_pattern.lower() or "shooting" in psych_pattern.lower() or "evening" in psych_pattern.lower() or "crows" in psych_pattern.lower():
        if direction == "put":
            confidence += psych_confidence * 0.25
    
    analysis = f"{direction or 'N/A'} | {psych_pattern}"
    if confidence >= 90:  # Changed from 95 to 90
        log.append(f"🔥 ELITE SMC/ICT SIGNAL: {direction.upper()} @ {confidence:.1f}%")
        live.update(update_ui("Analyzed", asset, analysis, log[-1], confidence=confidence))
        return direction, confidence
    else:
        log.append(f"Signal below 90%: {confidence:.1f}%")
        live.update(update_ui("Idle", asset, analysis, log[-1], confidence=confidence))
        return None, confidence

async def place_trade_with_martingale(client, asset, live, base_bet, martingale, stop_loss, stop_profit):
    global trade_count
    amount = base_bet
    attempt = 1
    total_profit = 0
    
    while attempt <= 3:
        balance = await client.get_balance()
        direction, confidence = await analyze_asset(client, asset, live)
        if not direction or confidence < 90:  # Changed from 95 to 90
            log.append("Awaiting 90% elite SMC/ICT signal...")
            live.update(update_ui("Idle", asset, "N/A", log[-1], confidence=confidence, balance=balance))
            return False
        
        log.append(f"Executing {direction.upper()} trade @ ${amount:.2f} (Conf: {confidence:.1f}%)")
        live.update(update_ui("Trading", asset, f"{direction}", log[-1], confidence=confidence, balance=balance))
        
        status, buy_info = await client.buy(amount, asset, direction, 60)
        if not status:
            log.append(f"Trade failed: {buy_info}")
            live.update(update_ui("Idle", asset, "N/A", log[-1], balance=balance))
            return False
        
        spinner = itertools.cycle(['🌑', '🌒', '🌓', '🌔', '🌕', '🌖', '🌗', '🌘'])
        for i in range(60):
            log[-1] = f"Trade in progress ({60-i}s)"
            live.update(update_ui("Waiting", asset, f"{direction}", log[-1], next(spinner), confidence, balance))
            await asyncio.sleep(1)
        
        win = await client.check_win(buy_info["id"])
        profit = client.get_profit()
        total_profit += profit
        balance = await client.get_balance()
        
        if win:
            log.append(f"🎉 WIN! Profit: ${profit:.2f}")
            trade_count += 1
            live.update(update_ui("Idle", asset, "N/A", log[-1], confidence=confidence, balance=balance))
            if total_profit >= stop_profit:
                log.append(f"Stop Profit reached: ${total_profit:.2f}")
                live.update(update_ui("Stopped", asset, "N/A", log[-1], balance=balance))
                return True
            return True
        else:
            log.append(f"❌ LOSS! Loss: ${profit:.2f}")
            amount *= martingale
            trade_count += 1
            attempt += 1
            if -total_profit >= stop_loss:
                log.append(f"Stop Loss triggered: ${-total_profit:.2f}")
                live.update(update_ui("Stopped", asset, "N/A", log[-1], balance=balance))
                return False
            if attempt > 3:
                log.append("Max Martingale attempts reached.")
            else:
                log.append(f"Martingale activated: Next @ ${amount:.2f}")
            live.update(update_ui("Idle", asset, "N/A", log[-1], balance=balance))
            return False

async def smart_martingale_trade():
    email, password, base_bet, martingale, stop_loss, stop_profit = get_user_input()
    client = Quotex(email=email, password=password, lang="pt")
    
    with Live(update_ui("Idle", "None", "N/A", "Initializing SMC/ICT Algos...", balance=0), refresh_per_second=15, console=console) as live:
        open_assets = await login_and_fetch_assets(client, live)
        if not open_assets:
            client.close()
            return
        
        high_profit_asset = select_high_profit_asset(open_assets, live)
        if not high_profit_asset:
            client.close()
            return
        
        initial_balance = await client.get_balance()
        while True:
            start_time = time.time()
            balance = await client.get_balance()
            trade_executed = await place_trade_with_martingale(client, high_profit_asset, live, base_bet, martingale, stop_loss, stop_profit)
            
            if not trade_executed and balance <= initial_balance - stop_loss:
                log.append(f"Stop Loss reached: ${initial_balance - balance:.2f}")
                live.update(update_ui("Stopped", high_profit_asset, "N/A", log[-1], balance=balance))
                break
            if trade_executed and balance >= initial_balance + stop_profit:
                log.append(f"Stop Profit reached: ${balance - initial_balance:.2f}")
                live.update(update_ui("Stopped", high_profit_asset, "N/A", log[-1], balance=balance))
                break
            
            elapsed = time.time() - start_time
            if elapsed < 180:
                wait_time = 180 - elapsed
                spinner = itertools.cycle(['🔍', '🔎', '🔬', '🔭'])
                for i in range(int(wait_time)):
                    balance = await client.get_balance()
                    log.append(f"Scanning for next SMC/ICT signal ({int(wait_time)-i}s)")
                    live.update(update_ui("Scanning", high_profit_asset, "N/A", log[-1], next(spinner), balance=balance))
                    await asyncio.sleep(1)
            if not trade_executed:
                log.append("No trade placed this cycle. Forcing next attempt...")
                live.update(update_ui("Idle", high_profit_asset, "N/A", log[-1], balance=balance))

        client.close()

# Execute
async def execute(argument):
    if argument == "smart_martingale_trade":
        await smart_martingale_trade()
    else:
        console.print("[red]Invalid option. Use 'help' for options.[/red]")

async def main():
    if len(sys.argv) != 2:
        console.print("[yellow]Please provide an option. Use 'help' for options.[/yellow]")
        return
    option = sys.argv[1]
    await execute(option)

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        console.print("[red]Closing program.[/red]")
    finally:
        loop.close()