"""
reconstruct_price_history.py

Reconstructs price_history JSONB for all active players from scratch,
using the exact same formula as backend/market/price_updater.py.

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
# Price-update constants (mirror price_updater.py exactly)
# ---------------------------------------------------------------------------
ROLLING_WINDOW = 5
SENSITIVITY    = 0.3
CAP_UP         = 0.10
CAP_DOWN       = -0.10
PRICE_FLOOR    = 1.0

DEFAULT_BASELINE = 20.0  # used when avg_points_baseline is NULL


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
    """Returns list of dicts: id, name, avg_points_baseline, current_price."""
    resp = (
        sb.table("players")
        .select("id, name, avg_points_baseline, current_price")
        .eq("is_active", True)
        .execute()
    )
    return resp.data or []


def fetch_completed_weeks(sb):
    """
    Returns list of (week, earliest_date_str) tuples, ordered by week ASC.
    Only series with status='finished' are considered.
    """
    resp = (
        sb.table("series")
        .select("week, date")
        .eq("status", "finished")
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


def fetch_all_game_stats_with_week(sb):
    """
    Fetches all player_game_stats rows joined with series.week and series.date.
    Returns list of dicts: player_id, game_points, week, series_date.

    We do this in bulk (paginated) to avoid N+1 queries per player.
    Uses PostgREST nested select: game_id → games(series_id → series(week, date))
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
                "games!inner(series!inner(week, date, status))"
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


def build_player_stats_index(raw_rows: list[dict]) -> dict[str, list[tuple[int, str, float]]]:
    """
    Returns: { player_id: [(week, date_str, game_points), ...] }
    Only includes rows from 'finished' series with a non-null week.
    Sorted by (week, date_str) ascending.
    """
    index: dict[str, list[tuple[int, str, float]]] = defaultdict(list)

    for row in raw_rows:
        game_points = row.get("game_points")
        if game_points is None:
            continue

        game = row.get("games") or {}
        # PostgREST returns nested objects; handle both list and dict forms
        if isinstance(game, list):
            game = game[0] if game else {}

        series_obj = game.get("series") or {}
        if isinstance(series_obj, list):
            series_obj = series_obj[0] if series_obj else {}

        week = series_obj.get("week")
        date_str = series_obj.get("date")
        status = series_obj.get("status")

        if week is None or date_str is None or status != "finished":
            continue

        index[row["player_id"]].append((int(week), date_str, float(game_points)))

    # Sort each player's list by (week, date) ascending
    for pid in index:
        index[pid].sort(key=lambda t: (t[0], t[1]))

    return dict(index)


# ---------------------------------------------------------------------------
# Core reconstruction
# ---------------------------------------------------------------------------

def reconstruct_for_player(
    player: dict,
    stats_by_week_and_date: list[tuple[int, str, float]],  # sorted asc
    completed_weeks: list[tuple[int, str]],
) -> list[dict]:
    """
    Returns reconstructed price_history list for one player.
    """
    baseline_raw = player.get("avg_points_baseline")
    baseline = float(baseline_raw) if baseline_raw is not None else DEFAULT_BASELINE
    initial_price = tier_price(baseline)

    history: list[dict] = []
    current_price = initial_price

    # Accumulate game points seen up to each week (sliding window)
    games_seen: list[float] = []  # ordered, all points up to current week

    # Build a lookup: week → list of game_points for this player that week
    points_by_week: dict[int, list[float]] = defaultdict(list)
    for (week, _date, gp) in stats_by_week_and_date:
        points_by_week[week].append(gp)

    for (week_num, week_date) in completed_weeks:
        # Add this week's games to cumulative list
        week_points = points_by_week.get(week_num, [])
        games_seen.extend(week_points)

        if not games_seen:
            # No stats for this player up to this week — skip
            continue

        # Rolling window: last ROLLING_WINDOW games
        recent = games_seen[-ROLLING_WINDOW:]
        recent_avg = mean(recent)

        delta_pct = (recent_avg - baseline) / baseline * SENSITIVITY
        delta_pct = clamp(delta_pct, CAP_DOWN, CAP_UP)

        new_price = max(round(current_price * (1 + delta_pct), 2), PRICE_FLOOR)

        history.append({
            "date":      week_date,
            "price":     round(new_price, 2),
            "delta_pct": round(delta_pct, 4),
            "week":      week_num,
        })

        current_price = new_price

    return history


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    print("=== Reconstructing price_history for all active players ===\n")

    # 1. Fetch players
    print("Step 1: Fetching active players...")
    players = fetch_active_players(sb)
    print(f"  Found {len(players)} active players.\n")

    # 2. Fetch completed weeks
    print("Step 2: Fetching completed weeks from series table...")
    completed_weeks = fetch_completed_weeks(sb)
    print(f"  Completed weeks: {[w for w, _ in completed_weeks]}\n")

    if not completed_weeks:
        print("WARNING: No completed weeks found. Nothing to reconstruct.")
        return

    # 3. Bulk-fetch all game stats
    print("Step 3: Fetching all player_game_stats...")
    raw_rows = fetch_all_game_stats_with_week(sb)
    stats_index = build_player_stats_index(raw_rows)
    print(f"  Players with game stats: {len(stats_index)}\n")

    # 4. Reconstruct and update
    print("Step 4: Reconstructing price_history and updating players...\n")
    updated_count = 0
    skipped_count = 0
    total_entries: list[int] = []

    sample_output: list[dict] = []

    for player in players:
        pid = player["id"]
        name = player.get("name", pid)
        player_stats = stats_index.get(pid, [])

        history = reconstruct_for_player(player, player_stats, completed_weeks)

        # Always write (even empty list — replaces corrupted data)
        sb.table("players").update({
            "price_history": history,
        }).eq("id", pid).execute()

        if history:
            updated_count += 1
            total_entries.append(len(history))
            print(f"  [OK] {name}: {len(history)} entries | "
                  f"start={history[0]['price']}M → end={history[-1]['price']}M")
            if len(sample_output) < 3:
                sample_output.append({"player": name, "history": history})
        else:
            skipped_count += 1
            print(f"  [--] {name}: no stats → price_history = []")

    # 5. Summary
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
            print(f"  Week {entry['week']:>2} | {entry['date']} | "
                  f"price={entry['price']:>6.2f}M | delta={entry['delta_pct']:+.2%}")


if __name__ == "__main__":
    main()
