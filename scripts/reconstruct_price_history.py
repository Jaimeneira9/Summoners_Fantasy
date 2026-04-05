"""
reconstruct_price_history.py

Reconstructs price_history JSONB for all active players from scratch,
processing by SERIES (not by week) — matching the exact behavior of
backend/market/price_updater.py (_update_single_player_price).

Key difference from previous version:
  - Old: one history entry per WEEK, initial price from tier_price(baseline)
  - New: one history entry per SERIES (each series triggers a price update),
         initial price back-calculated from current_price by undoing all deltas

Algorithm per player:
  1. Fetch all finished LEC Spring 2026 series the player participated in,
     ordered by series.date ASC, then game order within each series.
  2. Simulate the rolling-window exactly as price_updater does:
       games_seen grows one series at a time (all games in that series appended)
       recent = games_seen[-ROLLING_WINDOW:]
       delta = clamp((mean(recent) - baseline) / baseline * SENSITIVITY, CAP_DOWN, CAP_UP)
  3. Back-calculate P0 = current_price / ∏(1 + delta_i)
  4. Forward-apply from P0 to build history (one entry per series).
  5. Last price in history should equal current_price (modulo rounding).

Only updates price_history. Does NOT touch current_price.

Idempotent: running it twice produces the same result.
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict
from statistics import mean

# ---------------------------------------------------------------------------
# Load env from backend/.env if not already set
# ---------------------------------------------------------------------------
def _load_env():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(script_dir, "..", "backend", ".env")
    env_path = os.path.normpath(env_path)
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    os.environ.setdefault(key.strip(), val.strip())

_load_env()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set.")
    sys.exit(1)

from supabase import create_client  # noqa: E402 — after env is loaded

# ---------------------------------------------------------------------------
# Price-update constants — mirror price_updater.py exactly
# ---------------------------------------------------------------------------
ROLLING_WINDOW = 5
SENSITIVITY    = 0.3
CAP_UP         = 0.10
CAP_DOWN       = -0.10
PRICE_FLOOR    = 1.0

DEFAULT_BASELINE = 20.0  # used when avg_points_baseline is NULL

LEC_SPRING_2026_COMPETITION_ID = "4169a7c1-9e99-418d-a804-b556c318996f"


def clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------

def fetch_active_players(sb) -> list[dict]:
    """Returns list of dicts: id, name, avg_points_baseline, current_price, team."""
    resp = (
        sb.table("players")
        .select("id, name, avg_points_baseline, current_price, team")
        .eq("is_active", True)
        .execute()
    )
    return resp.data or []


def fetch_teams_name_map(sb) -> dict[str, str]:
    """Returns: { team_id: team_name }"""
    resp = sb.table("teams").select("id, name").execute()
    return {
        row["id"]: row["name"]
        for row in (resp.data or [])
        if row.get("id") and row.get("name")
    }


def fetch_all_game_stats(sb) -> list[dict]:
    """
    Fetches all player_game_stats rows joined with series info,
    filtered to finished LEC Spring 2026 series.

    Returns list of dicts with:
      player_id, game_points, series_id, series_date, series_week,
      team_home_id, team_away_id, game_id
    """
    print("  Fetching all player_game_stats (this may take a moment)...")
    all_rows: list[dict] = []
    page_size = 1000
    offset = 0

    while True:
        resp = (
            sb.table("player_game_stats")
            .select(
                "player_id, game_points, game_id, "
                "games!inner(id, series_id, "
                "series!inner(id, week, date, status, competition_id, team_home_id, team_away_id))"
            )
            .not_.is_("game_points", "null")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        batch = resp.data or []
        all_rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
        print(f"    ... fetched {offset} rows so far")

    print(f"  Total game stat rows fetched: {len(all_rows)}")
    return all_rows


def build_player_series_index(raw_rows: list[dict]) -> dict[str, dict]:
    """
    Builds a per-player index of series, where each series accumulates
    the game_points for that player IN ORDER (by game_id ascending as proxy
    for game order within the series).

    Returns:
    {
        player_id: {
            series_id: {
                "date": str,
                "week": int | None,
                "team_home_id": str,
                "team_away_id": str,
                "game_points": [float, ...],  # ordered by game_id
                "game_ids": [str, ...]
            },
            ...
        }
    }

    Only includes rows from finished LEC Spring 2026 series.
    """
    # player_id → series_id → data
    index: dict[str, dict[str, dict]] = defaultdict(dict)

    for row in raw_rows:
        game_points = row.get("game_points")
        if game_points is None:
            continue

        game = row.get("games") or {}
        if isinstance(game, list):
            game = game[0] if game else {}

        series_obj = game.get("series") or {}
        if isinstance(series_obj, list):
            series_obj = series_obj[0] if series_obj else {}

        if not series_obj:
            continue

        status       = series_obj.get("status")
        competition  = series_obj.get("competition_id")
        series_id    = series_obj.get("id")
        date_str     = series_obj.get("date")
        week         = series_obj.get("week")
        team_home_id = series_obj.get("team_home_id") or ""
        team_away_id = series_obj.get("team_away_id") or ""
        game_id      = game.get("id") or row.get("game_id") or ""

        if status != "finished":
            continue
        if competition != LEC_SPRING_2026_COMPETITION_ID:
            continue
        if not series_id or date_str is None:
            continue

        pid = row["player_id"]

        if series_id not in index[pid]:
            index[pid][series_id] = {
                "date":         date_str,
                "week":         week,
                "team_home_id": team_home_id,
                "team_away_id": team_away_id,
                "game_points":  [],
                "game_ids":     [],
            }

        index[pid][series_id]["game_points"].append((game_id, float(game_points)))

    # Sort game_points within each series by game_id (proxy for game order)
    for pid, series_map in index.items():
        for sid, sdata in series_map.items():
            sdata["game_points"].sort(key=lambda t: t[0])
            # Flatten to just points list after sorting
            sdata["game_points"] = [gp for _, gp in sdata["game_points"]]

    return dict(index)


def resolve_rival(serie: dict, player_team: str, teams_map: dict[str, str]) -> str | None:
    """
    Given a series dict and the player's team name, return the rival team name.
    Returns None if resolution fails.
    """
    home_id   = serie.get("team_home_id") or ""
    away_id   = serie.get("team_away_id") or ""
    home_name = teams_map.get(home_id, "")
    away_name = teams_map.get(away_id, "")

    if not player_team or not home_name or not away_name:
        return None

    if player_team == home_name:
        return away_name
    else:
        return home_name


# ---------------------------------------------------------------------------
# Core reconstruction
# ---------------------------------------------------------------------------

def reconstruct_player(
    player: dict,
    series_map: dict[str, dict],
    teams_map: dict[str, str],
) -> tuple[list[dict], float, float]:
    """
    Reconstructs price_history for one player, one entry per series.

    Returns:
      (history, initial_price, final_price_from_history)

    history entries:
      { date, price, delta_pct, week (if set), rival (if resolved) }
    """
    baseline_raw  = player.get("avg_points_baseline")
    baseline      = float(baseline_raw) if baseline_raw is not None else DEFAULT_BASELINE
    current_price = float(player["current_price"])
    player_team   = player.get("team") or ""

    # Sort series by date ASC
    series_list = sorted(series_map.values(), key=lambda s: s["date"])

    if not series_list:
        return [], current_price, current_price

    # ------------------------------------------------------------------
    # Step 1: Simulate rolling window to collect deltas
    # ------------------------------------------------------------------
    games_seen: list[float] = []
    deltas: list[float] = []

    for serie in series_list:
        games_seen.extend(serie["game_points"])
        recent     = games_seen[-ROLLING_WINDOW:]
        recent_avg = mean(recent)
        delta      = clamp((recent_avg - baseline) / baseline * SENSITIVITY, CAP_DOWN, CAP_UP)
        deltas.append(delta)

    # ------------------------------------------------------------------
    # Step 2: Back-calculate initial price
    #   P0 = current_price / ∏(1 + delta_i)
    # ------------------------------------------------------------------
    compound = 1.0
    for d in deltas:
        compound *= (1 + d)
    initial_price = round(current_price / compound, 2)

    # ------------------------------------------------------------------
    # Step 3: Forward-apply to build history
    # ------------------------------------------------------------------
    history: list[dict] = []
    price = initial_price

    for i, serie in enumerate(series_list):
        price  = max(round(price * (1 + deltas[i]), 2), PRICE_FLOOR)
        rival  = resolve_rival(serie, player_team, teams_map)

        entry: dict = {
            "date":      serie["date"],
            "price":     round(price, 2),
            "delta_pct": round(deltas[i], 4),
        }
        if serie.get("week") is not None:
            entry["week"] = serie["week"]
        if rival:
            entry["rival"] = rival

        history.append(entry)

    return history, initial_price, price


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    print("=== Reconstructing price_history for all active players (by series) ===")
    print(f"    Competition filter: LEC Spring 2026 ({LEC_SPRING_2026_COMPETITION_ID})\n")

    # 1. Fetch players
    print("Step 1: Fetching active players...")
    players = fetch_active_players(sb)
    print(f"  Found {len(players)} active players.\n")

    # 2. Fetch teams map
    print("Step 2: Fetching teams name map...")
    teams_map = fetch_teams_name_map(sb)
    print(f"  Teams fetched: {len(teams_map)}\n")

    # 3. Bulk-fetch all game stats
    print("Step 3: Fetching all player_game_stats with series info...")
    raw_rows     = fetch_all_game_stats(sb)
    player_index = build_player_series_index(raw_rows)
    print(f"  Players with game stats: {len(player_index)}\n")

    # 4. Reconstruct and update
    print("Step 4: Reconstructing price_history and updating players...\n")
    updated_count = 0
    skipped_count = 0
    mismatch_count = 0

    for player in players:
        pid  = player["id"]
        name = player.get("name", pid)

        series_map = player_index.get(pid, {})
        history, initial_price, final_price = reconstruct_player(player, series_map, teams_map)

        # Always write (even empty list — replaces stale data)
        sb.table("players").update({
            "price_history": history,
        }).eq("id", pid).execute()

        if not history:
            skipped_count += 1
            print(f"  [--] {name}: no stats → price_history = []")
            continue

        updated_count += 1
        current_price = float(player["current_price"])
        diff          = abs(final_price - current_price)
        mismatch_flag = " *** MISMATCH" if diff > 0.05 else ""
        if diff > 0.05:
            mismatch_count += 1

        # Build delta summary string
        delta_parts = []
        for entry in history:
            w   = entry.get("week", "?")
            pct = entry["delta_pct"] * 100
            delta_parts.append(f"J{w}: {pct:+.1f}%")
        delta_summary = ", ".join(delta_parts)

        print(
            f"  [OK] {name}: {len(history)} series | "
            f"P0={initial_price:.2f}M → {final_price:.2f}M "
            f"(current={current_price:.2f}M){mismatch_flag} | "
            f"{delta_summary}"
        )

    print(f"""
=== SUMMARY ===
  Total active players:       {len(players)}
  Players with history:       {updated_count}
  Players with no stats:      {skipped_count}
  Price mismatch (>0.05M):    {mismatch_count}
""")


if __name__ == "__main__":
    main()
