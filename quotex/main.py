import sys
import time
import asyncio
import itertools
from quotexapi.stable_api import Quotex
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.table import Table
from indicators import calculate_ema, calculate_rsi, calculate_macd, calculate_bollinger_bands, calculate_atr, calculate_adx
from patterns import detect_patterns
from candle_psychology import analyze_candle_psychology
from smc import analyze_smc
from ict import analyze_ict
from price_action import analyze_price_action  # New addition

console = Console()
trade_count = 0
log = []

def get_user_input():
    email = console.input("[bold neon_green]Enter Quotex Email: [/]")
    password = console.input("[bold neon_green]Enter Quotex Password: [/]")
    base_bet = float(console.input("[bold electric_blue]Enter Base Bet ($): [/]"))
    martingale = float(console.input("[bold electric_blue]Enter Martingale Multiplier (e.g., 2.0): [/]"))
    stop_loss = float(console.input("[bold hot_pink]Enter Stop Loss ($): [/]"))
    stop_profit = float(console.input("[bold neon_green]Enter Stop Profit ($): [/]"))
    return email, password, base_bet, martingale, stop_loss, stop_profit

def update_ui(status, assets_data, selected_asset, log_entry, spinner="", balance=0):
    table = Table.grid(expand=True)
    table.add_column(style="bold white on #0a0a23")
    table.add_column(style="bold white on #0a0a23")

    header = Text("✨ Quantum SMC/ICT Trading Matrix ✨", style="bold neon_green gradient(#00ffff #ff00ff)", justify="center")
    table.add_row("", header)

    status_color = {"Idle": "neon_green", "Trading": "electric_blue", "Scanning": "yellow", "Waiting": "cyan", "Analyzed": "magenta", "Stopped": "hot_pink", "Failed": "red"}.get(status, "white")
    status_display = f"[bold {status_color} underline]{status.upper()}[/]"
    table.add_row(Panel(f"⚡ Status: {status_display}", border_style=f"bold {status_color}", box=rich.box.MINIMAL, padding=(0, 1)))

    asset_signals = ""
    for asset, data in assets_data.items():
        confidence = data["confidence"]
        signal_bar = "█" * int(confidence / 5) + " " * (20 - int(confidence / 5))
        signal_color = "neon_green" if confidence >= 90 else "electric_blue" if confidence >= 70 else "hot_pink"
        asset_signals += f"[bold magenta]{asset}[/]: [{signal_color}]{signal_bar}[/] {confidence:.1f}%\n"
    signal_panel = Panel(Text(f"📡 Signals:\n{asset_signals.strip()}", style="white on #0a0a23"), border_style="bold neon_green", box=rich.box.MINIMAL, padding=(0, 1))
    table.add_row(signal_panel)

    asset_panel = Panel(Text(f"🎯 Selected: [bold magenta]{selected_asset or 'None'}[/]", style="white on #0a0a23"), border_style="bold magenta", box=rich.box.MINIMAL, padding=(0, 1))
    balance_panel = Panel(Text(f"💸 Balance: [bold cyan]${balance:.2f}[/]", style="white on #0a0a23"), border_style="bold cyan", box=rich.box.MINIMAL, padding=(0, 1))
    table.add_row(asset_panel, balance_panel)

    selected_data = assets_data.get(selected_asset, {"direction": "N/A", "pattern": "N/A", "kill_zone": "N/A", "pot": "N/A"})
    analysis = f"{selected_data['direction']} | {selected_data['pattern']} | {selected_data['kill_zone']} | {selected_data['pot']}"
    analysis_panel = Panel(Text(f"🔮 Analysis: [yellow]{analysis}[/]", style="white on #0a0a23"), border_style="bold yellow", box=rich.box.MINIMAL, padding=(0, 1))
    log_panel = Panel(Text(f"🔔 Log: {log_entry} {spinner}", style="white on #0a0a23"), border_style="bold electric_blue", box=rich.box.MINIMAL, padding=(0, 1))
    table.add_row(analysis_panel, log_panel)

    return Panel(table, border_style="bold neon_green gradient(#ff00ff #00ffff #ffff00)", box=rich.box.DOUBLE, padding=(1, 2), title="[bold electric_blue blinking]Quantum Matrix[/]", title_align="left", subtitle="[bold magenta]v1.0[/]", subtitle_align="right", style="on #0a0a23", width=90)

