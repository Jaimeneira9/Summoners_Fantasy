import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from supabase import Client

from auth.dependencies import get_current_user, get_supabase

logger = logging.getLogger(__name__)

router = APIRouter()

ROLE_ORDER = {"top": 1, "jungle": 2, "mid": 3, "adc": 4, "support": 5}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class SeriesCalendarEntry(BaseModel):
    series_id: str
    team_home: str
    team_away: str
    date: str
    week: int | None
    status: str
    result: str | None


class CalendarResponse(BaseModel):
    series: list[SeriesCalendarEntry]


class TeamH2HStats(BaseModel):
    team_id: str
    team_name: str
    wins: int
    losses: int
    avg_kda: float
    avg_gold_diff_15: float
    avg_dpm: float
    avg_cs_per_min: float


class PlayerH2HStats(BaseModel):
    player_id: str
    name: str
    role: str
    avg_kills: float
    avg_deaths: float
    avg_assists: float
    avg_cs_per_min: float
    avg_dpm: float
    avg_kda: float
    series_played: int


class H2HResponse(BaseModel):
    series_id: str
    date: str
    status: str
    result: str | None
    team_home: TeamH2HStats
    team_away: TeamH2HStats
    players_home: list[PlayerH2HStats]
    players_away: list[PlayerH2HStats]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


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


