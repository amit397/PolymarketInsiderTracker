# Quick Start

## Prerequisites
- **Python 3.12+**
- **Node.js 18+**

## Run the App

**Terminal 1 — Backend:**
```bash
cd backend
.\venv\Scripts\activate
uvicorn app.main:app --port 8000 --reload
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

Then open **http://localhost:3000** in your browser.

---

## First-Time Setup

### 1. Backend Setup

```bash
cd backend

# Create virtual environment (first time only)
python -m venv venv

# Activate it
.\venv\Scripts\activate        # Windows
# source venv/bin/activate     # Mac/Linux

# Install dependencies (first time only)
pip install -r requirements.txt

# Start the API server
uvicorn app.main:app --port 8000 --reload
```

The backend runs at **http://localhost:8000**.

> **Port already in use?** Run `netstat -ano | Select-String ":8000"` to find the PID, then `Stop-Process -Id <PID> -Force` to kill it.

## 2. Frontend Setup

Open a **second terminal**:

```bash
cd frontend

# Install dependencies (first time only)
npm install

# Start the dev server
npm run dev
```

The dashboard opens at **http://localhost:3000**.

## 3. Using the App

1. Open **http://localhost:3000** in your browser
2. Click **"Run Scan"** on the dashboard to scan recent Polymarket trades
3. The scan takes ~30-60 seconds (hitting live APIs)
4. Alerts with suspicion scores will appear in the feed
5. Click any alert to expand its factor breakdown
6. Click a wallet address to view its full profile

## Configuration (Optional)

No API keys are required — all Polymarket APIs are public. To enable wallet age detection, create `backend/.env`:

```
POLYGONSCAN_API_KEY=your_key_here
```

Get a free key at [polygonscan.com/apis](https://polygonscan.com/apis).

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/stats` | Dashboard statistics |
| GET | `/api/alerts` | All generated alerts |
| POST | `/api/scan` | Trigger a new scan |
| GET | `/api/wallet/{address}` | Wallet profile |
| GET | `/api/wallet/{address}/trades` | Wallet trade history |
| GET | `/api/markets/suspicious` | Markets with most alerts |

## Running Tests

```bash
cd backend
.\venv\Scripts\activate
pytest tests/ -v
```
