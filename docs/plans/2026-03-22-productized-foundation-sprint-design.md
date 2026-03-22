# Productized Foundation Sprint Design

Date: 2026-03-22

## Goal
Ship an aggressive but controlled sprint that fixes correctness issues, improves the consumer-facing UX, preserves the existing dark financial-terminal style, strengthens trader-intelligence workflows, starts the follow-wallet/copytrading-adjacent direction, and adds tests for all implemented behavior.

## Chosen approach
Adopt a productized foundation sprint rather than a surgical patch or full rewrite.

This sprint should:
- fix the current correctness issues,
- clarify the product architecture,
- create a persistence foundation for future Supabase support,
- separate insider detection from whales/follow-trader workflows,
- and add a small set of visible product improvements.

## Product framing
Position the app as:

> Track suspicious wallets, discover high-performing traders, and monitor high-signal Polymarket activity.

This framing supports both trader-intelligence users and a more consumer-friendly audience.

## Architecture

### 1. Detection and analytics backend
The backend remains the system of record for trade ingestion, wallet analysis, the canonical six-factor risk score, whales ranking metrics, and persistence/export behavior.

The backend will expose two intentionally separate product surfaces:
- Insiders: suspicious wallets, high-risk alerts, suspicious markets, explainable factor breakdowns.
- Whales: profitable / high-signal traders, sortable performance metrics, follow/watchlist-oriented data, and copytrading-adjacent foundations.

### 2. Persistence abstraction
Introduce a thin storage/repository abstraction so the app is not tightly coupled to local SQLite.

For this sprint:
- SQLite remains the active local store.
- JSON export/import is added for backup and restore.
- A Supabase-ready adapter contract is introduced so remote persistence can be added later without rewriting business logic.

### 3. Consumer-facing dashboard shell
Keep the current visual language, but improve clarity and navigation.

Key surfaces:
- Home: overview, suspicious activity, key stats, top signals.
- Whales: performance-oriented follow-trader surface.
- Methodology: clean explanation of the canonical six-factor engine.
- Utility UX: sorting, filters, empty states, export actions, followed-wallets, and clearer copy.

## Feature plan

### Core fixes
1. Canonical six-factor risk engine
   - one set of factor names,
   - one set of weights,
   - one score breakdown contract,
   - one threshold/gating story,
   - and plain-English explanations of risk.

2. Win rate / PnL repair
   - trace trade ingestion,
   - verify PnL calculation,
   - verify analysis persistence,
   - verify API serialization,
   - verify frontend rendering.

3. Persistence upgrade
   - add JSON export,
   - add JSON import/restore,
   - add storage abstractions/interfaces that are Supabase-ready.

4. Whales dashboard separation
   - independent page logic,
   - sortable headers,
   - better performance metrics,
   - clear distinction from suspicious-wallet tracking.

5. Conservative wallet-age filtering
   - use wallet age to reduce noisy alerts,
   - prefer trustworthiness over larger alert volume.

### Product improvements
6. Explainable score UX
   - top contributing factors,
   - severity labels,
   - short plain-English rationale.

7. Followed wallets / watchlist
   - local browser persistence,
   - easy revisit flow,
   - dedicated whales affordances.

8. Better whales metrics
   - win rate,
   - total PnL,
   - total volume,
   - resolved markets,
   - risk score,
   - optional followability/conviction composite if it fits naturally.

9. Cleaner dashboard narrative
   - reduce dev-board feel,
   - improve section hierarchy,
   - make whales vs insiders easier to understand.

### Recommended visible feature additions
- Followed wallets panel.
- Export intelligence snapshot.
- Why-flagged chips.

## Data flow

### Risk engine flow
The backend should emit one canonical analysis payload per wallet containing:
- normalized factor scores,
- final risk score,
- elevated factors,
- performance stats,
- explanation metadata required by the frontend.

The frontend should render this payload rather than re-deriving business logic.

### Persistence flow
scan/analyze → persist locally → export/import snapshot → render in UI

Internally:
- the repository/storage abstraction handles reads/writes,
- SQLite remains active for now,
- JSON export/import operates on a defined snapshot schema,
- future Supabase support plugs into the same contract later.

### Follow/watchlist flow
- users follow wallets on the whales page,
- followed addresses are stored in local storage,
- the UI hydrates them on the client,
- followed wallets appear in a dedicated panel or highlighted state.

## Error handling

### Backend
- invalid import/export payloads return structured errors,
- persistence failures fail safely with clear messages,
- pipeline/scoring issues should degrade gracefully where possible.

### Frontend
The UI should distinguish between:
- no data yet,
- backend unavailable,
- import/export failure,
- and no followed wallets yet.

## Testing plan

### Backend tests
Add or update coverage for:
- canonical scoring behavior,
- wallet-age filtering behavior,
- win-rate/PnL integration behavior,
- JSON export serialization,
- JSON import validation/restoration,
- repository/storage abstraction behavior where practical.

### Frontend tests
Add the lightest maintainable test setup needed for:
- whales sorting behavior,
- follow/unfollow local storage persistence,
- factor explanation rendering,
- any new utility logic extracted from components.

### Verification
Run:
- backend tests,
- frontend lint/build,
- and a manual smoke pass if the environment allows.

## Success criteria
The sprint is successful if:
1. the six-factor model is consistent everywhere,
2. whales and insiders feel like separate product surfaces,
3. win rate / PnL visibly work,
4. JSON export/import works,
5. watchlist/follow UX works,
6. conservative wallet-age filtering is active,
7. tests cover the new behavior,
8. and the UI still feels like the same product, just clearer and stronger.