async def login_and_fetch_assets(client, live):
    try:
        check_connect = await client.test_connection()
        if not check_connect:
            log.append("Connection failed")
            live.update(update_ui("Failed", {}, None, log[-1]))
            return None
        
        log.append("Logged in successfully!")
        
        with Progress(SpinnerColumn(), "[progress.description]{task.description}", BarColumn(), "[progress.percentage]{task.percentage:>3.0f}%", console=console) as progress:
            all_assets = await client.get_all_assets()
            task = progress.add_task("[cyan]Fetching Quantum Signals...", total=len(all_assets))
            open_assets = {}
            for i, asset_code in enumerate(all_assets):
                asset_info = await client.get_asset(asset_code)
                if asset_info and asset_info.get("is_open", False):
                    payout = await client.get_payout_by_asset(asset_code)
                    if payout and "turbo" in payout:
                        open_assets[asset_code] = payout["turbo"]["profit"]
                progress.update(task, advance=1)
                log.append(f"Scanning assets ({i+1}/{len(all_assets)})")
                live.update(update_ui("Fetching", {}, None, log[-1]))
                await asyncio.sleep(0.05)
            
            top_assets = dict(sorted(open_assets.items(), key=lambda x: x[1], reverse=True)[:3])
            log.append(f"Top Assets Loaded: {', '.join(f'{k} ({v}%)' for k, v in top_assets.items())}")
            live.update(update_ui("Idle", {k: {"confidence": 0, "direction": "N/A", "pattern": "N/A", "kill_zone": "N/A", "pot": "N/A"} for k in top_assets}, None, log[-1]))
        return top_assets
    except Exception as e:
        log.append(f"Asset fetch error: {str(e)}")
        live.update(update_ui("Failed", {}, None, log[-1]))
        return None

async def analyze_assets(client, assets, live):
    tasks = [analyze_single_asset(client, asset, live) for asset in assets]
    results = await asyncio.gather(*tasks)
    return dict(zip(assets.keys(), results))

