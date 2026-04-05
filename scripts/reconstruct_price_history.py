"""
reconstruct_price_history.py

Reconstructs price_history JSONB for all active players from scratch,
using the exact same formula as backend/market/price_updater.py.

Idempotent: running it twice produces the same result.
Filters to LEC Spring 2026 (competition_id = '4169a7c1-9e99-418d-a804-b556c318996f').
Includes rival team name per week entry.
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
# Price-update constants (mirror price_updater.py exactly)
# ---------------------------------------------------------------------------
ROLLING_WINDOW = 5
SENSITIVITY    = 0.3
CAP_UP         = 0.10
CAP_DOWN       = -0.10
PRICE_FLOOR    = 1.0

DEFAULT_BASELINE = 20.0  # used when avg_points_baseline is NULL

LEC_SPRING_2026_COMPETITION_ID = "4169a7c1-9e99-418d-a804-b556c318996f"


def tier_price(baseline: float) -> float:
    """Initial price from tier based on avg_points_baseline."""
    if baseline >= 40:
        return 30.0
    if baseline >= 33:
        return 25.0
    if baseline >= 24:
        return 20.0
    if baseline >= 18:
        return 15.0
    return 10.0


def clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------

def fetch_active_players(sb):
    """Returns list of dicts: id, name, avg_points_baseline, current_price, team."""
    resp = (
        sb.table("players")
        .select("id, name, avg_points_baseline, current_price, team")
        .eq("is_active", True)
        .execute()
    )
    return resp.data or []


def fetch_completed_weeks(sb):
    """
    Returns list of (week, earliest_date_str) tuples, ordered by week ASC.
    Only series with status='finished' for LEC Spring 2026 are considered.
    """
    resp = (
        sb.table("series")
        .select("week, date")
        .eq("status", "finished")
        .eq("competition_id", LEC_SPRING_2026_COMPETITION_ID)
        .not_.is_("week", "null")
        .order("week", desc=False)
        .order("date", desc=False)
        .execute()
    )
    rows = resp.data or []

    # Group by week → pick earliest date
    week_dates: dict[int, str] = {}
    for row in rows:
        w = row["week"]
        d = row["date"]
        if w is None or d is None:
            continue
        if w not in week_dates or d < week_dates[w]:
            week_dates[w] = d

    return sorted(week_dates.items())  # [(week_num, date_str), ...]


def fetch_series_for_competition(sb) -> list[dict]:
    """
    Fetches all finished series for LEC Spring 2026 with team_home_id, team_away_id, week, date.
    Returns list of dicts.
    """
    resp = (
        sb.table("series")
        .select("id, week, date, team_home_id, team_away_id")
        .eq("status", "finished")
        .eq("competition_id", LEC_SPRING_2026_COMPETITION_ID)
        .not_.is_("week", "null")
        .order("week", desc=False)
        .order("date", desc=False)
        .execute()
    )
    return resp.data or []


def fetch_teams_name_map(sb) -> dict[str, str]:
    """
    Returns: { team_id: team_name }
    """
    resp = (
        sb.table("teams")
        .select("id, name")
        .execute()
    )
    return {row["id"]: row["name"] for row in (resp.data or []) if row.get("id") and row.get("name")}


def fetch_all_game_stats_with_week(sb):
    """
    Fetches all player_game_stats rows joined with series.week, series.date,
    series.home_team, series.away_team — filtered to LEC Spring 2026.
    Returns list of dicts: player_id, game_points, week, series_date, series_id.

    We do this in bulk (paginated) to avoid N+1 queries per player.
    Uses PostgREST nested select: game_id → games(series_id → series(...))
    """
    print("  Fetching all player_game_stats (this may take a moment)...")
    all_rows: list[dict] = []
    page_size = 1000
    offset = 0

    while True:
        resp = (
            sb.table("player_game_stats")
            .select(
                "player_id, game_points, "
                "games!inner(series!inner(id, week, date, status, competition_id, team_home_id, team_away_id))"
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


def build_player_stats_index(
    raw_rows: list[dict],
) -> dict[str, list[tuple[int, str, float, str]]]:
    """
    Returns: { player_id: [(week, date_str, game_points, series_id), ...] }
    Only includes rows from 'finished' LEC Spring 2026 series with a non-null week.
    Sorted by (week, date_str) ascending.
    """
    index: dict[str, list[tuple[int, str, float, str]]] = defaultdict(list)

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

        week = series_obj.get("week")
        date_str = series_obj.get("date")
        status = series_obj.get("status")
        competition_id = series_obj.get("competition_id")
        series_id = series_obj.get("id", "")

        if week is None or date_str is None:
            continue
        if status != "finished":
            continue
        if competition_id != LEC_SPRING_2026_COMPETITION_ID:
            continue

        index[row["player_id"]].append((int(week), date_str, float(game_points), series_id))

    # Sort each player's list by (week, date) ascending
    for pid in index:
        index[pid].sort(key=lambda t: (t[0], t[1]))

    return dict(index)


def build_team_id_to_name_index(
    series_list: list[dict],
    teams_map: dict[str, str],
) -> dict[str, str]:
    """
    Returns: { team_id: team_name } resolved from series teams.
    Delegates to teams_map directly; this is a pass-through for clarity.
    """
    return teams_map


def build_series_rival_index(
    series_list: list[dict],
) -> dict[str, dict]:
    """
    Returns: { series_id: { team_home_id, team_away_id, week, date } }
    """
    return {
        s["id"]: s
        for s in series_list
        if s.get("id")
    }


# ---------------------------------------------------------------------------
# Core reconstruction
# ---------------------------------------------------------------------------

def reconstruct_for_player(
    player: dict,
    stats_by_week_and_date: list[tuple[int, str, float, str]],  # sorted asc
    completed_weeks: list[tuple[int, str]],
    series_index: dict[str, dict],
    teams_map: dict[str, str],
) -> list[dict]:
    """
    Returns reconstructed price_history list for one player.
    Includes rival team name per week entry.
    series_index: { series_id: { team_home_id, team_away_id, ... } }
    teams_map: { team_id: team_name }
    """
    baseline_raw = player.get("avg_points_baseline")
    baseline = float(baseline_raw) if baseline_raw is not None else DEFAULT_BASELINE
    initial_price = tier_price(baseline)
    player_team = player.get("team") or ""  # team name string

    history: list[dict] = []
    current_price = initial_price

    # Accumulate game points seen up to each week (sliding window)
    games_seen: list[float] = []  # ordered, all points up to current week

    # Build a lookup: week → list of (game_points, series_id) for this player that week
    week_data: dict[int, list[tuple[float, str]]] = defaultdict(list)
    for (week, _date, gp, series_id) in stats_by_week_and_date:
        week_data[week].append((gp, series_id))

    for (week_num, week_date) in completed_weeks:
        # Add this week's games to cumulative list
        week_entries = week_data.get(week_num, [])
        week_points = [gp for gp, _ in week_entries]
        games_seen.extend(week_points)

        if not games_seen:
            # No stats for this player up to this week — skip
            continue

        # Determine rival: pick the first series this player played this week
        rival: str | None = None
        if week_entries:
            first_series_id = week_entries[0][1]
            series = series_index.get(first_series_id)
            if series:
                home_team_id = series.get("team_home_id") or ""
                away_team_id = series.get("team_away_id") or ""
                home_team_name = teams_map.get(home_team_id, "")
                away_team_name = teams_map.get(away_team_id, "")
                if player_team and home_team_name and away_team_name:
                    # If player's team matches home team name, rival is away, else rival is home
                    if player_team == home_team_name:
                        rival = away_team_name
                    else:
                        rival = home_team_name

        # Rolling window: last ROLLING_WINDOW games
        recent = games_seen[-ROLLING_WINDOW:]
        recent_avg = mean(recent)

        delta_pct = (recent_avg - baseline) / baseline * SENSITIVITY
        delta_pct = clamp(delta_pct, CAP_DOWN, CAP_UP)

        new_price = max(round(current_price * (1 + delta_pct), 2), PRICE_FLOOR)

        entry: dict = {
            "date":      week_date,
            "price":     round(new_price, 2),
            "delta_pct": round(delta_pct, 4),
            "week":      week_num,
        }
        if rival:
            entry["rival"] = rival

        history.append(entry)

        current_price = new_price

    return history


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    print("=== Reconstructing price_history for all active players ===")
    print(f"    Competition filter: LEC Spring 2026 ({LEC_SPRING_2026_COMPETITION_ID})\n")

    # 1. Fetch players
    print("Step 1: Fetching active players...")
    players = fetch_active_players(sb)
    print(f"  Found {len(players)} active players.\n")

    # 2. Fetch completed weeks
    print("Step 2: Fetching completed weeks from series table (LEC Spring 2026 only)...")
    completed_weeks = fetch_completed_weeks(sb)
    print(f"  Completed weeks: {[w for w, _ in completed_weeks]}\n")

    if not completed_weeks:
        print("WARNING: No completed weeks found. Nothing to reconstruct.")
        return

    # 3. Fetch series metadata for rival lookup
    print("Step 3: Fetching series metadata for rival resolution...")
    series_list = fetch_series_for_competition(sb)
    series_index = build_series_rival_index(series_list)
    print(f"  Series fetched: {len(series_list)}\n")

    # 3b. Fetch teams name map (team_id → team_name)
    print("Step 3b: Fetching teams name map...")
    teams_map = fetch_teams_name_map(sb)
    print(f"  Teams fetched: {len(teams_map)}\n")

    # 4. Bulk-fetch all game stats
    print("Step 4: Fetching all player_game_stats...")
    raw_rows = fetch_all_game_stats_with_week(sb)
    stats_index = build_player_stats_index(raw_rows)
    print(f"  Players with game stats: {len(stats_index)}\n")

    # 5. Reconstruct and update
    print("Step 5: Reconstructing price_history and updating players...\n")
    updated_count = 0
    skipped_count = 0
    total_entries: list[int] = []

    sample_output: list[dict] = []

    for player in players:
        pid = player["id"]
        name = player.get("name", pid)
        player_stats = stats_index.get(pid, [])

        history = reconstruct_for_player(player, player_stats, completed_weeks, series_index, teams_map)

        # Always write (even empty list — replaces corrupted data)
        sb.table("players").update({
            "price_history": history,
        }).eq("id", pid).execute()

        if history:
            updated_count += 1
            total_entries.append(len(history))
            rival_sample = history[0].get("rival", "?")
            print(f"  [OK] {name}: {len(history)} entries | "
                  f"start={history[0]['price']}M → end={history[-1]['price']}M | "
                  f"rival[0]={rival_sample}")
            if len(sample_output) < 3:
                sample_output.append({"player": name, "history": history})
        else:
            skipped_count += 1
            print(f"  [--] {name}: no stats → price_history = []")

    # 6. Summary
    avg_entries = round(mean(total_entries), 1) if total_entries else 0
    print(f"""
=== SUMMARY ===
  Total active players:    {len(players)}
  Players with history:    {updated_count}
  Players with no stats:   {skipped_count}
  Avg entries per player:  {avg_entries}
  Weeks processed:         {len(completed_weeks)}
""")

    print("=== SAMPLE OUTPUT (up to 3 players) ===")
    for sample in sample_output:
        print(f"\nPlayer: {sample['player']}")
        for entry in sample["history"]:
            rival_str = entry.get("rival", "N/A")
            print(f"  Week {entry['week']:>2} | {entry['date']} | "
                  f"price={entry['price']:>6.2f}M | delta={entry['delta_pct']:+.2%} | "
                  f"rival={rival_str}")


if __name__ == "__main__":
    main()
