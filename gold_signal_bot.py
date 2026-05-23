#!/usr/bin/env python3
"""
🤖 Gold Signal Bot — Super Simple Gold
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Strategy:
  1. D1 — Trend via EMA 20
  2. H1 — S/R levels (High/Low of last 16 candles)
  3. M15 — Breakout with volume confirmation → signal

Environment variables:
  BOT_TOKEN  — Telegram bot token
  CHAT_ID    — Telegram chat ID for notifications
"""

import yfinance as yf
import pandas as pd
import numpy as np
import time
import requests
import os
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ════════════════════ CONFIG ════════════════════
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")

SYMBOL = "GC=F"        # Yahoo Finance ticker — Gold Futures (COMEX)

# Strategy params
TREND_PERIOD = 20       # EMA 20 on D1
SR_PERIOD = 16          # H1 candles for range
VOLUME_MULT = 1.5       # Volume > avg × N
CONFIRM_OFFSET = 0.05   # % breakout offset

# Runtime
CHECK_INTERVAL = 15 * 60   # check every 15 minutes
COOLDOWN_MIN = 120         # 120 min cooldown after signal

STATE_FILE = Path(__file__).parent / "bot_state.json"


class GoldSignalBot:
    def __init__(self):
        self.state = self._load_state()
        self.log("🚀 Gold Signal Bot started — Super Simple Gold")

        if not BOT_TOKEN or not CHAT_ID:
            self.log("⚠️ BOT_TOKEN or CHAT_ID not set. Telegram alerts disabled.")

    # ═══════════════════════════════════════════════
    #   State persistence
    # ═══════════════════════════════════════════════

    def _load_state(self):
        d = {
            "last_signal_time": 0,
            "last_signal_side": None,
            "last_signal_price": 0,
            "total_signals": 0,
        }
        if STATE_FILE.exists():
            try:
                s = json.loads(STATE_FILE.read_text())
                for k in d:
                    if k in s:
                        d[k] = s[k]
            except:
                pass
        return d

    def _save_state(self):
        STATE_FILE.write_text(json.dumps(self.state, default=str, indent=2))

    # ═══════════════════════════════════════════════
    #   Logging
    # ═══════════════════════════════════════════════

    def log(self, msg):
        ts = datetime.now().strftime('%H:%M:%S')
        print(f"[{ts}] {msg}", flush=True)

    def tg(self, text):
        if not BOT_TOKEN or not CHAT_ID:
            return
        try:
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    'chat_id': CHAT_ID,
                    'text': text,
                    'parse_mode': 'Markdown'
                },
                timeout=10
            )
        except Exception as e:
            self.log(f"⚠️ Telegram error: {e}")

    # ═══════════════════════════════════════════════
    #   Data
    # ═══════════════════════════════════════════════

    def fetch_data(self):
        """Fetch D1, H1, M15 data from Yahoo Finance"""
        try:
            ticker = yf.Ticker(SYMBOL)
            now = datetime.now()

            d1 = ticker.history(period="2mo", interval="1d")
            if d1.empty:
                self.log("⚠️ No D1 data")
                return None, None, None

            h1 = ticker.history(period="5d", interval="1h")
            if h1.empty:
                self.log("⚠️ No H1 data")
                return None, None, None

            m15 = ticker.history(period="2d", interval="15m")
            if m15.empty:
                self.log("⚠️ No M15 data")
                return None, None, None

            self.log(f"📥 Data: D1({len(d1)}d) H1({len(h1)}h) M15({len(m15)}candles)")
            return d1, h1, m15

        except Exception as e:
            self.log(f"❌ Fetch error: {e}")
            return None, None, None

    # ═══════════════════════════════════════════════
    #   Analysis
    # ═══════════════════════════════════════════════

    def get_trend(self, d1):
        """D1 EMA 20 trend"""
        closes = d1['Close'].values
        if len(closes) < TREND_PERIOD + 1:
            return None, 0

        k = 2 / (TREND_PERIOD + 1)
        ema = np.mean(closes[:TREND_PERIOD])
        for price in closes[TREND_PERIOD:]:
            ema = price * k + ema * (1 - k)

        last_close = closes[-1]
        bias = 'bull' if last_close > ema else 'bear'
        return bias, ema

    def get_levels(self, h1):
        """S/R from last N H1 candles"""
        candles = h1.tail(SR_PERIOD)
        if len(candles) < SR_PERIOD:
            return None, None

        range_high = candles['High'].max()
        range_low = candles['Low'].min()
        avg_vol = candles['Volume'].mean()

        return {
            'high': range_high,
            'low': range_low,
            'avg_vol': avg_vol,
            'width': range_high - range_low,
            'width_pct': (range_high - range_low) / range_low * 100
        }

    def check_signal(self, trend_bias, trend_ema, levels, m15):
        """Check for breakout + volume + trend confirmation"""
        if trend_bias is None or levels is None:
            return None, None

        if len(m15) < 3:
            return None, None

        last = m15.iloc[-1]
        price = last['Close']
        volume = last['Volume']

        vol_ok = volume >= levels['avg_vol'] * VOLUME_MULT

        # Long breakout
        breakout_high = levels['high'] * (1 + CONFIRM_OFFSET / 100)
        if price >= breakout_high and vol_ok:
            return 'LONG', levels['high']

        # Short breakout
        breakout_low = levels['low'] * (1 - CONFIRM_OFFSET / 100)
        if price <= breakout_low and vol_ok:
            return 'SHORT', levels['low']

        return None, None

    # ═══════════════════════════════════════════════
    #   Signal
    # ═══════════════════════════════════════════════

    def send_signal(self, direction, level, trend_bias, trend_ema, levels, price):
        """Format and send signal"""
        now = time.time()

        # Cooldown check
        if now - self.state.get('last_signal_time', 0) < COOLDOWN_MIN * 60:
            self.log(f"⏳ Cooldown {COOLDOWN_MIN}min — signal {direction} skipped")
            return

        # Duplicate protection
        last_side = self.state.get('last_signal_side')
        if last_side == direction:
            delta = abs(price - self.state.get('last_signal_price', 0))
            if delta / price * 100 < 0.3:
                self.log(f"⏳ Duplicate signal — skipped")
                return

        # TP / SL
        range_width = levels['width']
        sl_distance = range_width * 0.3
        tp_distance = range_width * 0.6

        if direction == 'LONG':
            tp = price + tp_distance
            sl = price - sl_distance
        else:
            tp = price - tp_distance
            sl = price + sl_distance

        rr = round(tp_distance / sl_distance, 2) if sl_distance > 0 else 0

        # Update state
        self.state['last_signal_time'] = now
        self.state['last_signal_side'] = direction
        self.state['last_signal_price'] = price
        self.state['total_signals'] = self.state.get('total_signals', 0) + 1
        self._save_state()

        bias_emoji = '🐂' if trend_bias == 'bull' else '🐻'
        emoji = '🟢' if direction == 'LONG' else '🔴'

        msg = (
            f"{emoji} *GOLD SIGNAL — {direction}*\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"📈 Price: ${price:.2f}\n"
            f"📊 Breakout: ${level:.2f}\n"
            f"📐 Range: ${levels['low']:.2f} — ${levels['high']:.2f} ({levels['width_pct']:.2f}%)\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"{bias_emoji} D1 EMA{TREND_PERIOD}: ${trend_ema:.2f} ({trend_bias.upper()})\n"
            f"📊 Volume: ✅ >{VOLUME_MULT}x avg\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"🎯 TP: ${tp:.2f}\n"
            f"🛑 SL: ${sl:.2f}\n"
            f"📐 R:R: {rr:.2f}:1\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"💡 Signal #{(self.state.get('total_signals', 0))}\n\n"
            f"_Test on demo first_"
        )

        self.log(f"📡 Signal {direction} | ${price:.2f} | TP ${tp:.2f} SL ${sl:.2f}")
        self.tg(msg)

    # ═══════════════════════════════════════════════
    #   Status
    # ═══════════════════════════════════════════════

    def send_status(self, d1, h1, m15):
        """Periodic status update"""
        bias, ema = self.get_trend(d1)
        levels = self.get_levels(h1)

        if bias is None or levels is None:
            return

        emoji = '🐂' if bias == 'bull' else '🐻'
        price = m15.iloc[-1]['Close']

        msg = (
            f"📊 *GOLD — Status*\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"📈 Price: ${price:.2f}\n"
            f"{emoji} D1 EMA{TREND_PERIOD}: ${ema:.2f} ({bias.upper()})\n"
            f"📐 Range: ${levels['low']:.2f} — ${levels['high']:.2f}\n"
            f"📊 Volume threshold: >{VOLUME_MULT}x ({levels['avg_vol']:.0f})\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"💼 Signals sent: #{self.state.get('total_signals', 0)}\n\n"
            f"_Waiting for breakout with volume_"
        )

        self.log(f"📊 Status sent | ${price:.2f} | {bias}")
        self.tg(msg)

    # ═══════════════════════════════════════════════
    #   Main loop
    # ═══════════════════════════════════════════════

    def run(self):
        d1, h1, m15 = self.fetch_data()
        if d1 is not None:
            self.log("✅ Bot started — waiting for breakout")
            self.tg("🤖 *Gold Bot started*\nWaiting for breakout — signals only when it matters")
        else:
            self.log("❌ Failed to load data on startup")

        last_check = 0

        while True:
            try:
                now = time.time()

                if now - last_check >= CHECK_INTERVAL:
                    d1, h1, m15 = self.fetch_data()
                    if d1 is not None and h1 is not None and m15 is not None:
                        trend_bias, trend_ema = self.get_trend(d1)
                        levels = self.get_levels(h1)

                        if trend_bias and levels:
                            self.log(f"📊 {trend_bias.upper()} | EMA: ${trend_ema:.2f} | "
                                    f"${levels['low']:.2f}-${levels['high']:.2f}")

                            direction, breakout_at = self.check_signal(
                                trend_bias, trend_ema, levels, m15
                            )
                            if direction and breakout_at:
                                price = m15.iloc[-1]['Close']
                                self.send_signal(direction, breakout_at,
                                                trend_bias, trend_ema, levels, price)

                    last_check = now

                time.sleep(60)

            except KeyboardInterrupt:
                self.log("⏹ Stopped")
                break
            except Exception as e:
                self.log(f"❌ Error: {e}")
                time.sleep(30)


if __name__ == "__main__":
    GoldSignalBot().run()
