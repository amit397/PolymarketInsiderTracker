# Polymarket Insider Tracker — 7-Issue Fix Plan (v2)

> Governed by Global Agent Rules §3 (Coding Standards), §4 (Task Execution), §8 (Quality Gates).
> Skills utilized: `frontend-design` (whale sort UI, about page polish), `vercel-react-best-practices` (React patterns for sorting state).

---

## 1. About Page Factor Titles Missing

**Root Cause:** [page.js](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/frontend/src/app/page.js) references `FACTOR_LABELS.f_fresh` etc., but [utils.js](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/frontend/src/lib/utils.js) defines keys as `volume_anomaly`, [topic_concentration](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/backend/app/services/scoring.py#332-335), etc. — **none match**, so every title is `undefined`. Additionally, only 5 factors shown; backend has 6.

### Changes

#### [MODIFY] [utils.js](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/frontend/src/lib/utils.js)

Align `FACTOR_LABELS` keys to the backend's 6-factor system ([win_rate_anomaly](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/backend/app/services/scoring.py#42-68), [bet_concentration](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/backend/app/services/scoring.py#70-87), [timing_signal](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/backend/app/services/scoring.py#89-112), [entry_price_edge](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/backend/app/services/scoring.py#114-139), [account_pattern](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/backend/app/services/scoring.py#141-194), [position_size_signal](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/backend/app/services/scoring.py#196-236)).

#### [MODIFY] [page.js (about)](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/frontend/src/app/about/page.js)

Use correct keys from `FACTOR_LABELS`, add 6th card (Position Size Signal), correct all weights, add brief justification for each weight.

---

## 2 & 3. Risk Score Weight Reconciliation

**Problem:** Three conflicting weight sets (README vs about page vs backend). Backend is source of truth.

### Weight Justifications

| Factor | Weight | Why |
|--------|--------|-----|
| **Position Size Signal** | 25% | Strongest insider signal. Large USDC on low-probability outcomes = high conviction from foreknowledge. SEC research shows abnormal position sizing is the most predictive informed-trading feature. |
| **Account Pattern** | 20% | Fresh single-purpose wallets are #2 insider hallmark — throwaway wallets avoid identity linkage. |
| **Win Rate Anomaly** | 15% | Above-random win rate suggests information advantage; confidence-weighted for small samples. |
| **Bet Concentration** | 15% | Insiders concentrate on 1-2 markets they have info on, unlike diversified traders. |
| **Entry Price Edge** | 15% | Buying winners at extreme undervalued prices (YES at $0.05) = foreknowledge smoking gun. |
| **Timing Signal** | 10% | Lower weight since legitimate traders also time entries near resolution. |

### Changes

#### [MODIFY] [README.md](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/README.md)

Update factor table to 6-factor system with correct weights and justification column.

#### [MODIFY] [page.js (about)](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/frontend/src/app/about/page.js)

Add justification text to each [FactorCard](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/frontend/src/app/about/page.js#89-104).

---

## 4. Database Persistence — Dual Approach (Option B + C)

**Root Cause:** SQLite is file-based; ephemeral platforms lose it on restart.

### Approach: JSON workaround now + Supabase infrastructure for future

#### Phase 1 — JSON Export/Import (immediate workaround)

##### [MODIFY] [routes.py](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/backend/app/api/routes.py)

Add two admin endpoints:
- `GET /api/admin/export` — dumps all tables (wallets, alerts, trades, markets) as JSON
- `POST /api/admin/import` — restores from JSON payload. Uses `INSERT OR REPLACE` for idempotency (§5 Idempotency Requirement).

#### Phase 2 — Supabase Infrastructure Setup

##### [NEW] [supabase_config.py](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/backend/app/core/supabase_config.py)

Configuration module for Supabase connection. Reads `SUPABASE_URL` and `SUPABASE_KEY` from env vars (§2 Credential Safety — no hardcoded secrets).

##### [MODIFY] [.env.example](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/backend/.env.example)

Add `SUPABASE_URL` and `SUPABASE_KEY` placeholders.

##### [NEW] [SUPABASE_MIGRATION.md](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/backend/SUPABASE_MIGRATION.md)

Migration guide documenting:
- SQL schema to create in Supabase dashboard (DDL from [database.py](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/backend/app/core/database.py))
- How to swap [database.py](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/backend/app/core/database.py) to use `asyncpg` / `supabase-py`
- Env var configuration steps

> [!IMPORTANT]
> The Supabase migration is **infrastructure setup only** — the actual [database.py](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/backend/app/core/database.py) swap is documented but not applied. This avoids breaking the working local SQLite setup while giving you everything needed to flip the switch.

---

## 5. Win Rate & Profit Always 0

**Root Cause:**
1. PnL only computes for resolved markets (if none are resolved, values are legitimately 0)
2. [win_rate](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/backend/app/services/scoring.py#42-68) stored as percentage (0-100) but frontend multiplies by 100 again → display bug waiting to happen
3. `total_profit = max(0, pnl)` — user wants lifetime PnL (can be negative)

### Changes

#### [MODIFY] [pnl_calculator.py](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/backend/app/services/pnl_calculator.py)

- [win_rate](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/backend/app/services/scoring.py#42-68) → return as decimal (0.0–1.0), consistent with frontend expectations
- `total_profit` → renamed semantically to be lifetime PnL (remove [max(0, ...)](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/backend/tests/test_scoring.py#111-113))

#### [MODIFY] [account_analyzer.py](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/backend/app/services/account_analyzer.py)

Pass `win_rate * 100` to [compute_win_rate_anomaly()](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/backend/app/services/scoring.py#42-68) since it expects percentage input.

#### [MODIFY] [test_pnl_calculator.py](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/backend/tests/test_pnl_calculator.py)

Update assertions: [win_rate](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/backend/app/services/scoring.py#42-68) from `100.0`/`50.0` → `1.0`/`0.5`, `total_profit` for losers → negative PnL.

---

## 6. Whales Tab — Sortable Column Headers + Feature Description

**User feedback:** Whales tab should be a **separate feature** tracking profitable wallets (not insider-related).

### Changes

#### [MODIFY] [page.js (whales)](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/frontend/src/app/whales/page.js)

Per `vercel-react-best-practices` (`rerender-derived-state-no-effect`, `js-tosorted-immutable`):
- Add `sortKey` / `sortDir` state
- Clickable column headers with ▲/▼ indicators
- Derive sorted list during render (no `useEffect`)
- Use `toSorted()` for immutability
- Update page title/description: "**Top Performing Wallets** — Tracking the most profitable wallets on Polymarket by volume and win rate"

---

## 7. Insider Detection — Implement Improvements

**User feedback:** Implement the proposed detection improvements as code, not just documentation.

### Changes

#### [MODIFY] [scanner.py](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/backend/app/services/scanner.py)

Add **wallet-age pre-filter**: Before adding a wallet to `wallet_candidates`, check trade history count. Skip wallets with > 50 prior trades and > 365 days age (known active traders).

#### [NEW] [topic_classifier.py](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/backend/app/services/topic_classifier.py)

Topic cluster detection module:
- Group markets by topic keywords (e.g., "Trump", "tariff", "Fed", "election")
- Flag wallets that bet on multiple markets in the same topic cluster
- Returns `topic_concentration_score` (0.0–1.0)

#### [MODIFY] [account_analyzer.py](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/backend/app/services/account_analyzer.py)

Integrate improvements:
1. **First-deposit → first-trade correlation**: Check if `account_age_days < 7` AND first trade is within 24h of wallet creation
2. **Counter-consensus weighting**: Boost [entry_price_edge](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/backend/app/services/scoring.py#114-139) score for entries at < 20¢ (already partially handled by [compute_entry_price_edge](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/backend/app/services/scoring.py#114-139), but add explicit weighting in the analyzer)
3. **Topic cluster detection**: Use `topic_classifier.py` to enhance [bet_concentration](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/backend/app/services/scoring.py#70-87) factor when wallet bets across same-topic markets

#### [MODIFY] [page.js (about)](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/frontend/src/app/about/page.js)

Add an "Insider Detection Methodology" section explaining the 4 detection improvements.

---

## Verification Plan

### Automated Tests (§8 Quality Gates)

```bash
cd backend && .\venv\Scripts\activate && pytest tests/ -v
```

All tests in [test_scoring.py](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/backend/tests/test_scoring.py) and [test_pnl_calculator.py](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/backend/tests/test_pnl_calculator.py) must pass.

### Manual Verification

| Issue | Check |
|-------|-------|
| 1 | About page: all 6 factor cards show titles |
| 2-3 | About page + README weights match [config.py](file:///c:/Users/User/Desktop/PolymarketInsiderTracker/backend/app/core/config.py) |
| 4 | `GET /api/admin/export` returns JSON; `POST /api/admin/import` restores it |
| 5 | Insiders with resolved markets show non-zero win rate/PnL |
| 6 | Whales: click each column header → sorts ▲/▼ |
| 7 | Scanner logs show wallet-age filtering; topic classifier runs |

### Browser Verification

Open `http://localhost:3000` — verify about page, whales sort, and insider table visually.
