# 🤖 Gold Signal Bot

> **Automated trading signals for Gold Futures (GC=F)** with Telegram notifications.

Strategy: D1 trend analysis → H1 S/R levels → M15 breakout + volume confirmation.

## 🚀 Quick Start

```bash
# Clone & install
git clone https://github.com/rozbalovan/gold-signal-bot.git
cd gold-signal-bot
pip install -r requirements.txt

# Configure
cp .env.example .env
nano .env  # add your BOT_TOKEN and CHAT_ID

# Run
python gold_signal_bot.py
```

## 📊 Strategy

| Timeframe | Logic | Purpose |
|-----------|-------|---------|
| **D1** | EMA 20 | Trend direction filter |
| **H1** | 16-candle High/Low | S/R levels + range width |
| **M15** | Breakout + Volume >1.5x avg | Entry signal |

## 📈 Signal Format

```
🟢 GOLD SIGNAL — LONG
━━━━━━━━━━━━━━━━━
📈 Price: $2350.50
📊 Breakout: $2348.20
📐 Range: $2335.10 — $2348.20 (0.56%)
━━━━━━━━━━━━━━━━━
🐂 D1 EMA20: $2320.45 (BULL)
📊 Volume: ✅ >1.5x
━━━━━━━━━━━━━━━━━
🎯 TP: $2357.00
🛑 SL: $2343.00
📐 R:R: 1.67:1
━━━━━━━━━━━━━━━━━
💡 Signal #7
```

## ⚙️ Configuration

| Variable | Description |
|----------|-------------|
| `BOT_TOKEN` | Telegram bot token from @BotFather |
| `CHAT_ID` | Your Telegram user/chat ID |

## 🔧 Strategy Params (editable in code)

| Param | Default | Description |
|-------|---------|-------------|
| `TREND_PERIOD` | 20 | D1 EMA period |
| `SR_PERIOD` | 16 | H1 candles for range |
| `VOLUME_MULT` | 1.5 | Volume threshold multiplier |
| `COOLDOWN_MIN` | 120 | Minutes between signals |

## 📁 Files

```
gold-signal-bot/
├── gold_signal_bot.py   # Main bot
├── requirements.txt      # Dependencies
├── .env.example          # Config template
└── bot_state.json        # Auto-created (state persistence)
```

## 🛡️ Risk Warning

Trading futures carries significant risk. This bot provides signals — always validate on demo accounts before real trading. Past performance ≠ future results.

---

*Built by [@rozbalovan](https://github.com/rozbalovan)*