async def analyze_single_asset(client, asset, live):
    try:
        candles = await client.get_candle(asset, 60, 120)
        if not candles or len(candles) < 50:
            return {"direction": None, "confidence": 0, "pattern": "N/A", "kill_zone": "N/A", "pot": "N/A"}
        
        ema_short = calculate_ema(candles, 10)
        ema_long = calculate_ema(candles, 50)
        rsi = calculate_rsi(candles)
        macd_line, signal_line, histogram = calculate_macd(candles)
        upper_bb, sma_bb, lower_bb, bandwidth = calculate_bollinger_bands(candles)
        atr = calculate_atr(candles)
        adx = calculate_adx(candles)
        latest_close = candles[-1]["close"]
        current_time = candles[-1]["time"]
        
        psych = analyze_candle_psychology(candles)
        smc = analyze_smc(candles)
        ict = analyze_ict(candles, current_time)
        price_action = analyze_price_action(candles)  # Enhanced price action
        psych_pattern, psych_confidence = detect_patterns(candles)
        
        confidence = 0
        direction = None
        
        # Technical Indicators
        if latest_close > ema_short > ema_long:
            confidence += 10
            direction = "call"
        elif latest_close < ema_short < ema_long:
            confidence += 10
            direction = "put"
        
        if rsi < 30 and direction == "call":
            confidence += 8
        elif rsi > 70 and direction == "put":
            confidence += 8
        
        if macd_line > signal_line and histogram > 0 and direction == "call":
            confidence += 10
        elif macd_line < signal_line and histogram < 0 and direction == "put":
            confidence += 10
        
        if latest_close < upper_bb and direction == "call" and bandwidth > 0.015:
            confidence += 8
        elif latest_close > lower_bb and direction == "put" and bandwidth > 0.015:
            confidence += 8
        
        if adx > 25:
            confidence += 8
        
        if atr > sma_bb * 0.005:
            confidence += 8
        
        # Candle Psychology
        if psych["trend_persistence"] > 50 and direction == "call":
            confidence += min(15, psych["trend_persistence"] * 0.3)
        elif psych["trend_persistence"] < -50 and direction == "put":
            confidence += min(15, abs(psych["trend_persistence"]) * 0.3)
        
        if psych["reversal_strength"] > 70:
            if direction == "call" and psych["sentiment"] == "bullish":
                confidence += min(10, psych["reversal_strength"] * 0.15)
            elif direction == "put" and psych["sentiment"] == "bearish":
                confidence += min(10, psych["reversal_strength"] * 0.15)
        
        if psych["volatility_clustering"] > 60:
            confidence += min(8, psych["volatility_clustering"] * 0.15)
        
        if psych["exhaustion_signal"] > 80:
            if direction == "call" and psych["sentiment"] == "bullish":
                confidence += min(10, psych["exhaustion_signal"] * 0.15)
            elif direction == "put" and psych["sentiment"] == "bearish":
                confidence += min(10, psych["exhaustion_signal"] * 0.15)
        
        if psych["fractal_momentum"] > 1.5 and direction == "call":
            confidence += min(8, psych["fractal_momentum"] * 3)
        elif psych["fractal_momentum"] < -1.5 and direction == "put":
            confidence += min(8, abs(psych["fractal_momentum"]) * 3)
        
        if psych["mtf_correlation"] > 70 and direction == "call":
            confidence += min(10, psych["mtf_correlation"] * 0.15)
        elif psych["mtf_correlation"] < -70 and direction == "put":
            confidence += min(10, abs(psych["mtf_correlation"]) * 0.15)
        
        if psych["psychological_pressure"] > 60:
            confidence += min(8, psych["psychological_pressure"] * 0.15)
        
        if psych["candle_entropy"] > 70:
            confidence += 8
        
        # SMC
        ob = smc["order_block"]
        if ob["level"] and ob["type"] == "bullish" and direction == "call" and abs(latest_close - ob["level"]) < atr:
            confidence += min(15, ob["confidence"] * 0.2)
        elif ob["level"] and ob["type"] == "bearish" and direction == "put" and abs(latest_close - ob["level"]) < atr:
            confidence += min(15, ob["confidence"] * 0.2)
        
        liq = smc["liquidity_grab"]
        if liq["direction"] == "bullish" and direction == "call":
            confidence += min(10, liq["confidence"] * 0.15)
        elif liq["direction"] == "bearish" and direction == "put":
            confidence += min(10, liq["confidence"] * 0.15)
        
        imb = smc["imbalance"]
        if imb["direction"] == "bullish" and direction == "call" and latest_close < imb["level"]:
            confidence += min(10, imb["confidence"] * 0.15)
        elif imb["direction"] == "bearish" and direction == "put" and latest_close > imb["level"]:
            confidence += min(10, imb["confidence"] * 0.15)
        
        # ICT
        fvg = ict["fair_value_gap"]
        if fvg["detected"] and direction == "call" and latest_close < fvg["level"]:
            confidence += min(15, fvg["probability"] * 0.2)
        elif fvg["detected"] and direction == "put" and latest_close > fvg["level"]:
            confidence += min(15, fvg["probability"] * 0.2)
        
        kz = ict["kill_zone"]
        if kz["active"] and direction:
            confidence += min(10, kz["confidence"] * 0.15)
        
        pot = ict["power_of_three"]
        if pot["pattern"] == "Bullish Power of Three" and direction == "call":
            confidence += min(10, pot["confidence"] * 0.15)
        elif pot["pattern"] == "Bearish Power of Three" and direction == "put":
            confidence += min(10, pot["confidence"] * 0.15)
        
        # Patterns
        if "bullish" in psych_pattern.lower() or "hammer" in psych_pattern.lower() or "morning" in psych_pattern.lower():
            if direction == "call":
                confidence += min(15, psych_confidence * 0.2)
        elif "bearish" in psych_pattern.lower() or "shooting" in psych_pattern.lower() or "evening" in psych_pattern.lower():
            if direction == "put":
                confidence += min(15, psych_confidence * 0.2)

        # Price Action
        supply = price_action["supply_zone"]
        demand = price_action["demand_zone"]
        if direction == "call" and latest_close > demand["level"] and abs(latest_close - demand["level"]) < atr:
            confidence += min(15, demand["strength"] * 0.2)
        elif direction == "put" and latest_close < supply["level"] and abs(latest_close - supply["level"]) < atr:
            confidence += min(15, supply["strength"] * 0.2)
        
        if price_action["breakout_power"] > 50 and direction == "call":
            confidence += min(15, price_action["breakout_power"] * 0.2)
        elif price_action["breakout_power"] > 50 and direction == "put":
            confidence += min(15, price_action["breakout_power"] * 0.2)
        
        trend = price_action["trendline_dynamics"]
        if trend["slope"] > 0 and trend["strength"] > 70 and direction == "call":
            confidence += min(10, trend["strength"] * 0.15)
        elif trend["slope"] < 0 and trend["strength"] > 70 and direction == "put":
            confidence += min(10, trend["strength"] * 0.15)
        
        liq_sweep = price_action["liquidity_sweep"]
        if liq_sweep["type"] == "bullish" and direction == "call" and abs(latest_close - liq_sweep["level"]) < atr:
            confidence += min(15, liq_sweep["confidence"] * 0.2)
        elif liq_sweep["type"] == "bearish" and direction == "put" and abs(latest_close - liq_sweep["level"]) < atr:
            confidence += min(15, liq_sweep["confidence"] * 0.2)
        
        if price_action["price_rejection_intensity"] > 70:
            if direction == "call" and latest_close > price_action["volatility_adjusted_pivot"]:
                confidence += min(10, price_action["price_rejection_intensity"] * 0.15)
            elif direction == "put" and latest_close < price_action["volatility_adjusted_pivot"]:
                confidence += min(10, price_action["price_rejection_intensity"] * 0.15)
        
        if price_action["consolidation_breakout_potential"] > 80 and direction:
            confidence += min(10, price_action["consolidation_breakout_potential"] * 0.15)
        
        if price_action["impulse_wave_strength"] > 5 and direction == "call":
            confidence += min(10, price_action["impulse_wave_strength"] * 2)
        elif price_action["impulse_wave_strength"] > 5 and direction == "put":
            confidence += min(10, price_action["impulse_wave_strength"] * 2)
        
        if price_action["fibonacci_confluence"] > 80 and direction:
            confidence += 10
        
        if price_action["momentum_divergence"] > 50:
            if direction == "call" and latest_close > price_action["volatility_adjusted_pivot"]:
                confidence -= 10  # Reduce confidence for bullish divergence
            elif direction == "put" and latest_close < price_action["volatility_adjusted_pivot"]:
                confidence -= 10  # Reduce confidence for bearish divergence

        confidence = min(100, confidence)
        return {
            "direction": direction,
            "confidence": confidence,
            "pattern": psych_pattern,
            "kill_zone": kz["type"] if kz["active"] else "No Kill Zone",
            "pot": pot["pattern"] if pot["pattern"] else "No POT"
        }
    except Exception as e:
        log.append(f"Analysis error for {asset}: {str(e)}")
        live.update(update_ui("Idle", {asset: {"confidence": 0, "direction": "N/A", "pattern": "N/A", "kill_zone": "N/A", "pot": "N/A"}}, None, log[-1]))
        return {"direction": None, "confidence": 0, "pattern": "N/A", "kill_zone": "N/A", "pot": "N/A"}

