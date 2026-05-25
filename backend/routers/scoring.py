"""
Router: Puntuación y leaderboard de la liga.

Rutas principales:
  GET /leaderboard/{league_id}          — ranking de managers (con soporte de filtro por jornada)
  GET /leaderboard/{league_id}/detailed — ranking con stats agregadas por manager
  GET /player/{player_id}/history       — historial de puntuación de un jugador (últimas 10 series)

Lógica de negocio central:
  - El leaderboard básico consulta la view member_total_points para los puntos totales
    (más eficiente que sumar series por series).
  - Al filtrar por semana (?week=N), los puntos se recalculan desde lineup_snapshots
    (el equipo que tenía el manager ese día) y player_series_stats (puntos de esa jornada).
    El capitán dobla los puntos de ese jugador.
  - El leaderboard detallado agrega stats de player_game_stats filtrando por
    competition_id del league a través del join games → series.
  - avg_pts_per_week solo cuenta semanas donde la suma de starters > 0 (semanas jugadas).
  - El historial de un jugador incluye stat_breakdown: la contribución de cada stat
    al puntaje de fantasía, usando ROLE_WEIGHTS del scoring engine.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
    """Lanza HTTP 403 si el usuario no es miembro de la liga indicada."""
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
    """Ranking de managers de la liga. Opcionalmente filtra por jornada (?week=N).

    Sin week: ordena por total_points dinámico (desde la view member_total_points).
    Con week: recalcula puntos de esa jornada usando snapshots y player_series_stats,
    y dobla los puntos del capitán. El orden cambia al ranking de esa jornada.
    Siempre incluye available_weeks y current_week para el selector del frontend.
    """
    # Fetch all league_members and verify membership in a single query
    members_resp = (
        supabase.table("league_members")
        .select("id, user_id, total_points, remaining_budget")
        .eq("league_id", str(league_id))
        .order("total_points", desc=True)
        .execute()
    )
    members = members_resp.data or []
    if not any(str(m.get("user_id", "")) == str(user["id"]) for m in members):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No eres miembro de esta liga")

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

    # Obtener competition_id de la liga (fuente de verdad: fantasy_leagues, no competitions global)
    league_resp = (
        supabase.table("fantasy_leagues")
        .select("competition_id")
        .eq("id", str(league_id))
        .single()
        .execute()
    )
    if not league_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Liga no encontrada")
    active_competition_id: str | None = str(league_resp.data["competition_id"]) if league_resp.data.get("competition_id") else None

    # Obtener semanas disponibles (series finalizadas como fuente de verdad)
    available_weeks: list[int] = []
    current_week: int | None = None
    if active_competition_id:
        snapped_resp = (
            supabase.table("series")
            .select("week")
            .eq("competition_id", active_competition_id)
            .eq("status", "finished")
            .execute()
        )
        week_set: set[int] = set()
        for row in (snapped_resp.data or []):
            w = row.get("week")
            if w is not None:
                week_set.add(int(w))
        available_weeks = sorted(week_set)
        current_week = max(available_weeks) if available_weeks else None

    def _calc_week_points(target_week: int) -> dict[str, float]:
        """Calcula los puntos de jornada de cada manager.

        Usa lineup_snapshots como fuente del equipo (no el roster actual).
        Un manager necesita al menos 5 starters en el snapshot para puntuar.
        El capitán aporta el doble de sus puntos individuales.
        """
        from collections import defaultdict as _defaultdict

        series_week_resp = (
            supabase.table("series")
            .select("id")
            .eq("competition_id", active_competition_id)
            .eq("week", target_week)
            .eq("status", "finished")
            .execute()
        )
        series_ids_for_week = [s["id"] for s in (series_week_resp.data or [])]

        result: dict[str, float] = {mid: 0.0 for mid in member_ids}

        if not series_ids_for_week:
            return result

        snap_resp = (
            supabase.table("lineup_snapshots")
            .select("member_id, slot, player_id, captain_player_id")
            .eq("competition_id", active_competition_id)
            .eq("week", target_week)
            .in_("member_id", member_ids)
            .execute()
        )
        if snap_resp.data:
            snapped: dict[str, list[str]] = _defaultdict(list)
            captain_by_member: dict[str, str | None] = {}
            for row in snap_resp.data:
                mid_snap = row["member_id"]
                if row["player_id"] and not (row.get("slot") or "").startswith("bench"):
                    snapped[mid_snap].append(row["player_id"])
                if mid_snap not in captain_by_member and row.get("captain_player_id") is not None:
                    captain_by_member[mid_snap] = row["captain_player_id"]
            week_starter_player_ids: dict[str, list[str]] = {
                mid: snapped.get(mid, []) for mid in member_ids
            }
        else:
            week_starter_player_ids = {mid: [] for mid in member_ids}
            captain_by_member = {}

        members_without_captain = [mid for mid in member_ids if mid not in captain_by_member]
        if members_without_captain:
            try:
                cap_resp = (
                    supabase.table("captain_selections")
                    .select("member_id, captain_player_id")
                    .eq("competition_id", active_competition_id)
                    .eq("week", target_week)
                    .in_("member_id", members_without_captain)
                    .execute()
                )
                for cap_row in (cap_resp.data or []):
                    captain_by_member[cap_row["member_id"]] = cap_row.get("captain_player_id")
            except Exception as exc:
                logger.warning("Failed to fetch captain_selections for week=%d: %s", target_week, exc)

        all_starter_ids = list({pid for pids in week_starter_player_ids.values() for pid in pids})
        if not all_starter_ids:
            return result

        pss_resp = (
            supabase.table("player_series_stats")
            .select("player_id, series_id, series_points")
            .in_("player_id", all_starter_ids)
            .in_("series_id", series_ids_for_week)
            .execute()
        )
        player_week_points: dict[str, float] = {}
        for row in (pss_resp.data or []):
            pid = row["player_id"]
            pts = float(row.get("series_points") or 0)
            player_week_points[pid] = player_week_points.get(pid, 0.0) + pts

        for mid in member_ids:
            starters = week_starter_player_ids[mid]
            if len(starters) < 5:
                result[mid] = 0.0
            else:
                captain_pid = captain_by_member.get(mid)
                result[mid] = sum(
                    player_week_points.get(pid, 0.0) * (
                        2 if captain_pid is not None and str(pid) == str(captain_pid) else 1
                    )
                    for pid in starters
                )

        return result

    week_points_map: dict[str, float | None] = {mid: None for mid in member_ids}
    dynamic_total_points: dict[str, float] = {mid: 0.0 for mid in member_ids}

    # Total dinámico: query a la view — filtra por member_ids, no necesita competition_id
    if member_ids:
        pts_resp = (
            supabase.table("member_total_points")
            .select("member_id, total_points")
            .in_("member_id", member_ids)
            .execute()
        )
        for row in (pts_resp.data or []):
            dynamic_total_points[row["member_id"]] = float(row["total_points"] or 0)

    # Si se pidió una semana específica, calculamos los puntos de esa semana
    if active_competition_id and week is not None:
        week_points_map = {mid: v for mid, v in _calc_week_points(week).items()}

    # Ordenar según contexto: si hay week → por week_points desc, si no → por total dinámico desc
    if week is not None:
        members_sorted = sorted(
            members,
            key=lambda m: week_points_map.get(m["id"]) or 0.0,
            reverse=True,
        )
    else:
        members_sorted = sorted(
            members,
            key=lambda m: dynamic_total_points.get(m["id"], 0.0),
            reverse=True,
        )

    entries = [
        LeaderboardEntry(
            rank=i + 1,
            member_id=m["id"],
            username=profiles_map.get(m.get("user_id", ""), {}).get("username"),
            avatar_url=profiles_map.get(m.get("user_id", ""), {}).get("avatar_url"),
            total_points=dynamic_total_points.get(m["id"], 0.0),
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
    league_id: UUID = Query(..., description="ID de la liga para filtrar por competition"),
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> dict:
    """Historial de stats y puntuación de un jugador, filtrado por la competition de la liga.

    Devuelve las últimas 10 series jugadas en la competición. Para cada serie incluye:
    - Stats promedio (KDA, CS/min, DPM) desde player_series_stats.
    - gold_diff_15 y xp_diff_15 desde player_game_stats (promedio de games de esa serie).
    - stat_breakdown: contribución de cada stat al puntaje según ROLE_WEIGHTS del engine.
    - total_points: acumulado de toda la competición (sin límite de 10 series).
    """
    league_resp = (
        supabase.table("fantasy_leagues")
        .select("competition_id")
        .eq("id", str(league_id))
        .single()
        .execute()
    )
    if not league_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Liga no encontrada")
    competition_id: str = str(league_resp.data["competition_id"])

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

    raw_series = [
        row for row in raw_series
        if str((row.get("series") or {}).get("competition_id") or "") == competition_id
    ]
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

    # Sumar series_points de todas las series de la competition de la liga (sin límite de 10)
    total_resp = (
        supabase.table("player_series_stats")
        .select("series_points, series(competition_id)")
        .eq("player_id", str(player_id))
        .execute()
    )
    total_points = sum(
        float(r.get("series_points") or 0)
        for r in (total_resp.data or [])
        if str((r.get("series") or {}).get("competition_id") or "") == competition_id
    )

    return {"player": player, "stats": stats, "total_points": round(total_points, 2)}


@router.get("/leaderboard/{league_id}/detailed", response_model=list[DetailedLeaderboardEntry])
def get_detailed_leaderboard(
    league_id: UUID,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> list[DetailedLeaderboardEntry]:
    """Leaderboard detallado con stats agregadas por manager (KDA, gold@15, pts/semana).

    Más costoso que el leaderboard básico porque agrega player_game_stats y
    player_series_stats de todos los starters de cada manager.
    Corre en threadpool (sync def) para no bloquear el event loop.
    avg_pts_per_week solo cuenta semanas donde el equipo sumó puntos > 0.
    """
    # 1. Fetch league_members and verify membership in a single query
    members_resp = (
        supabase.table("league_members")
        .select("id, user_id, total_points, remaining_budget")
        .eq("league_id", str(league_id))
        .order("total_points", desc=True)
        .execute()
    )
    members = members_resp.data or []
    if not any(str(m.get("user_id", "")) == str(user["id"]) for m in members):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No eres miembro de esta liga")
    if not members:
        return []

    member_ids = [m["id"] for m in members]

    # 1b. Fetch real total_points from the view (league_members.total_points is always 0)
    pts_view_resp = (
        supabase.table("member_total_points")
        .select("member_id, total_points")
        .in_("member_id", member_ids)
        .execute()
    )
    pts_map = {r["member_id"]: float(r["total_points"] or 0) for r in (pts_view_resp.data or [])}

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

    # 5. Fetch competition_id from the league (source of truth: fantasy_leagues, not global competitions)
    league_resp = (
        supabase.table("fantasy_leagues")
        .select("competition_id")
        .eq("id", str(league_id))
        .single()
        .execute()
    )
    if not league_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Liga no encontrada")
    active_competition_id: str | None = (
        str(league_resp.data["competition_id"]) if league_resp.data.get("competition_id") else None
    )

    # 5b. Fetch all series_ids for the competition once — used to filter both pgs and pss in SQL
    competition_series_ids: list[str] = []
    competition_week_map: dict[str, int] = {}  # series_id -> week
    if active_competition_id:
        series_resp = (
            supabase.table("series")
            .select("id, week")
            .eq("competition_id", active_competition_id)
            .execute()
        )
        for s in (series_resp.data or []):
            sid = s["id"]
            competition_series_ids.append(sid)
            if s.get("week") is not None:
                competition_week_map[sid] = int(s["week"])

    # 6. Batch query: player_game_stats for all starters, filtered by competition in SQL
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

    if all_starter_ids and competition_series_ids:
        # Filter player_game_stats in SQL via games.series_id — no Python-side filtering needed
        pgs_resp = (
            supabase.table("player_game_stats")
            .select("player_id, kills, deaths, assists, gold_diff_15, game_points, games(series_id)")
            .in_("player_id", all_starter_ids)
            .in_("games.series_id", competition_series_ids)
            .execute()
        )
        for row in (pgs_resp.data or []):
            game = row.get("games") or {}
            series_id = str(game.get("series_id") or "")
            if not series_id or series_id not in competition_week_map:
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
            week = competition_week_map.get(series_id)
            if week is not None:
                acc["week_set"].add(week)

    # 6b. Batch query: player_series_stats for all starters, filtered by competition in SQL.
    # weeks_scored = weeks where sum of starters' series_points > 0.
    # { member_id: { week: sum_series_points } }
    member_week_pts: dict[str, dict[int, float]] = {mid: {} for mid in member_ids}

    if all_starter_ids and competition_series_ids:
        pss_resp = (
            supabase.table("player_series_stats")
            .select("player_id, series_points, series_id")
            .in_("player_id", all_starter_ids)
            .in_("series_id", competition_series_ids)
            .execute()
        )
        for row in (pss_resp.data or []):
            sid = str(row.get("series_id") or "")
            week = competition_week_map.get(sid)
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
        total_points = pts_map.get(mid, 0.0)
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
                total_points=pts_map.get(mid, 0.0),
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
