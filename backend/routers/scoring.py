from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from supabase import Client

from auth.dependencies import get_current_user, get_supabase
from scoring.engine import ROLE_WEIGHTS, STATS_TO_NORMALIZE

router = APIRouter()


class LeaderboardEntry(BaseModel):
    rank: int
    member_id: UUID
    username: str | None = None
    avatar_url: str | None = None
    total_points: float
    remaining_budget: float
    player_count: int


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


@router.get("/leaderboard/{league_id}", response_model=list[LeaderboardEntry])
async def get_leaderboard(
    league_id: UUID,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> list[LeaderboardEntry]:
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
    profiles_map: dict[str, str] = {}
    if user_ids:
        profiles_resp = (
            supabase.table("profiles")
            .select("id, username, avatar_url")
            .in_("id", user_ids)
            .execute()
        )
        profiles_map = {p["id"]: p for p in (profiles_resp.data or [])}

    player_counts: dict[str, int] = {}
    for m in members:
        roster_resp = (
            supabase.table("rosters")
            .select("id")
            .eq("member_id", m["id"])
            .execute()
        )
        if roster_resp.data:
            roster_id = roster_resp.data[0]["id"]
            count_resp = (
                supabase.table("roster_players")
                .select("id", count="exact")
                .eq("roster_id", roster_id)
                .execute()
            )
            player_counts[m["id"]] = count_resp.count or 0
        else:
            player_counts[m["id"]] = 0

    return [
        LeaderboardEntry(
            rank=i + 1,
            member_id=m["id"],
            username=profiles_map.get(m.get("user_id", ""), {}).get("username"),
            avatar_url=profiles_map.get(m.get("user_id", ""), {}).get("avatar_url"),
            total_points=float(m["total_points"] or 0),
            remaining_budget=float(m["remaining_budget"] or 0),
            player_count=player_counts.get(m["id"], 0),
        )
        for i, m in enumerate(members)
    ]


@router.get("/player/{player_id}/history")
async def get_player_score_history(
    player_id: UUID,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> dict:
    """Historial de stats y puntuación de un jugador (últimas 10 partidas)."""
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

    # Obtener los games del jugador ordenados por fecha real de la serie (desc)
    # Primero buscamos los game_ids via games → series ordenados por series.date
    games_for_player_resp = (
        supabase.table("player_game_stats")
        .select("game_id, games(id, series(date))")
        .eq("player_id", str(player_id))
        .execute()
    )
    # Construir lista ordenada por series.date desc, limitada a 10
    games_with_date = []
    for row in (games_for_player_resp.data or []):
        game = row.get("games") or {}
        series_info = game.get("series") or {}
        games_with_date.append({
            "game_id": row["game_id"],
            "series_date": series_info.get("date"),
        })
    games_with_date.sort(key=lambda x: x["series_date"] or "", reverse=False)
    ordered_game_ids = [g["game_id"] for g in games_with_date[:10]]

    # Stats recientes desde player_game_stats
    stats_resp = (
        supabase.table("player_game_stats")
        .select("kills, deaths, assists, cs_per_min, vision_score, game_points, dpm, gold_diff_15, xp_diff_15, turret_damage, objective_steals, game_id, result")
        .eq("player_id", str(player_id))
        .in_("game_id", ordered_game_ids)
        .execute()
    )
    raw_stats = stats_resp.data or []
    # Re-ordenar raw_stats según el orden correcto de fechas
    game_id_order = {gid: idx for idx, gid in enumerate(ordered_game_ids)}
    raw_stats.sort(key=lambda s: game_id_order.get(s["game_id"], 9999))

    # Enriquecer con metadata del game (equipos + fecha + duración)
    game_ids = ordered_game_ids
    games_map: dict = {}
    teams_map: dict = {}
    if game_ids:
        games_resp = (
            supabase.table("games")
            .select("id, team_home_id, team_away_id, duration_min, series(date, competition_id, competitions(name))")
            .in_("id", game_ids)
            .execute()
        )
        games_map = {g["id"]: g for g in (games_resp.data or [])}

        team_ids = {g["team_home_id"] for g in games_resp.data or []} | \
                   {g["team_away_id"] for g in games_resp.data or []}
        if team_ids:
            teams_resp = (
                supabase.table("teams")
                .select("id, name")
                .in_("id", list(team_ids))
                .execute()
            )
            teams_map = {t["id"]: t["name"] for t in (teams_resp.data or [])}

    # Obtener el equipo del jugador para identificar al rival
    player_team = player.get("team", "")

    stats = []
    for s in raw_stats:
        game = games_map.get(s["game_id"]) or {}
        series_data = game.get("series") or {}
        duration = float(game.get("duration_min") or 30)

        home_name = teams_map.get(game.get("team_home_id"), "")
        away_name = teams_map.get(game.get("team_away_id"), "")
        # team_1 = equipo del jugador, team_2 = rival
        if player_team and player_team.lower() in away_name.lower():
            team_1, team_2 = away_name, home_name
        else:
            team_1, team_2 = home_name, away_name

        competition_id = str(series_data.get("competition_id") or "")
        competition_obj = series_data.get("competitions") or {}
        competition_name = competition_obj.get("name") or ""

        # Calcular breakdown de puntos por stat
        role = player.get("role", "")
        role_weights = ROLE_WEIGHTS.get(role, {})
        can_normalize = duration > 0
        stat_values = {
            "kills": s.get("kills") or 0,
            "deaths": s.get("deaths") or 0,
            "assists": s.get("assists") or 0,
            "cs_per_min": float(s.get("cs_per_min") or 0),
            "vision_score": s.get("vision_score") or 0,
            "dpm": float(s.get("dpm") or 0),
            "gold_diff_15": s.get("gold_diff_15") or 0,
            "xp_diff_15": s.get("xp_diff_15") or 0,
            "turret_damage": s.get("turret_damage") or 0,
            "objective_steals": s.get("objective_steals") or 0,
        }
        stat_breakdown: dict[str, float] = {}
        for stat, weight in role_weights.items():
            raw = stat_values.get(stat, 0)
            if can_normalize and stat in STATS_TO_NORMALIZE:
                value = raw / duration
            else:
                value = raw
            stat_breakdown[stat] = round(value * weight, 2)

        stats.append({
            "kills": s["kills"],
            "deaths": s["deaths"],
            "assists": s["assists"],
            "cs_per_min": round(float(s["cs_per_min"] or 0), 2),
            "vision_score": s["vision_score"],
            "fantasy_points": s["game_points"],
            "result": s.get("result"),
            "dpm": s.get("dpm"),
            "gold_diff_at_15": s.get("gold_diff_15"),
            "xp_diff_15": s.get("xp_diff_15"),
            "turret_damage": s.get("turret_damage"),
            "competition_id": competition_id,
            "competition_name": competition_name,
            "stat_breakdown": stat_breakdown,
            "matches": {
                "scheduled_at": series_data.get("date"),
                "team_1": team_1,
                "team_2": team_2,
            } if game else None,
        })

    # Obtener la competition activa para filtrar puntos del split actual
    active_comp_resp = (
        supabase.table("competitions")
        .select("id")
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    active_competition_id = (active_comp_resp.data or [{}])[0].get("id") if active_comp_resp.data else None

    # Query separada sin límite para calcular el total real del split actual
    # Filtra player_game_stats → games → series donde series.competition_id = competition activa
    if active_competition_id:
        total_resp = (
            supabase.table("player_game_stats")
            .select("game_points, games(series(competition_id))")
            .eq("player_id", str(player_id))
            .execute()
        )
        total_points = sum(
            float(r.get("game_points") or 0)
            for r in (total_resp.data or [])
            if (r.get("games") or {}).get("series", {}).get("competition_id") == active_competition_id
        )
    else:
        # Sin competition activa: devolver 0 en lugar de sumar todo sin filtro
        total_points = 0.0

    return {"player": player, "stats": stats, "total_points": round(total_points, 2)}
