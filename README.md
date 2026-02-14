# 🔍 Polymarket Insider Trading Tracker

A web application that detects potentially suspicious trading activity on [Polymarket](https://polymarket.com) by analyzing publicly available trade data. The system computes a multi-factor **suspicion score** for each wallet and presents results through an interactive dashboard.

> **Disclaimer:** This tool is for informational and research purposes only. It does not accuse anyone of illegal activity. All data is sourced from public blockchains and APIs.

---

## How It Works

### Detection Logic

The tracker identifies wallets exhibiting patterns commonly associated with informed trading:

- **Fresh wallets** making large, concentrated bets
- **Unusually large trades** relative to market norms
- **Bets concentrated in a single topic** rather than diversified
- **Trades timed suspiciously close** to market resolution
- **Rapid price movement** in the trader's favor shortly after entry
- **Short-dated contract focus** — proactive scanning of markets resolving within 1–7 days, the highest-risk window for insider activity

Each wallet receives a **Suspicion Score (0–100)** computed from 5 weighted factors:

| Factor | Weight | What It Measures |
|--------|--------|------------------|
| Volume Anomaly | 30% | Trade size vs. market average (statistical outlier detection, min 10 trades) |
| Topic Concentration | 25% | How narrowly focused the wallet's bets are (HHI index) |
| Market Timing | 20% | Proximity of trade to market resolution (logarithmic decay, meaningful across 1h–30d) |
| Wallet Freshness | 15% | Age of wallet — newer wallets score higher |
| Rapid Profit | 10% | Price moved in wallet's favor within 24h of trade |

Alerts are only raised when score ≥ 50 **and** at least 2 individual factors are elevated.

### Validation

The scoring engine is calibrated against **known suspicious wallets** identified by the community (e.g., 0xafEe/AlphaRaccoon, bigwinner01) to ensure the detection logic produces meaningful results before going live.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.11+ / FastAPI |
| **Database** | SQLite (via aiosqlite) |
| **HTTP Client** | httpx (async) |
| **Frontend** | Next.js 14 (App Router) |
| **Charts** | Recharts |
| **Styling** | Vanilla CSS (dark theme) |

### Data Sources

| API | Purpose |
|-----|---------|
| [Gamma API](https://gamma-api.polymarket.com) | Market metadata (categories, resolution dates, volume) |
| [Data API](https://data-api.polymarket.com) | Historical trade data (maker, taker, size, timestamp) |
| [CLOB API](https://clob.polymarket.com) | Real-time prices and order books (requires API key) |
| [Polygonscan API](https://api.polygonscan.com) | Wallet age (first transaction date) |

---

## Project Structure

```
polymarket-insider-tracker/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app
│   │   ├── api/
│   │   │   ├── routes.py           # API endpoints
│   │   │   └── schemas.py          # Pydantic models
│   │   ├── core/
│   │   │   ├── config.py           # Settings & scoring weights
│   │   │   ├── database.py         # SQLite setup
│   │   │   └── models.py           # DB table definitions
│   │   └── services/
│   │       ├── gamma_client.py     # Gamma API client
│   │       ├── data_client.py      # Data API client
│   │       ├── clob_client.py      # CLOB API client
│   │       ├── polygonscan.py      # Wallet age lookup
│   │       ├── scanner.py          # Scanning orchestrator
│   │       └── scoring.py          # Suspicion score calculator
│   ├── tests/
│   ├── requirements.txt
│   └── data/                       # SQLite database file
├── frontend/
│   ├── src/
│   │   ├── app/                    # Next.js pages
│   │   ├── components/             # React components
│   │   └── lib/                    # API client
│   └── package.json
└── README.md
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/alerts` | GET | Recent alerts (filterable by `min_score`, `category`) |
| `/api/wallet/{address}` | GET | Wallet profile with score breakdown |
| `/api/wallet/{address}/trades` | GET | Paginated trade history |
| `/api/markets/suspicious` | GET | Markets ranked by avg suspicion score |
| `/api/markets/expiring` | GET | Markets resolving soon with suspicious trade counts (filterable by `hours`, `min_score`, `min_volume`) |
| `/api/stats` | GET | Global dashboard statistics |
| `/api/scan` | POST | Trigger a manual scan |

---

## Setup & Running

### Prerequisites
- Python 3.11+
- Node.js 18+
- Polygonscan API key (free tier: [polygonscan.com](https://polygonscan.com/apis))

### Backend
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env  # Add your POLYGONSCAN_API_KEY
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Running Tests
```bash
cd backend
python -m pytest tests/ -v

# Calibration test (requires internet)
python -m pytest tests/test_calibration.py -v --timeout=120
```

---

## Dashboard Preview

### Alert Feed (Home Page)
- Live feed of flagged wallets sorted by suspicion score
- Color-coded score badges (green → red)
- Reason tags: "Fresh Wallet", "Large Trade", "Timed Entry"
- Category and score filters
- Tab toggle between **All Alerts** and **Expiring Soon**

### Expiring Markets (Short-Dated Contracts)
- Dedicated view for markets resolving within 1–7 days
- Time horizon selector: 24h / 48h / 72h / 7 days
- Market cards with **live countdown timers** to resolution
- Suspicious trade count and top suspicion score per market
- Click to expand and see flagged wallets for each market
- Sorted by urgency (soonest-resolving first)

### Wallet Profile
- Overall score gauge with factor-by-factor breakdown
- Trade timeline with market annotations
- Category distribution donut chart
- Links to Polymarket and Polygonscan

---

## Roadmap

- [x] Detection logic design & scoring formula
- [ ] **Phase 1:** Data layer + scoring engine + calibration tests
- [ ] **Phase 2:** FastAPI backend + API endpoints (including `/api/markets/expiring`)
- [ ] **Phase 3:** Next.js dashboard + wallet profiles + short-dated contracts view
- [ ] **Future:** On-chain funding analysis, ML anomaly detection, WebSocket real-time alerts
