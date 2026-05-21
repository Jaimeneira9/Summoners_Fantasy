# 🏆 Summoner's Fantasy

> A fully automated fantasy esports platform for the **LEC** and **LES** (League of Legends EMEA Championship / Superliga) — built with real match data, role-weighted scoring, and two distinct game modes.

[![Next.js](https://img.shields.io/badge/Next.js-14-black?logo=next.js&logoColor=white)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Supabase](https://img.shields.io/badge/Supabase-Postgres-3ECF8E?logo=supabase&logoColor=white)](https://supabase.com/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)

---

## 📸 Screenshots

| Dashboard | League Lineup | Player Market |
|-----------|---------------|---------------|
| League overview with scores and standings | Manage your 5-role roster per split | Bid on players in a rotating auction market |

> The UI uses a cream/purple/gold light theme with a responsive layout: **sidebar on desktop**, **bottom navigation on mobile**.

---

## ✨ Features

- 🏟️ **Private Fantasy Leagues** — create leagues with invite codes; two game modes with different rules and member limits
- 🎮 **Two Game Modes** — `draft_market` (blind bid auction) and `budget_pick` (direct free-agent signings)
- 📊 **Real-Time Scoring** — fantasy points calculated per series (BO3/BO5), averaged across games, updated every hour
- 🎯 **Role-Weighted Scoring Engine** — different stat weights per role (Top, Jungle, Mid, ADC, Support) with multikill bonuses and per-minute normalization
- 🛒 **Auction-Based Player Market** — blind bid system with rotating listings; resolves every hour (`draft_market` only)
- 🤝 **Peer-to-Peer Market** — managers can sell players and receive direct offers from other managers
- 🛡️ **Rescission Clause** — 14-day protection window after a purchase; any manager can trigger it by paying `MAX(paid price, current price)`
- 🎖️ **Captain System** — designate one starter per jornada to double their fantasy points
- 📅 **Lineup Snapshots** — historical record of each manager's roster per jornada; powers per-week leaderboards
- 🔄 **Trade System** — propose and accept trades between league members
- 📈 **Activity Feed** — league-wide log of bids, trades, roster changes, and clause activations
- 🏅 **Standings per Split** — seasonal resets with historical stats preservation
- 📡 **Automated Data Pipeline** — scrapes gol.gg for LEC/LES match data every hour via Cloudflare Browser Rendering API
- 🔒 **Row-Level Security** — full RLS on all Supabase tables; users only see their own league data
- 📱 **Fully Responsive** — sidebar (desktop) + bottom nav (mobile)

---

## 🎮 Game Modes

### `draft_market` — Auction League
The classic fantasy format. Each manager starts with a **$100 budget**. Players are listed on a rotating blind-bid market; when a listing closes, the highest bidder wins the player. Supports 2–8 members per league.

Key rules:
- Blind bids: you don't see what others bid
- Rescission clause protects purchased players for 14 days
- Peer-to-peer sell offers between managers
- Captain doubles one starter's points per jornada

### `budget_pick` — Free Agency League
No auction market. Managers sign players directly from the free-agent pool at their current price. No member limit. Simpler onboarding for casual groups.

Key rules:
- Instant signings — no bidding or waiting for market resolution
- Budget tracked; price paid is returned when dropping a player
- Captain system still applies
- No rescission clause (no market to protect against)

---

## 🛠️ Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| **Frontend** | Next.js 14 (App Router) | React Server Components, file-based routing |
| **Styling** | TailwindCSS | Cream/purple/gold design system |
| **Language (FE)** | TypeScript 5.x | Strict mode |
| **Backend** | FastAPI 0.115.0 (Python) | Async-ready REST API |
| **Scheduler** | APScheduler | Background jobs: market refresh, series ingest, split reset |
| **Database** | Supabase (Postgres) | RLS enabled on all tables |
| **Auth** | Supabase Auth | JWT-based, SSR-compatible |
| **Data Pipeline** | gol.gg + Cloudflare Browser Rendering API | Scrapes live LEC/LES match data |
| **Deployment** | Docker / docker-compose | Single `docker compose up --build` starts everything |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA PIPELINE (hourly)                   │
│                                                                 │
│  gol.gg ──► Cloudflare Browser    ──► series_ingest.py          │
│  (LEC/LES)  Rendering API             │                         │
│             (Markdown endpoint)       ├─► Upsert series/games   │
│                                       ├─► Calculate match pts   │
│                                       └─► Avg stats per series  │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SUPABASE (Postgres + RLS)                  │
│                                                                 │
│  players  ◄──► player_game_stats ◄──► series                   │
│  fantasy_leagues ◄──► league_members ◄──► roster_slots         │
│  lineup_snapshots ◄──► captain_selections                       │
│  market_listings ◄──► bids ◄──► transactions                   │
│  sell_offers ◄──► trades ◄──► activity_log                     │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       FASTAPI BACKEND                           │
│                                                                 │
│  /players   /leagues   /market   /scoring   /roster             │
│  /trades    /activity  /bids     /splits    /teams              │
│  /series    /competitions                                       │
│                                                                 │
│  APScheduler jobs (every hour):                                 │
│    ├─ series_ingest   → fetch & store LEC/LES game data         │
│    ├─ market_refresh  → resolve bids, rotate listings           │
│    └─ split_reset     → daily check (01:00 UTC)                 │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    NEXT.JS 14 FRONTEND                          │
│                                                                 │
│  (auth)    → /login  /signup                                    │
│  (protected) → /dashboard                                       │
│               /leagues/[id]/lineup       roster management      │
│               /leagues/[id]/market       auction marketplace    │
│               /leagues/[id]/standings    leaderboard            │
│               /leagues/[id]/activity     event feed             │
│               /leagues/[id]/calendar     series by jornada      │
│               /leagues/[id]/teams        LEC/LES team standings │
│               /leagues/[id]/h2h/[id]     H2H series detail      │
│               /leagues/[id]/stats/[id]   player profile         │
│               /leagues/[id]/ligas        competition selector   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Getting Started

See [`despliegue.md`](./despliegue.md) for full deployment instructions (Docker, environment variables, Supabase setup).

**Quick start with Docker:**

```bash
git clone https://github.com/your-username/Summoners_Fantasy.git
cd Summoners_Fantasy

# Copy and fill in environment files
cp backend/.env.example backend/.env
cp frontend/.env.local.example frontend/.env.local

# Build and start everything
docker compose up --build
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3002 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |

**Required environment variables** (backend):

```env
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# For the gol.gg pipeline
CLOUDFLARE_ACCOUNT_ID=your-account-id
CLOUDFLARE_API_TOKEN=your-api-token

ENVIRONMENT=development
FRONTEND_URL=http://localhost:3002
```

### Debug Endpoints (development only)

```bash
# Force a series ingest from gol.gg
curl -s -X POST http://localhost:8000/debug/series-ingest | jq

# Force a market refresh
curl -s -X POST http://localhost:8000/debug/market-refresh | jq
```

---

## 📁 Project Structure

```
Summoners_Fantasy/
├── docker-compose.yml           # Starts backend + frontend with one command
├── despliegue.md                # Full deployment guide (Docker, env vars, DB)
│
├── backend/
│   ├── Dockerfile
│   ├── main.py                  # FastAPI app, lifespan, scheduler setup, admin endpoints
│   ├── requirements.txt
│   ├── auth/                    # JWT dependency injection
│   ├── routers/                 # REST endpoints
│   │   ├── players.py           # Player catalog + price history
│   │   ├── leagues.py           # League CRUD + members
│   │   ├── market.py            # Listings, bids, sell offers, peer offers, clause
│   │   ├── roster.py            # Roster management, captain, budget_pick signings
│   │   ├── scoring.py           # Leaderboard, per-week scoring, player history
│   │   ├── trades.py            # Trade proposals and acceptance
│   │   ├── activity.py          # Activity feed
│   │   ├── bids.py              # Bid tracking
│   │   ├── splits.py            # Split/season management
│   │   ├── series.py            # Series calendar
│   │   ├── match_detail.py      # Game-by-game H2H stats
│   │   ├── teams.py             # LEC/LES team standings
│   │   └── competitions.py      # Active competition lookup
│   ├── scoring/
│   │   ├── engine.py            # Role-weighted fantasy points calculator
│   │   └── config_loader.py     # Scoring config loader
│   ├── pipeline/
│   │   ├── gol_gg.py            # gol.gg scraper via Cloudflare Browser Rendering
│   │   └── series_ingest.py     # Orchestrates full series → DB pipeline
│   ├── market/
│   │   ├── refresh.py           # Bid resolution + listing rotation
│   │   ├── bid_resolver.py      # Bid resolution logic
│   │   └── price_updater.py     # Price update after transactions
│   ├── admin/
│   │   └── split_reset.py       # Split season reset handler
│   └── tests/                   # Pytest tests
│
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── (auth)/          # login, signup pages
│       │   └── (protected)/     # authenticated routes
│       │       ├── dashboard/   # league list + create/join
│       │       └── leagues/[id]/
│       │           ├── lineup/          # roster management + captain selection
│       │           ├── market/          # auction marketplace + peer offers
│       │           ├── standings/       # leaderboard (all-time + per jornada)
│       │           ├── activity/        # league event feed
│       │           ├── calendar/        # series grouped by jornada
│       │           ├── teams/           # LEC/LES team standings
│       │           ├── ligas/           # competition selector
│       │           ├── h2h/[seriesId]/  # H2H series detail (game-by-game)
│       │           └── stats/[playerId]/ # player profile + clause/offer panels
│       ├── components/          # Shared UI (Sidebar, BottomNav, PlayerCard, etc.)
│       └── lib/
│           └── api.ts           # Typed API client
│
├── supabase/
│   └── migrations/              # Ordered SQL migration files
│
└── scripts/
    └── dev.sh                   # Start backend + frontend in parallel (no Docker)
```

---

## 📡 Data Pipeline

The pipeline runs every hour via APScheduler and follows this sequence:

```
1. Lookup gol_gg_slug from competitions WHERE is_active = true
2. fetch_matchlist(slug)     → list of GameEntry (game_id, teams, date)
3. Resolve team UUIDs        → match team names against teams.aliases
4. Upsert series             → UNIQUE (team_home_id, team_away_id, date)
5. For each game:
   ├─ fetch_game_fullstats(game_id) → player stats rows
   ├─ fetch_game_meta(game_id)      → game duration, winner
   ├─ Resolve player UUIDs
   ├─ calculate_match_points(stats, role, duration)
   └─ Upsert player_game_stats
6. Aggregate per-series averages → upsert player_series_stats
7. Update series.game_count + series.winner_id
8. Update manager total_points from lineup_snapshots
```

---

## 🎯 Scoring Formula

Fantasy points per game are calculated per role with distinct stat weights. Stats marked with `/min` are normalized by game duration before applying weights.

| Role | Key Stats |
|------|-----------|
| **Top** | kills/min, deaths/min, assists/min, CS/min, gold diff @15, DPM, turret damage, XP diff @15 |
| **Jungle** | kills/min, deaths/min, assists/min, CS/min, gold diff @15, DPM, **objective steals**, XP diff @15 |
| **Mid** | kills/min, deaths/min, assists/min, CS/min, gold diff @15, DPM, XP diff @15 |
| **ADC** | kills/min, deaths/min, assists/min, CS/min, gold diff @15, DPM, XP diff @15 |
| **Support** | kills/min, deaths/min, assists/min, CS/min, gold diff @15, DPM, **vision score/min**, objective steals, XP diff @15 |

**Multikill Bonuses:**

| Kill streak | Bonus |
|-------------|-------|
| Double Kill | +2 pts |
| Triple Kill | +5 pts |
| Quadra Kill | +8 pts |
| Penta Kill  | +15 pts |

**Per-minute normalization:** `kills`, `assists`, `deaths`, and `vision_score` are divided by `game_duration_min` before applying weights. `CS/min`, `DPM`, `gold_diff_15`, and `XP_diff_15` are already rate stats and are used as-is. This eliminates stat inflation from unusually long or short games.

A player's series score is the **average** across all games in the series (BO3/BO5).

**Captain bonus:** the designated captain's points for that jornada are doubled. Only starters (slots 1–5) can be captain.

---

## 🗄️ Database Schema

### Core Tables

| Table | Description |
|-------|-------------|
| `players` | LEC/LES player roster — name, role, team, price, price history |
| `teams` | LEC/LES teams with `aliases[]` array for name resolution |
| `competitions` | Splits/seasons with `gol_gg_slug` for pipeline lookup |
| `series` | BO3/BO5 series between two teams |
| `series_games` | Individual game records within a series |
| `player_game_stats` | Per-game stats + fantasy points per player |
| `player_series_stats` | Averaged stats + total points per series per player |

### Fantasy Layer

| Table | Description |
|-------|-------------|
| `fantasy_leagues` | Private leagues — invite code, game mode, budget, max members |
| `league_members` | User membership — remaining budget, total points |
| `roster_slots` | Active roster (5 role slots + coach + 2 bench per member) |
| `lineup_snapshots` | Historical roster record per manager per jornada |
| `captain_selections` | Captain designation per manager per jornada |
| `market_listings` | Active auction listings with `closes_at` deadline |
| `bids` | Blind bids on listings per user |
| `sell_offers` | Peer-to-peer sell offers between managers |
| `trades` | Proposed/accepted trades between members |
| `transactions` | Immutable history of all market activity |
| `activity_log` | League event feed (bids won, trades, roster changes, clause activations) |

### Key Relationships

```
fantasy_leagues
    └── league_members (user_id, remaining_budget, total_points)
            ├── roster_slots (player_id, role_slot)
            ├── lineup_snapshots (week, player snapshot)
            └── captain_selections (week, player_id)

series
    └── series_games
            └── player_game_stats (player_id, kills, deaths, ..., match_points)
                    └── player_series_stats (avg_kills, avg_deaths, ..., total_points)

market_listings
    └── bids (user_id, amount)
    └── → transactions (on resolution)

sell_offers (peer-to-peer)
    └── → transactions (on acceptance)
```

> All tables have Row-Level Security (RLS) enabled. Users can only read/write data belonging to leagues they are members of.

---

## 🤖 AI-Driven Development

This project is built with a fully **agentic development workflow** — not just "AI autocomplete", but a structured system where AI acts as a senior engineer that maintains context, makes architectural decisions, and executes work autonomously.

### The Problem with Vibe Coding

Most "AI-assisted" development is just prompt-and-paste: you describe something, the AI writes code, you copy it in, things break, you prompt again. There is no memory, no architectural coherence, no learning. The AI forgets everything between sessions.

Summoner's Fantasy was built differently.

### The Stack

#### 🧠 Engram — Persistent Memory

Every architectural decision, bug fix, discovered gotcha, and established convention is saved to **Engram** — a persistent memory system that survives across sessions and context compactions.

When a new session starts, the agent searches Engram for relevant prior context before writing a single line of code. This means:

- No re-explaining the same constraints session after session
- Bugs fixed once are never re-introduced because the fix is documented
- Conventions are established once and consistently applied everywhere

#### 📋 SDD — Spec-Driven Development

Before implementing any substantial feature, the agent follows a structured planning workflow:

```
explore → propose → spec → design → tasks → apply → verify → archive
```

Each phase produces a documented artifact stored in Engram. This prevents "just code it" impulses and ensures every feature is understood before it is built. The spec becomes the source of truth; the code is its implementation.

#### 🏗️ Agent Teams — Orchestrator / Sub-agent Model

The main conversation thread (orchestrator) **never does real work**. It:
- Understands the task
- Searches Engram for relevant context
- Delegates all actual work to sub-agents with fresh context windows

Sub-agents execute focused tasks (read files, write code, run analysis) and return summaries. This prevents context window bloat, avoids compaction mid-feature, and keeps the orchestrator's context clean for coordination.

#### 🔧 Specialized Skills

Domain-specific coding standards are loaded as **skills** based on context:

| Context | Skill Loaded |
|---------|-------------|
| FastAPI routes | `fastapi` — async patterns, dependency injection, error handling |
| Supabase queries | `supabase-postgres-best-practices` — RLS-aware patterns, type generation |
| React components | `vercel-react-best-practices` — RSC vs client, streaming |
| UI design | `web-design-guidelines` — design tokens, spacing, accessibility |
| gol.gg scraping | `golgg-scraper` — Cloudflare Browser Rendering patterns |

#### Why This Matters

Traditional development accumulates technical debt because context is lost. Code written Monday is refactored Thursday because nobody remembers the constraints that shaped it. With Engram + SDD:

- The "why" behind every decision is preserved
- Architecture evolves intentionally, not accidentally
- A new session picks up exactly where the last one left off — even weeks later

This is what it looks like to use AI as **Jarvis**, not as Stack Overflow.