async def place_trade_with_martingale(client, assets, live, base_bet, martingale, stop_loss, stop_profit):
    global trade_count
    amount = base_bet
    attempt = 1
    total_profit = 0
    cycle_start = time.time()
    trade_executed = False
    assets_data = {asset: {"confidence": 0, "direction": "N/A", "pattern": "N/A", "kill_zone": "N/A", "pot": "N/A"} for asset in assets}
    
    while time.time() - cycle_start < 180:
        try:
            balance = await client.get_balance()
            assets_data = await analyze_assets(client, assets, live)
            
            best_asset = max(assets_data.items(), key=lambda x: x[1]["confidence"] if x[1]["direction"] else 0, default=(None, {"confidence": 0}))
            best_confidence = best_asset[1]["confidence"]
            best_direction = best_asset[1]["direction"]
            selected_asset = best_asset[0]
            
            if best_direction and best_confidence >= 90:
                log.append(f"Executing {best_direction.upper()} trade on {selected_asset} @ ${amount:.2f} (Conf: {best_confidence:.1f}%)")
                live.update(update_ui("Trading", assets_data, selected_asset, log[-1], balance=balance))
                status, result = await client.buy_and_check_win(amount, selected_asset, best_direction, 60)
                trade_executed = True
            elif not trade_executed and time.time() - cycle_start > 150 and best_direction and best_confidence >= 90:
                log.append(f"Fallback Trade {best_direction.upper()} on {selected_asset} @ ${amount:.2f} (Conf: {best_confidence:.1f}%)")
                live.update(update_ui("Trading", assets_data, selected_asset, log[-1], balance=balance))
                status, result = await client.buy_and_check_win(amount, selected_asset, best_direction, 60)
                trade_executed = True
            else:
                spinner = itertools.cycle(['🌌', '🌠', '💫', '✨'])
                remaining = int(180 - (time.time() - cycle_start))
                log.append(f"Scanning quantum signals ({remaining}s)")
                live.update(update_ui("Scanning", assets_data, None, log[-1], next(spinner), balance=balance))
                await asyncio.sleep(1)
                continue
            
            if not status:
                log.append(f"Trade failed: {result}")
                live.update(update_ui("Idle", assets_data, selected_asset, log[-1], balance=balance))
                return False
            
            spinner = itertools.cycle(['⚡', '🔋', '🌩️', '💥'])
            for i in range(60):
                log[-1] = f"Trade executing ({60-i}s)"
                live.update(update_ui("Waiting", assets_data, selected_asset, log[-1], next(spinner), balance=balance))
                await asyncio.sleep(1)
            
            win = result.get("win", False)
            profit = result.get("profit", 0)
            total_profit += profit
            balance = await client.get_balance()
            
            if win:
                log.append(f"🎉 WIN! Profit: ${profit:.2f}")
                trade_count += 1
                live.update(update_ui("Idle", assets_data, selected_asset, log[-1], balance=balance))
                if total_profit >= stop_profit:
                    log.append(f"Quantum Profit achieved: ${total_profit:.2f}")
                    live.update(update_ui("Stopped", assets_data, selected_asset, log[-1], balance=balance))
                    return True
                return True
            else:
                log.append(f"❌ LOSS! Loss: ${profit:.2f}")
                amount *= martingale
                trade_count += 1
                attempt += 1
                if -total_profit >= stop_loss:
                    log.append(f"Quantum Loss limit hit: ${-total_profit:.2f}")
                    live.update(update_ui("Stopped", assets_data, selected_asset, log[-1], balance=balance))
                    return False
                if attempt > 3:
                    log.append("Max quantum attempts reached.")
                else:
                    log.append(f"Quantum escalation: Next @ ${amount:.2f}")
                live.update(update_ui("Idle", assets_data, selected_asset, log[-1], balance=balance))
                return False
        except Exception as e:
            log.append(f"Trade error: {str(e)}")
            live.update(update_ui("Idle", assets_data, selected_asset, log[-1], balance=balance))
            return False
    
    if not trade_executed:
        try:
            assets_data = await analyze_assets(client, assets, live)
            best_asset = max(assets_data.items(), key=lambda x: x[1]["confidence"] if x[1]["direction"] else 0, default=(None, {"confidence": 0}))
            best_confidence = best_asset[1]["confidence"]
            best_direction = best_asset[1]["direction"]
            selected_asset = best_asset[0]
            
            if best_direction and best_confidence >= 90:
                log.append(f"Forced Trade {best_direction.upper()} on {selected_asset} @ ${amount:.2f} (Conf: {best_confidence:.1f}%)")
                live.update(update_ui("Trading", assets_data, selected_asset, log[-1], balance=balance))
                status, result = await client.buy_and_check_win(amount, selected_asset, best_direction, 60)
                if status:
                    win = result.get("win", False)
                    profit = result.get("profit", 0)
                    total_profit += profit
                    balance = await client.get_balance()
                    log.append(f"Forced Trade {'WIN' if win else 'LOSS'}: ${profit:.2f}")
                    live.update(update_ui("Idle", assets_data, selected_asset, log[-1], balance=balance))
                    return win
                else:
                    log.append("Forced trade failed")
                    live.update(update_ui("Idle", assets_data, selected_asset, log[-1], balance=balance))
                    return False
            else:
                log.append("No quantum signal ≥90% for forced trade")
                live.update(update_ui("Idle", assets_data, None, log[-1], balance=balance))
                return False
        except Exception as e:
            log.append(f"Forced trade error: {str(e)}")
            live.update(update_ui("Idle", assets_data, None, log[-1], balance=balance))
            return False

