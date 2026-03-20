# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Flask-based cryptocurrency market analysis platform running on port 6969. Provides real-time analysis of BTC/altcoins using EMA-based indicators, AHR999, MVRV, and BTC dominance data. UI and code comments are primarily in Chinese.

## Commands

### Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # configure API keys
```

### Run
```bash
./start.sh        # start app.py + telegram_alert.py as background processes
./stop.sh         # stop both processes
python3 app.py    # run Flask dev server directly (port 6969)
```

### Logs
```
logs/app.log
logs/telegram_alert.log
```

No test suite or linter configured.

## Architecture

### Core Files
- **`app.py`** — Flask entry point. Initializes routes and spawns a background daemon thread that refreshes AHR999, MVRV, and BTCDOM caches every hour.
- **`modules/routes.py`** — All HTTP endpoints (7 routes: `/`, `/get_chart`, `/get_market_trends`, `/get_dashboard`, `/get_ahr999`, `/get_mvrv`, `/get_btc_dominance`, `/get_price_alerts`).
- **`modules/trading_analysis.py`** — Core calculation engine (~974 lines). Contains `KlineBot` class plus standalone functions for each indicator.
- **`telegram_alert.py`** — Separate background process. Monitors BTC/ETH/SOL every 5 minutes and sends Telegram notifications on MA line crossings. Logs alerts to `telegram_alert.json`.
- **`templates/`** — Jinja2 templates. `layout.html` is the shell; `partials/` contains modular components including `scripts.html` (72KB JS with Lightweight Charts v4) and `styles.html` (40KB CSS).

### MA Line System (Key Domain Logic)
The platform uses a custom EMA-derived band system in `KlineBot`:
- `MA2 = (MA30 + MA72) / 2` — trend centerline
- `MA3 = MA2 × 1.1` — uptrend line (light green)
- `MA4 = MA2 × 1.2` — strong trend (dark green)
- `MA5 = MA2 × 0.9` — downtrend line (light red)
- `MA6 = MA2 × 0.8` — super downtrend (dark red)

### External API Dependencies
| API | Purpose | Notes |
|-----|---------|-------|
| Binance REST | K-line data | 4 fallback domains; paginates up to 4000 candles |
| CoinGecko | Recent BTCDOM market cap (last 365d) | Requires `COINGECKO_API_KEY` |
| CryptoCompare | Historical BTCDOM data (1–4 years) | Normalized against CoinGecko overlap |
| BGeometrics | MVRV ratio | Cached 3600s |
| Telegram Bot API | Price alerts | Requires `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |

### Caching
In-memory cache with 3600s TTL for AHR999, MVRV, and BTCDOM. Cache is pre-warmed on startup via the background thread in `app.py`.

### Required Environment Variables (`.env`)
```
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
TELEGRAM_THREAD_ID=   # optional, for group chat topics
COINGECKO_API_KEY=
```
