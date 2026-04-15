import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from supabase import Client

from auth.dependencies import get_current_user, get_supabase
from scoring.engine import ROLE_WEIGHTS, STATS_TO_NORMALIZE
from utils.teams import resolve_team_id

logger = logging.getLogger(__name__)

router = APIRouter()


class LeaderboardEntry(BaseModel):
    rank: int
    member_id: UUID
    username: str | None = None
    avatar_url: str | None = None
    total_points: float
    remaining_budget: float
    player_count: int
    week_points: float | None = None


class LeaderboardResponse(BaseModel):
    entries: list["LeaderboardEntry"]
    current_week: int | None
    available_weeks: list[int]
    selected_week: int | None


class MemberStatsOut(BaseModel):
    avg_kda: float | None
    avg_gold_diff_15: float | None
    avg_pts_per_week: float | None
    games_counted: int


class DetailedLeaderboardEntry(BaseModel):
    rank: int
    member_id: str
    username: str | None = None
    avatar_url: str | None = None
    total_points: float
    remaining_budget: float
    player_count: int
    stats: MemberStatsOut


def _check_membership(supabase: Client, league_id: str, user_id: str) -> None:
    resp = (
        supabase.table("league_members")
        .select("id")
        .eq("league_id", league_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No eres miembro de esta liga")


@router.get("/leaderboard/{league_id}", response_model=LeaderboardResponse)
async def get_leaderboard(
    league_id: UUID,
    week: int | None = None,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> LeaderboardResponse:
    _check_membership(supabase, str(league_id), user["id"])

    members_resp = (
        supabase.table("league_members")
        .select("id, user_id, total_points, remaining_budget")
        .eq("league_id", str(league_id))
        .order("total_points", desc=True)
        .execute()
    )
    members = members_resp.data or []

    # Traer usernames de profiles en una sola query
    user_ids = [m["user_id"] for m in members if m.get("user_id")]
    profiles_map: dict[str, dict] = {}
    if user_ids:
        profiles_resp = (
            supabase.table("profiles")
            .select("id, username, avatar_url")
            .in_("id", user_ids)
            .execute()
        )
        profiles_map = {p["id"]: p for p in (profiles_resp.data or [])}

    # Fetch rosters in bulk
    member_ids = [m["id"] for m in members]
    rosters_resp = (
        supabase.table("rosters")
        .select("id, member_id")
        .in_("member_id", member_ids)
        .execute()
    )
    roster_rows = rosters_resp.data or []
    roster_id_to_member: dict[str, str] = {r["id"]: r["member_id"] for r in roster_rows}
    roster_ids = [r["id"] for r in roster_rows]

    player_counts: dict[str, int] = {mid: 0 for mid in member_ids}
    member_starter_player_ids: dict[str, list[str]] = {mid: [] for mid in member_ids}

    if roster_ids:
        rp_resp = (
            supabase.table("roster_players")
            .select("roster_id, player_id, slot")
            .in_("roster_id", roster_ids)
            .execute()
        )
        for rp in (rp_resp.data or []):
            mid = roster_id_to_member.get(rp["roster_id"])
            if not mid:
                continue
            player_counts[mid] = player_counts.get(mid, 0) + 1
            slot = rp.get("slot") or ""
            if not slot.startswith("bench"):
                member_starter_player_ids[mid].append(rp["player_id"])

    # Obtener competition activa
    active_comp_resp = (
        supabase.table("competitions")
        .select("id")
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    active_competition_id: str | None = (
        (active_comp_resp.data or [{}])[0].get("id") if active_comp_resp.data else None
    )

    # Obtener semanas disponibles (solo semanas con lineup_snapshots)
    available_weeks: list[int] = []
    current_week: int | None = None
    if active_competition_id:
        snapped_resp = (
            supabase.table("lineup_snapshots")
            .select("week")
            .eq("competition_id", active_competition_id)
            .execute()
        )
        week_set: set[int] = set()
        for row in (snapped_resp.data or []):
            w = row.get("week")
            if w is not None:
                week_set.add(int(w))
        available_weeks = sorted(week_set)
        current_week = max(available_weeks) if available_weeks else None

    # Calcular week_points si se pidió una semana
    week_points_map: dict[str, float | None] = {mid: None for mid in member_ids}
    if week is not None and active_competition_id:
        # Series terminadas de esa semana
        series_week_resp = (
            supabase.table("series")
            .select("id")
            .eq("competition_id", active_competition_id)
            .eq("week", week)
            .eq("status", "finished")
            .execute()
        )
        series_ids_for_week = [s["id"] for s in (series_week_resp.data or [])]

        if series_ids_for_week:
            # Intentar reconstruir member_starter_player_ids desde lineup_snapshots
            snap_resp = (
                supabase.table("lineup_snapshots")
                .select("member_id, slot, player_id")
                .eq("competition_id", active_competition_id)
                .eq("week", week)
                .in_("member_id", member_ids)
                .execute()
            )
            if snap_resp.data:
                # Rebuild from snapshot
                from collections import defaultdict as _defaultdict
                snapped: dict[str, list[str]] = _defaultdict(list)
                for row in snap_resp.data:
                    if row["player_id"] and not (row.get("slot") or "").startswith("bench"):
                        snapped[row["member_id"]].append(row["player_id"])
                # Replace member_starter_player_ids with snapshot data for this week
                week_starter_player_ids: dict[str, list[str]] = {
                    mid: snapped.get(mid, []) for mid in member_ids
                }
            else:
                # No snapshot: manager had no starters this week → 0 points
                week_starter_player_ids = {mid: [] for mid in member_ids}

            # Fetch player_series_stats para todos los starters de esta semana
            all_starter_ids = list({pid for pids in week_starter_player_ids.values() for pid in pids})
            if all_starter_ids:
                pss_resp = (
                    supabase.table("player_series_stats")
                    .select("player_id, series_id, series_points")
                    .in_("player_id", all_starter_ids)
                    .in_("series_id", series_ids_for_week)
                    .execute()
                )
                # Acumular puntos por jugador
                player_week_points: dict[str, float] = {}
                for row in (pss_resp.data or []):
                    pid = row["player_id"]
                    pts = float(row.get("series_points") or 0)
                    player_week_points[pid] = player_week_points.get(pid, 0.0) + pts

                for mid in member_ids:
                    starters = week_starter_player_ids[mid]
                    if len(starters) < 5:
                        week_points_map[mid] = 0.0
                    else:
                        total = sum(player_week_points.get(pid, 0.0) for pid in starters)
                        week_points_map[mid] = total
        else:
            # Semana pedida sin series → 0 para todos
            for mid in member_ids:
                week_points_map[mid] = 0.0

    # Ordenar según contexto: si hay week → por week_points desc, si no → por total_points
    if week is not None:
        members_sorted = sorted(
            members,
            key=lambda m: week_points_map.get(m["id"]) or 0.0,
            reverse=True,
        )
    else:
        members_sorted = members  # ya viene ordenado por total_points desde la query

    entries = [
        LeaderboardEntry(
            rank=i + 1,
            member_id=m["id"],
            username=profiles_map.get(m.get("user_id", ""), {}).get("username"),
            avatar_url=profiles_map.get(m.get("user_id", ""), {}).get("avatar_url"),
            total_points=float(m["total_points"] or 0),
            remaining_budget=float(m["remaining_budget"] or 0),
            player_count=player_counts.get(m["id"], 0),
            week_points=week_points_map.get(m["id"]),
        )
        for i, m in enumerate(members_sorted)
    ]

    return LeaderboardResponse(
        entries=entries,
        current_week=current_week,
        available_weeks=available_weeks,
        selected_week=week,
    )


@router.get("/player/{player_id}/history")
async def get_player_score_history(
    player_id: UUID,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> dict:
    """Historial de stats y puntuación de un jugador (últimas 10 series)."""
    # Datos básicos del jugador
    player_resp = (
        supabase.table("players")
        .select("id, name, team, role, image_url, current_price")
        .eq("id", str(player_id))
        .execute()
    )
    if not player_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Jugador no encontrado")
    player = player_resp.data[0]

    # Resolver team_id del jugador via teams table (matching por nombre)
    player_team_name = player.get("team", "")
    player_team_id: str | None = resolve_team_id(supabase, player_team_name) if player_team_name else None

    # Fetch player_series_stats con join a series (fecha, equipos, winner) y teams
    series_stats_resp = (
        supabase.table("player_series_stats")
        .select(
            "series_id, series_points, avg_kills, avg_deaths, avg_assists, avg_cs_per_min, avg_dpm,"
            " series(id, date, competition_id, winner_id, team_home_id, team_away_id, competitions(name))"
        )
        .eq("player_id", str(player_id))
        .execute()
    )
    raw_series = series_stats_resp.data or []

    raw_series.sort(key=lambda x: (x.get("series") or {}).get("date") or "", reverse=True)
    raw_series = raw_series[:10]

    # Collect series_ids for the diff stats lookup
    series_ids_for_lookup = [str(row["series_id"]) for row in raw_series]

    # Collect all team_ids to fetch names
    team_ids: set[str] = set()
    for row in raw_series:
        s = row.get("series") or {}
        if s.get("team_home_id"):
            team_ids.add(s["team_home_id"])
        if s.get("team_away_id"):
            team_ids.add(s["team_away_id"])

    teams_map: dict[str, str] = {}
    if team_ids:
        teams_resp = (
            supabase.table("teams")
            .select("id, name")
            .in_("id", list(team_ids))
            .execute()
        )
        teams_map = {t["id"]: t["name"] for t in (teams_resp.data or [])}

    # Fetch gold_diff_15 and xp_diff_15 from player_game_stats joined with games(series_id)
    # Build per-series averages
    series_gold_diff: dict[str, float | None] = {}
    series_xp_diff: dict[str, float | None] = {}
    series_avg_duration: dict[str, float] = {}
    if series_ids_for_lookup:
        pgs_resp = (
            supabase.table("player_game_stats")
            .select("gold_diff_15, xp_diff_15, games(series_id, duration_min)")
            .eq("player_id", str(player_id))
            .execute()
        )
        # Group by series_id
        gold_by_series: dict[str, list[float]] = {}
        xp_by_series: dict[str, list[float]] = {}
        duration_by_series: dict[str, list[float]] = {}
        for pgs_row in (pgs_resp.data or []):
            game = pgs_row.get("games") or {}
            sid = str(game.get("series_id") or "")
            if sid not in series_ids_for_lookup:
                continue
            if pgs_row.get("gold_diff_15") is not None:
                gold_by_series.setdefault(sid, []).append(float(pgs_row["gold_diff_15"]))
            if pgs_row.get("xp_diff_15") is not None:
                xp_by_series.setdefault(sid, []).append(float(pgs_row["xp_diff_15"]))
            duration = game.get("duration_min")
            if duration is not None:
                duration_by_series.setdefault(sid, []).append(float(duration))
        for sid in series_ids_for_lookup:
            gold_vals = gold_by_series.get(sid, [])
            xp_vals = xp_by_series.get(sid, [])
            dur_vals = duration_by_series.get(sid, [])
            series_gold_diff[sid] = round(sum(gold_vals) / len(gold_vals), 1) if gold_vals else None
            series_xp_diff[sid] = round(sum(xp_vals) / len(xp_vals), 1) if xp_vals else None
            series_avg_duration[sid] = sum(dur_vals) / len(dur_vals) if dur_vals else 33.4

    stats = []
    for row in raw_series:
        s = row.get("series") or {}
        competition_obj = s.get("competitions") or {}
        competition_id = str(s.get("competition_id") or "")
        competition_name = competition_obj.get("name") or ""

        home_id = s.get("team_home_id")
        away_id = s.get("team_away_id")
        home_name = teams_map.get(home_id, "") if home_id else ""
        away_name = teams_map.get(away_id, "") if away_id else ""

        # team_1 = equipo del jugador, team_2 = rival
        if player_team_id and away_id == player_team_id:
            team_1, team_2 = away_name, home_name
        else:
            team_1, team_2 = home_name, away_name

        # Determinar resultado de la serie
        winner_id = s.get("winner_id")
        if winner_id is None:
            result = None
        elif player_team_id and winner_id == player_team_id:
            result = 1
        else:
            result = 0

        sid = str(row["series_id"])

        role = (player.get("role") or "").lower()
        stat_breakdown: dict[str, float] | None = None
        if role in ROLE_WEIGHTS:
            weights = ROLE_WEIGHTS[role]
            avg_duration = series_avg_duration.get(sid, 33.4) or 33.4
            stat_source = {
                "kills": float(row.get("avg_kills") or 0),
                "deaths": float(row.get("avg_deaths") or 0),
                "assists": float(row.get("avg_assists") or 0),
                "cs_per_min": float(row.get("avg_cs_per_min") or 0),
                "dpm": float(row.get("avg_dpm") or 0),
                "gold_diff_15": series_gold_diff.get(sid) or 0.0,
                "xp_diff_15": series_xp_diff.get(sid) or 0.0,
            }
            stat_breakdown = {}
            for stat, weight in weights.items():
                if stat not in stat_source:
                    continue
                value = stat_source[stat]
                if stat in STATS_TO_NORMALIZE:
                    value = value / avg_duration
                stat_breakdown[stat] = round(value * weight, 2)

        stats.append({
            "series_id": sid,
            "kills": round(float(row.get("avg_kills") or 0), 2),
            "deaths": round(float(row.get("avg_deaths") or 0), 2),
            "assists": round(float(row.get("avg_assists") or 0), 2),
            "cs_per_min": round(float(row.get("avg_cs_per_min") or 0), 2),
            "fantasy_points": round(float(row.get("series_points") or 0), 2),
            "result": result,
            "dpm": round(float(row.get("avg_dpm") or 0), 1) if row.get("avg_dpm") is not None else None,
            "gold_diff_at_15": series_gold_diff.get(sid),
            "xp_diff_at_15": series_xp_diff.get(sid),
            "turret_damage": None,
            "competition_id": competition_id,
            "competition_name": competition_name,
            "stat_breakdown": stat_breakdown,
            "matches": {
                "scheduled_at": s.get("date"),
                "team_1": team_1,
                "team_2": team_2,
            } if s else None,
        })

    # Obtener la competition activa para calcular el total del split actual
    active_comp_resp = (
        supabase.table("competitions")
        .select("id")
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    active_competition_id = (active_comp_resp.data or [{}])[0].get("id") if active_comp_resp.data else None

    # Sumar series_points de todas las series del split activo (sin límite de 10)
    if active_competition_id:
        total_resp = (
            supabase.table("player_series_stats")
            .select("series_points, series(competition_id)")
            .eq("player_id", str(player_id))
            .execute()
        )
        total_points = sum(
            float(r.get("series_points") or 0)
            for r in (total_resp.data or [])
            if str((r.get("series") or {}).get("competition_id") or "") == str(active_competition_id)
        )
    else:
        total_points = 0.0

    return {"player": player, "stats": stats, "total_points": round(total_points, 2)}


@router.get("/leaderboard/{league_id}/detailed", response_model=list[DetailedLeaderboardEntry])
def get_detailed_leaderboard(
    league_id: UUID,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> list[DetailedLeaderboardEntry]:
    """
    Leaderboard detallado: incluye stats agregadas por manager (KDA, gold@15, pts/semana).
    Más costoso que el leaderboard básico — corre en threadpool (sync def).
    """
    _check_membership(supabase, str(league_id), user["id"])

    # 1. Fetch league_members ordered by total_points DESC
    members_resp = (
        supabase.table("league_members")
        .select("id, user_id, total_points, remaining_budget")
        .eq("league_id", str(league_id))
        .order("total_points", desc=True)
        .execute()
    )
    members = members_resp.data or []
    if not members:
        return []

    member_ids = [m["id"] for m in members]

    # 2. Fetch usernames from profiles in one query
    user_ids = [m["user_id"] for m in members if m.get("user_id")]
    profiles_map: dict[str, dict] = {}
    if user_ids:
        profiles_resp = (
            supabase.table("profiles")
            .select("id, username, avatar_url")
            .in_("id", user_ids)
            .execute()
        )
        profiles_map = {p["id"]: p for p in (profiles_resp.data or [])}

    # 3. Fetch rosters for all members in one query
    rosters_resp = (
        supabase.table("rosters")
        .select("id, member_id")
        .in_("member_id", member_ids)
        .execute()
    )
    roster_rows = rosters_resp.data or []
    roster_id_to_member: dict[str, str] = {r["id"]: r["member_id"] for r in roster_rows}
    roster_ids = [r["id"] for r in roster_rows]

    # 4. Fetch starter roster_players for all rosters (exclude bench slots)
    member_starter_ids: dict[str, list[str]] = {mid: [] for mid in member_ids}
    player_count_map: dict[str, int] = {mid: 0 for mid in member_ids}

    if roster_ids:
        rp_resp = (
            supabase.table("roster_players")
            .select("roster_id, player_id, slot")
            .in_("roster_id", roster_ids)
            .execute()
        )
        for rp in (rp_resp.data or []):
            member_id = roster_id_to_member.get(rp["roster_id"])
            if not member_id:
                continue
            player_count_map[member_id] = player_count_map.get(member_id, 0) + 1
            slot = rp.get("slot") or ""
            if not slot.startswith("bench"):
                member_starter_ids[member_id].append(rp["player_id"])

    # 5. Fetch active competition_id
    active_comp_resp = (
        supabase.table("competitions")
        .select("id")
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    active_competition_id: str | None = (
        (active_comp_resp.data or [{}])[0].get("id") if active_comp_resp.data else None
    )

    # 6. Batch query: player_game_stats for all starters, filtered by active competition
    all_starter_ids = list({pid for pids in member_starter_ids.values() for pid in pids})

    # Map player_id -> member_id for aggregation
    player_to_member: dict[str, str] = {}
    for mid, pids in member_starter_ids.items():
        for pid in pids:
            player_to_member[pid] = mid

    # Per-member accumulators
    # { member_id: {kills: [], deaths: [], assists: [], gold_diff_15: [], game_points: [], weeks: set()} }
    from collections import defaultdict
    member_stats_raw: dict[str, dict] = {
        mid: {
            "kills": [],
            "deaths": [],
            "assists": [],
            "gold_diff_15": [],
            "game_points": [],
            "week_set": set(),
        }
        for mid in member_ids
    }

    if all_starter_ids and active_competition_id:
        # Fetch via games → series join to filter by competition_id
        pgs_resp = (
            supabase.table("player_game_stats")
            .select("player_id, kills, deaths, assists, gold_diff_15, game_points, games(series(competition_id, week))")
            .in_("player_id", all_starter_ids)
            .execute()
        )
        for row in (pgs_resp.data or []):
            game = row.get("games") or {}
            series_data = game.get("series") or {}
            if str(series_data.get("competition_id") or "") != str(active_competition_id):
                continue

            pid = row["player_id"]
            mid = player_to_member.get(pid)
            if not mid:
                continue

            acc = member_stats_raw[mid]
            if row.get("kills") is not None:
                acc["kills"].append(float(row["kills"]))
            if row.get("deaths") is not None:
                acc["deaths"].append(float(row["deaths"]))
            if row.get("assists") is not None:
                acc["assists"].append(float(row["assists"]))
            if row.get("gold_diff_15") is not None:
                acc["gold_diff_15"].append(float(row["gold_diff_15"]))
            if row.get("game_points") is not None:
                acc["game_points"].append(float(row["game_points"]))
            week = series_data.get("week")
            if week is not None:
                acc["week_set"].add(week)

    # 6b. Batch query: player_series_stats for all starters, to compute weeks_scored per member.
    # weeks_scored = weeks where sum of starters' series_points > 0.
    # { member_id: { week: sum_series_points } }
    member_week_pts: dict[str, dict[int, float]] = {mid: {} for mid in member_ids}

    if all_starter_ids and active_competition_id:
        pss_resp = (
            supabase.table("player_series_stats")
            .select("player_id, series_points, series(competition_id, week)")
            .in_("player_id", all_starter_ids)
            .execute()
        )
        for row in (pss_resp.data or []):
            series_data = row.get("series") or {}
            if str(series_data.get("competition_id") or "") != str(active_competition_id):
                continue
            week = series_data.get("week")
            if week is None:
                continue
            pid = row["player_id"]
            mid = player_to_member.get(pid)
            if not mid:
                continue
            pts = float(row.get("series_points") or 0)
            week_map = member_week_pts[mid]
            week_map[week] = week_map.get(week, 0.0) + pts

    # 7. Aggregate per member and build response
    def _safe_avg(values: list[float]) -> float | None:
        return round(sum(values) / len(values), 3) if values else None

    result: list[DetailedLeaderboardEntry] = []
    for i, m in enumerate(members):
        mid = m["id"]
        acc = member_stats_raw[mid]

        avg_kills = _safe_avg(acc["kills"])
        avg_deaths = _safe_avg(acc["deaths"])
        avg_assists = _safe_avg(acc["assists"])
        avg_gold_diff_15 = _safe_avg(acc["gold_diff_15"])
        games_counted = len(acc["kills"])

        # avg_kda = (avg_kills + avg_assists) / max(avg_deaths, 1)
        if avg_kills is not None and avg_assists is not None:
            _deaths = avg_deaths if avg_deaths and avg_deaths > 0 else 1.0
            avg_kda: float | None = round((avg_kills + avg_assists) / _deaths, 3)
        else:
            avg_kda = None

        # avg_pts_per_week = member.total_points / weeks_scored
        # weeks_scored = weeks where sum of starters' series_points > 0
        week_map = member_week_pts[mid]
        weeks_scored = sum(1 for pts in week_map.values() if pts > 0)
        total_points = float(m["total_points"] or 0)
        avg_pts_per_week: float | None = (
            round(total_points / weeks_scored, 2) if weeks_scored > 0 else None
        )

        profile = profiles_map.get(m.get("user_id", ""), {})

        result.append(
            DetailedLeaderboardEntry(
                rank=i + 1,
                member_id=mid,
                username=profile.get("username"),
                avatar_url=profile.get("avatar_url"),
                total_points=float(m["total_points"] or 0),
                remaining_budget=float(m["remaining_budget"] or 0),
                player_count=player_count_map.get(mid, 0),
                stats=MemberStatsOut(
                    avg_kda=avg_kda,
                    avg_gold_diff_15=avg_gold_diff_15,
                    avg_pts_per_week=avg_pts_per_week,
                    games_counted=games_counted,
                ),
            )
        )

    return result