async def smart_martingale_trade():
    email, password, base_bet, martingale, stop_loss, stop_profit = get_user_input()
    client = Quotex(email=email, password=password, lang="pt")
    
    with Live(update_ui("Idle", {}, None, "Initializing Quantum SMC/ICT Matrix...", balance=0), refresh_per_second=20, console=console) as live:
        top_assets = await login_and_fetch_assets(client, live)
        if not top_assets:
            return
        
        initial_balance = await client.get_balance()
        while True:
            balance = await client.get_balance()
            trade_executed = await place_trade_with_martingale(client, top_assets, live, base_bet, martingale, stop_loss, stop_profit)
            
            if not trade_executed and balance <= initial_balance - stop_loss:
                log.append(f"Quantum Loss limit hit: ${initial_balance - balance:.2f}")
                live.update(update_ui("Stopped", {k: {"confidence": 0, "direction": "N/A", "pattern": "N/A", "kill_zone": "N/A", "pot": "N/A"} for k in top_assets}, None, log[-1], balance=balance))
                break
            if trade_executed and balance >= initial_balance + stop_profit:
                log.append(f"Quantum Profit achieved: ${balance - initial_balance:.2f}")
                live.update(update_ui("Stopped", {k: {"confidence": 0, "direction": "N/A", "pattern": "N/A", "kill_zone": "N/A", "pot": "N/A"} for k in top_assets}, None, log[-1], balance=balance))
                break
            
            elapsed = time.time() - (time.time() - 180)
            if elapsed < 180:
                wait_time = 180 - elapsed
                spinner = itertools.cycle(['🌌', '🌠', '💫', '✨'])
                for i in range(int(wait_time)):
                    balance = await client.get_balance()
                    log.append(f"Preparing quantum cycle ({int(wait_time)-i}s)")
                    live.update(update_ui("Scanning", {k: {"confidence": 0, "direction": "N/A", "pattern": "N/A", "kill_zone": "N/A", "pot": "N/A"} for k in top_assets}, None, log[-1], next(spinner), balance=balance))
                    await asyncio.sleep(1)

async def execute(argument):
    if argument == "smart_martingale_trade":
        await smart_martingale_trade()
    else:
        console.print("[red]Invalid option. Use 'help' for options.[/red]")

async def main():
    if len(sys.argv) != 2:
        console.print("[yellow]Please test with: python main.py smart_martingale_trade[/yellow]")
        return
    option = sys.argv[1]
    await execute(option)

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        console.print("[red]Quantum Matrix shutdown.[/red]")
    finally:
        loop.close()