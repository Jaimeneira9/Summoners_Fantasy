# 🏆 LOLFantasy

> A fully automated fantasy esports platform for the **LEC** (League of Legends EMEA Championship) — built with real match data, auction-based markets, and role-weighted scoring.

[![Next.js](https://img.shields.io/badge/Next.js-14-black?logo=next.js&logoColor=white)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
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

- 🏟️ **Private Fantasy Leagues** — create leagues with invite codes, up to 10 members, each with a $100 budget
- 📊 **Real-Time Scoring** — fantasy points calculated per series (BO3/BO5), averaged across games, updated every hour
- 🎯 **Role-Weighted Scoring Engine** — different stat weights per role (Top, Jungle, Mid, ADC, Support, Coach) with multikill bonuses and anti-snowball normalization
- 🛒 **Auction-Based Player Market** — blind bid system with rotating listings; market refreshes every hour
- 🔄 **Trade System** — propose and accept trades between league members
- 📈 **Activity Feed** — league-wide log of bids, trades, and roster changes
- 🏅 **Standings per Split** — seasonal resets with historical stats preservation
- 📡 **Automated Data Pipeline** — scrapes gol.gg for LEC match data every hour via Cloudflare Browser Rendering API
- 🔒 **Row-Level Security** — full RLS on all Supabase tables; users only see their own league data
- 📱 **Fully Responsive** — sidebar (desktop) + bottom nav (mobile)

---

## 🛠️ Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| **Frontend** | Next.js 14 (App Router) | React Server Components, file-based routing |
| **Styling** | TailwindCSS | Cream/purple/gold design system |
| **Language (FE)** | TypeScript 5.x | Strict mode |
| **Backend** | FastAPI (Python) | Async-ready REST API |
| **Scheduler** | APScheduler | Background jobs: market refresh, series ingest, split reset |
| **Database** | Supabase (Postgres) | RLS enabled on all tables |
| **Auth** | Supabase Auth | JWT-based, SSR-compatible |
| **Data Pipeline** | gol.gg + Cloudflare Browser Rendering API | Scrapes live LEC match data |
| **Deployment (FE)** | Vercel | Edge-compatible Next.js deployment |
| **Deployment (BE)** | Any ASGI host (Railway, Fly.io, etc.) | Uvicorn server |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA PIPELINE (hourly)                   │
│                                                                 │
│  gol.gg ──► Cloudflare Browser    ──► series_ingest.py          │
│  (LEC)      Rendering API             │                         │
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
│  market_listings ◄──► bids ◄──► transactions                   │
│  trades ◄──► activity_log                                       │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       FASTAPI BACKEND                           │
│                                                                 │
│  /players   /leagues   /market   /scoring                       │
│  /trades    /roster    /activity /bids    /splits               │
│                                                                 │
│  APScheduler jobs (every hour):                                 │
│    ├─ series_ingest   → fetch & store LEC game data             │
│    ├─ market_refresh  → resolve bids, rotate listings           │
│    └─ split_reset     → daily check for season transitions      │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    NEXT.JS 14 FRONTEND                          │
│                                                                 │
│  (auth)    → /login  /signup                                    │
│  (protected) → /dashboard                                       │
│               /leagues/[id]/lineup                              │
│               /leagues/[id]/market                              │
│               /leagues/[id]/standings                           │
│               /leagues/[id]/activity                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🤖 AI-Driven Development

This project is built with a fully **agentic development workflow** — not just "AI autocomplete", but a structured system where AI acts as a senior engineer that maintains context, makes architectural decisions, and executes work autonomously.

### The Problem with Vibe Coding

Most "AI-assisted" development is just prompt-and-paste: you describe something, the AI writes code, you copy it in, things break, you prompt again. There is no memory, no architectural coherence, no learning. The AI forgets everything between sessions.

LOLFantasy was built differently.

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
| Supabase queries | `supabase` — RLS-aware patterns, type generation |
| React components | `vercel-react-best-practices` — RSC vs client, streaming |
| UI design | `web-design-guidelines` — design tokens, spacing, accessibility |
| gol.gg scraping | `golgg-scraper` — Cloudflare Browser Rendering patterns |

#### Why This Matters

Traditional development accumulates technical debt because context is lost. Code written Monday is refactored Thursday because nobody remembers the constraints that shaped it. With Engram + SDD:

- The "why" behind every decision is preserved
- Architecture evolves intentionally, not accidentally
- A new session picks up exactly where the last one left off — even weeks later

This is what it looks like to use AI as **Jarvis**, not as Stack Overflow.

---

## 🚀 Getting Started

### Prerequisites

- Node.js 18+
- Python 3.11+
- A [Supabase](https://supabase.com) project
- A [Cloudflare](https://cloudflare.com) account with Browser Rendering API access (for the data pipeline)

### 1. Clone & Configure

```bash
git clone https://github.com/your-username/LOLFantasy.git
cd LOLFantasy
```

### 2. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your Supabase credentials
```

**Required environment variables** (see `backend/.env.example`):

```env
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# Optional — for the gol.gg pipeline
CLOUDFLARE_ACCOUNT_ID=your-account-id
CLOUDFLARE_API_TOKEN=your-api-token

ENVIRONMENT=development
FRONTEND_URL=http://localhost:3000
```

### 3. Frontend Setup

```bash
cd frontend
npm install
cp .env.local.example .env.local
# Add your Supabase anon key and project URL
```

### 4. Database Migrations

```bash
# Apply all migrations to your Supabase project
supabase db push
```

### 5. Run Everything

```bash
# From the project root — starts both services in parallel
./scripts/dev.sh
```

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |

### Debug Endpoints (development only)

```bash
# Force a market refresh
curl -s -X POST http://localhost:8000/debug/market-refresh | jq

# Force a series ingest from gol.gg
curl -s -X POST http://localhost:8000/debug/series-ingest | jq
```

---

## 📁 Project Structure

```
LOLFantasy/
├── backend/
│   ├── main.py                  # FastAPI app, lifespan, scheduler setup
│   ├── auth/                    # JWT dependency injection
│   ├── routers/                 # REST endpoints (players, leagues, market, scoring, trades, roster, activity, bids, splits)
│   ├── scoring/
│   │   └── engine.py            # Role-weighted fantasy points calculator
│   ├── pipeline/
│   │   ├── gol_gg.py            # gol.gg scraper via Cloudflare Browser Rendering
│   │   ├── series_ingest.py     # Orchestrates full series → DB pipeline
│   │   └── scheduler.py         # APScheduler job definitions
│   ├── market/
│   │   └── refresh.py           # Bid resolution + listing rotation logic
│   ├── admin/
│   │   └── split_reset.py       # Split season reset handler
│   ├── models/                  # Pydantic models
│   ├── tests/                   # Pytest tests
│   └── requirements.txt
│
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── (auth)/          # login, signup pages
│       │   └── (protected)/     # authenticated routes
│       │       ├── dashboard/   # league list + create/join
│       │       └── leagues/[id]/
│       │           ├── lineup/      # roster management
│       │           ├── market/      # auction marketplace
│       │           ├── standings/   # leaderboard
│       │           └── activity/    # league event feed
│       ├── components/          # Shared UI (Sidebar, BottomNav, PlayerCard, LeagueRow, etc.)
│       └── lib/
│           └── api.ts           # Typed API client
│
├── supabase/
│   └── migrations/              # Ordered SQL migration files
│
└── scripts/
    └── dev.sh                   # Start backend + frontend in parallel
```

---

## 📡 Data Pipeline

The pipeline runs every hour via APScheduler and follows this sequence:

```
1. Lookup gol_gg_slug from competitions WHERE name = 'LEC'
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
```

### Scoring Formula

Fantasy points per game are calculated per role with distinct stat weights:

| Role | Key Stats |
|------|-----------|
| **Top** | kills, deaths, assists, CS/min, gold diff @15 |
| **Jungle** | kills, deaths, assists, CS/min, **objective steals** |
| **Mid** | kills, deaths, assists, CS/min, gold diff @15 |
| **ADC** | kills, deaths, assists, CS/min, **damage share** |
| **Support** | kills, deaths, assists, **vision score**, objective steals |

**Bonuses:** Double Kill (+2), Triple Kill (+5), Quadra Kill (+8), Penta Kill (+15)

**Anti-snowball normalization:** Games longer than 30 minutes apply a dampening factor: `points / (1 + excess_minutes × 0.01)` — preventing late-game statistical inflation from skewing scores.

A player's series score is the **average** across all games in the series (BO3/BO5).

---

## 🗄️ Database Schema

### Core Tables

| Table | Description |
|-------|-------------|
| `players` | LEC player roster — name, role, team, price, price history |
| `teams` | LEC teams with `aliases[]` array for name resolution |
| `competitions` | Splits/seasons with `gol_gg_slug` for pipeline lookup |
| `series` | BO3/BO5 series between two teams |
| `series_games` | Individual game records within a series |
| `player_game_stats` | Per-game stats + fantasy points per player |
| `player_series_stats` | Averaged stats + total points per series per player |

### Fantasy Layer

| Table | Description |
|-------|-------------|
| `fantasy_leagues` | Private leagues with invite codes, budget, max members |
| `league_members` | User membership — remaining budget, total points |
| `roster_slots` | Active roster (5 role slots per member per league) |
| `market_listings` | Active auction listings with `closes_at` deadline |
| `bids` | Blind bids on listings per user |
| `trades` | Proposed/accepted trades between members |
| `transactions` | Immutable history of all market activity |
| `activity_log` | League event feed (bids won, trades, roster changes) |

### Key Relationships

```
fantasy_leagues
    └── league_members (user_id, remaining_budget, total_points)
            └── roster_slots (player_id, role_slot)

series
    └── series_games
            └── player_game_stats (player_id, kills, deaths, ..., match_points)
                    └── player_series_stats (avg_kills, avg_deaths, ..., total_points)

market_listings
    └── bids (user_id, amount)
    └── → transactions (on resolution)
```

> All tables have Row-Level Security (RLS) enabled. Users can only read/write data belonging to leagues they are members of.

---

## 📄 License

MIT — see [LICENSE](LICENSE) for details.