def _get_active_competition(supabase: Client) -> dict:
    comp_resp = (
        supabase.table("competitions")
        .select("id, name")
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if not comp_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No hay competición activa")
    return comp_resp.data[0]


def _build_result(winner_id: str | None, team_home_id: str, game_count: int) -> str | None:
    """Build result string e.g. '2-1' from home team's perspective."""
    if not winner_id:
        return None
    loser_wins = game_count - 2
    if loser_wins < 0:
        loser_wins = 0
    if winner_id == team_home_id:
        return f"2-{loser_wins}"
    else:
        return f"{loser_wins}-2"


def _build_team_stats(
    supabase: Client,
    team_id: str,
    team_name: str,
    competition_id: str,
    all_series: list[dict],
    player_ids_by_team_name: dict[str, list[str]],
) -> TeamH2HStats:
    """Build TeamH2HStats for one team using pre-fetched series + player_game_stats."""
    wins = 0
    losses = 0
    for s in all_series:
        if s.get("status") != "finished":
            continue
        home = s.get("team_home_id")
        away = s.get("team_away_id")
        winner = s.get("winner_id")
        if team_id not in (home, away):
            continue
        if winner == team_id:
            wins += 1
        elif winner:
            losses += 1

    player_ids = player_ids_by_team_name.get(team_name, [])

    kills_list: list[float] = []
    deaths_list: list[float] = []
    assists_list: list[float] = []
    gold_diff_list: list[float] = []
    dpm_list: list[float] = []
    cs_list: list[float] = []

    if player_ids:
        pgs_resp = (
            supabase.table("player_game_stats")
            .select("kills, deaths, assists, gold_diff_15, dpm, cs_per_min, games(series(competition_id, status))")
            .in_("player_id", player_ids)
            .execute()
        )
        for row in (pgs_resp.data or []):
            game = row.get("games") or {}
            series_data = game.get("series") or {}
            if str(series_data.get("competition_id") or "") != str(competition_id):
                continue
            if series_data.get("status") != "finished":
                continue
            if row.get("kills") is not None:
                kills_list.append(float(row["kills"]))
            if row.get("deaths") is not None:
                deaths_list.append(float(row["deaths"]))
            if row.get("assists") is not None:
                assists_list.append(float(row["assists"]))
            if row.get("gold_diff_15") is not None:
                gold_diff_list.append(float(row["gold_diff_15"]))
            if row.get("dpm") is not None:
                dpm_list.append(float(row["dpm"]))
            if row.get("cs_per_min") is not None:
                cs_list.append(float(row["cs_per_min"]))

    avg_kills = _safe_avg(kills_list)
    avg_deaths = _safe_avg(deaths_list)
    avg_assists = _safe_avg(assists_list)
    avg_kda = round((avg_kills + avg_assists) / max(avg_deaths, 1), 2)

    return TeamH2HStats(
        team_id=team_id,
        team_name=team_name,
        wins=wins,
        losses=losses,
        avg_kda=avg_kda,
        avg_gold_diff_15=_safe_avg(gold_diff_list),
        avg_dpm=_safe_avg(dpm_list),
        avg_cs_per_min=_safe_avg(cs_list),
    )


def _build_players_stats(
    supabase: Client,
    team_name: str,
    competition_id: str,
    player_rows: list[dict],
    series_ids_in_competition: list[str],
) -> list[PlayerH2HStats]:
    """Build PlayerH2HStats list for one team, sorted by role order."""
    team_players = [p for p in player_rows if p.get("team") == team_name and p.get("role") != "coach"]
    result: list[PlayerH2HStats] = []

    for p in team_players:
        pid = p["id"]
        role = p.get("role") or "unknown"

        # Get per-series stats from player_series_stats
        pss_resp = (
            supabase.table("player_series_stats")
            .select("series_id, avg_kills, avg_deaths, avg_assists, avg_cs_per_min, avg_dpm")
            .eq("player_id", pid)
            .in_("series_id", series_ids_in_competition)
            .execute()
        )
        rows = pss_resp.data or []
        if not rows:
            continue

        kills_list = [float(r["avg_kills"]) for r in rows if r.get("avg_kills") is not None]
        deaths_list = [float(r["avg_deaths"]) for r in rows if r.get("avg_deaths") is not None]
        assists_list = [float(r["avg_assists"]) for r in rows if r.get("avg_assists") is not None]
        cs_list = [float(r["avg_cs_per_min"]) for r in rows if r.get("avg_cs_per_min") is not None]
        dpm_list = [float(r["avg_dpm"]) for r in rows if r.get("avg_dpm") is not None]

        avg_kills = _safe_avg(kills_list)
        avg_deaths = _safe_avg(deaths_list)
        avg_assists = _safe_avg(assists_list)
        avg_kda = round((avg_kills + avg_assists) / max(avg_deaths, 1), 2)

        result.append(
            PlayerH2HStats(
                player_id=pid,
                name=p.get("name") or "",
                role=role,
                avg_kills=avg_kills,
                avg_deaths=avg_deaths,
                avg_assists=avg_assists,
                avg_cs_per_min=_safe_avg(cs_list),
                avg_dpm=_safe_avg(dpm_list),
                avg_kda=avg_kda,
                series_played=len(rows),
            )
        )

    result.sort(key=lambda x: ROLE_ORDER.get(x.role, 99))
    return result


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/{league_id}/calendar", response_model=CalendarResponse)
def get_calendar(
    league_id: UUID,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> CalendarResponse:
    """
    Returns all series for the active competition, ordered by date ASC.
    """
    _check_membership(supabase, str(league_id), user["id"])

    competition = _get_active_competition(supabase)
    competition_id = competition["id"]

    # Fetch all series with home/away team info
    series_resp = (
        supabase.table("series")
        .select(
            "id, date, week, status, winner_id, game_count, team_home_id, team_away_id,"
            " home_team:teams!series_team_home_id_fkey(id, name),"
            " away_team:teams!series_team_away_id_fkey(id, name)"
        )
        .eq("competition_id", competition_id)
        .order("date", desc=False)
        .execute()
    )

    entries: list[SeriesCalendarEntry] = []
    for s in (series_resp.data or []):
        home_team = s.get("home_team") or {}
        away_team = s.get("away_team") or {}
        winner_id = s.get("winner_id")
        game_count = s.get("game_count") or 0
        team_home_id = s.get("team_home_id") or ""

        result: str | None = None
        if s.get("status") == "finished":
            result = _build_result(winner_id, team_home_id, game_count)

        entries.append(
            SeriesCalendarEntry(
                series_id=str(s["id"]),
                team_home=home_team.get("name") or "",
                team_away=away_team.get("name") or "",
                date=str(s.get("date") or ""),
                week=s.get("week"),
                status=s.get("status") or "scheduled",
                result=result,
            )
        )

    return CalendarResponse(series=entries)


@router.get("/{series_id}/h2h", response_model=H2HResponse)
def get_h2h(
    series_id: UUID,
    league_id: UUID,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> H2HResponse:
    """
    Returns head-to-head data for a specific series.
    Auth check: user must be a member of the given league.
    """
    _check_membership(supabase, str(league_id), user["id"])

    # 1. Fetch the series record
    series_resp = (
        supabase.table("series")
        .select(
            "id, date, status, winner_id, game_count, team_home_id, team_away_id, competition_id,"
            " home_team:teams!series_team_home_id_fkey(id, name, logo_url),"
            " away_team:teams!series_team_away_id_fkey(id, name, logo_url)"
        )
        .eq("id", str(series_id))
        .single()
        .execute()
    )
    if not series_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Serie no encontrada")

    s = series_resp.data
    competition_id = str(s["competition_id"])
    team_home_id = str(s["team_home_id"])
    team_away_id = str(s["team_away_id"])
    home_team_data = s.get("home_team") or {}
    away_team_data = s.get("away_team") or {}
    home_team_name = home_team_data.get("name") or ""
    away_team_name = away_team_data.get("name") or ""

    # 2. Get result
    winner_id = s.get("winner_id")
    game_count = s.get("game_count") or 0
    result: str | None = None
    if s.get("status") == "finished":
        result = _build_result(winner_id, team_home_id, game_count)

    # 3. Fetch all series in this competition (for win/loss counting)
    all_series_resp = (
        supabase.table("series")
        .select("id, team_home_id, team_away_id, winner_id, status")
        .eq("competition_id", competition_id)
        .execute()
    )
    all_series = all_series_resp.data or []

    # 4. Fetch all active players (for team membership)
    all_players_resp = (
        supabase.table("players")
        .select("id, name, team, role")
        .eq("is_active", True)
        .execute()
    )
    all_players = all_players_resp.data or []

    # Build player_ids by team name for stat queries
    player_ids_by_team: dict[str, list[str]] = {}
    for p in all_players:
        tname = p.get("team") or ""
        player_ids_by_team.setdefault(tname, []).append(p["id"])

    # 5. Build team stats
    team_home_stats = _build_team_stats(
        supabase, team_home_id, home_team_name,
        competition_id, all_series, player_ids_by_team,
    )
    team_away_stats = _build_team_stats(
        supabase, team_away_id, away_team_name,
        competition_id, all_series, player_ids_by_team,
    )

    # 6. Get series IDs for this competition (for player_series_stats queries)
    series_ids_in_comp = [str(s2["id"]) for s2 in all_series]

    # 7. Build player stats for each team
    players_home = _build_players_stats(
        supabase, home_team_name, competition_id, all_players, series_ids_in_comp
    )
    players_away = _build_players_stats(
        supabase, away_team_name, competition_id, all_players, series_ids_in_comp
    )

    return H2HResponse(
        series_id=str(series_id),
        date=str(s.get("date") or ""),
        status=s.get("status") or "scheduled",
        result=result,
        team_home=team_home_stats,
        team_away=team_away_stats,
        players_home=players_home,
        players_away=players_away,
    )
