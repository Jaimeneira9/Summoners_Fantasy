from __future__ import annotations

# ---------------------------------------------------------------------------
# Column name reference (verified from supabase/migrations/):
#   games.duration_min         — numeric(6,2), NULL until game finishes
#   games.winner_id            — uuid FK to teams.id, NULL until game finishes
#   player_game_stats.result   — int CHECK (0=loss, 1=win), NULL if not finished
#   player_game_stats.xp_diff_15 — integer, may be NULL
#   player_game_stats.gold_diff_15 — integer, may be NULL
#   player_series_stats.avg_gold_diff_15 — numeric(8,2), may be NULL
#   player_series_stats has NO avg_xp_diff_15 column (not in any migration)
# ---------------------------------------------------------------------------

import logging
from collections import defaultdict
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from supabase import Client

from auth.dependencies import get_current_user, get_supabase
from routers.series import ROLE_ORDER, _check_membership

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------


class PlayerGameStatRow(BaseModel):
    player_id: str
    name: str
    role: str
    image_url: str | None
    team_id: str
    kills: float
    deaths: float
    assists: float
    game_points: float | None
    gold_diff_15: float | None
    xp_diff_15: float | None
    result: int | None  # 1=win, 0=loss, None if not finished


class PlayerSeriesStatRow(BaseModel):
    player_id: str
    name: str
    role: str
    image_url: str | None
    team_id: str
    games_played: int
    series_points: float
    avg_kills: float
    avg_deaths: float
    avg_assists: float
    avg_gold_diff_15: float | None
    avg_xp_diff_15: float | None  # always None — not in player_series_stats


class GameDetailData(BaseModel):
    game_id: str
    game_number: int
    duration_min: float | None
    winner_team_id: str | None  # maps to games.winner_id
    players: list[PlayerGameStatRow]


class TeamDetailInfo(BaseModel):
    id: str
    name: str
    logo_url: str | None
    score: int  # games won in the series


class MatchDetailPlayed(BaseModel):
    series_id: str
    status: str
    score_home: int
    score_away: int
    team_home: TeamDetailInfo
    team_away: TeamDetailInfo
    games: list[GameDetailData]
    series_stats: list[PlayerSeriesStatRow]


class PlayerSeasonAvgRow(BaseModel):
    player_id: str
    name: str
    role: str
    image_url: str | None
    team_id: str
    games_played: int
    avg_points: float | None
    avg_kills: float
    avg_deaths: float
    avg_assists: float
    avg_gold_diff_15: float | None  # null — player_series_stats has no avg_xp_diff_15
    avg_xp_diff_15: float | None    # always null — not in player_series_stats


class MatchDetailUpcoming(BaseModel):
    series_id: str
    status: str
    scheduled_at: str | None
    team_home: TeamDetailInfo
    team_away: TeamDetailInfo
    season_averages: list[PlayerSeasonAvgRow]


class MatchDetailEnvelope(BaseModel):
    mode: Literal["played", "upcoming"]
    played: MatchDetailPlayed | None = None
    upcoming: MatchDetailUpcoming | None = None


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _safe_avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


def _fetch_game_stats(
    supabase: Client, series_id: str
) -> tuple[list[dict], list[dict]]:
    """
    Returns (games_rows, player_stats_rows).
    Single batch query for all player_game_stats — no N+1.
    """
    games_resp = (
        supabase.table("games")
        .select("id, game_number, duration_min, winner_id")
        .eq("series_id", series_id)
        .order("game_number", desc=False)
        .execute()
    )
    games_rows = games_resp.data or []

    if not games_rows:
        return games_rows, []

    game_ids = [g["id"] for g in games_rows]

    pgs_resp = (
        supabase.table("player_game_stats")
        .select(
            "game_id, player_id, kills, deaths, assists, game_points,"
            " gold_diff_15, xp_diff_15, result,"
            " players(name, role, image_url, team)"
        )
        .in_("game_id", game_ids)
        .execute()
    )
    player_stats_rows = pgs_resp.data or []

    return games_rows, player_stats_rows


def _resolve_canonical_team_name(
    raw_team: str,
    home_team_data: dict,
    away_team_data: dict,
) -> str:
    """
    Maps a raw team name (e.g. 'G2' from players.team) to the canonical full
    team name used by TeamDetailInfo (e.g. 'G2 Esports' from teams.name).

    Checks against aliases[] for each team; falls back to the raw value.
    """
    raw_lower = raw_team.strip().lower()

    for team_data in (home_team_data, away_team_data):
        canonical_name: str = team_data.get("name") or ""
        aliases: list[str] = team_data.get("aliases") or []
        # Include the canonical name itself as an implicit alias
        all_names = [canonical_name] + aliases
        for alias in all_names:
            if alias.strip().lower() == raw_lower:
                return canonical_name

    # No match found — return as-is (will result in an empty section, visible
    # in logs via the warning below, rather than a silent mismatch)
    logger.warning(
        "Could not resolve team name '%s' to any known team (home='%s', away='%s')",
        raw_team,
        home_team_data.get("name"),
        away_team_data.get("name"),
    )
    return raw_team


def _build_played(
    series: dict,
    games_rows: list[dict],
    player_stats_rows: list[dict],
) -> MatchDetailPlayed:
    """Build MatchDetailPlayed from pre-fetched data."""
    series_id = str(series["id"])
    team_home_id = str(series["team_home_id"])
    team_away_id = str(series["team_away_id"])
    home_team_data = series.get("home_team") or {}
    away_team_data = series.get("away_team") or {}

    # Group player stats by game_id
    stats_by_game: dict[str, list[dict]] = defaultdict(list)
    for row in player_stats_rows:
        stats_by_game[row["game_id"]].append(row)

    # Count scores (games won per team)
    score_home = 0
    score_away = 0
    for g in games_rows:
        winner = g.get("winner_id")
        if winner == team_home_id:
            score_home += 1
        elif winner == team_away_id:
            score_away += 1

    # Build GameDetailData list
    games_detail: list[GameDetailData] = []
    for g in games_rows:
        gid = g["id"]
        rows = stats_by_game.get(gid, [])

        player_rows: list[PlayerGameStatRow] = []
        for row in rows:
            p = row.get("players") or {}
            raw_team = str(p.get("team") or "")
            canonical_team = _resolve_canonical_team_name(raw_team, home_team_data, away_team_data)
            player_rows.append(
                PlayerGameStatRow(
                    player_id=str(row["player_id"]),
                    name=p.get("name") or "",
                    role=p.get("role") or "unknown",
                    image_url=p.get("image_url"),
                    team_id=canonical_team,
                    kills=float(row.get("kills") or 0),
                    deaths=float(row.get("deaths") or 0),
                    assists=float(row.get("assists") or 0),
                    game_points=float(row["game_points"]) if row.get("game_points") is not None else None,
                    gold_diff_15=float(row["gold_diff_15"]) if row.get("gold_diff_15") is not None else None,
                    xp_diff_15=float(row["xp_diff_15"]) if row.get("xp_diff_15") is not None else None,
                    result=int(row["result"]) if row.get("result") is not None else None,
                )
            )

        # Sort by ROLE_ORDER
        player_rows.sort(key=lambda x: ROLE_ORDER.get(x.role, 99))

        winner_id = g.get("winner_id")
        games_detail.append(
            GameDetailData(
                game_id=gid,
                game_number=g["game_number"],
                duration_min=float(g["duration_min"]) if g.get("duration_min") is not None else None,
                winner_team_id=str(winner_id) if winner_id else None,
                players=player_rows,
            )
        )

    # Build series_stats: aggregate per player across all games
    agg: dict[str, dict] = {}
    for row in player_stats_rows:
        pid = str(row["player_id"])
        p = row.get("players") or {}
        if pid not in agg:
            raw_team = str(p.get("team") or "")
            canonical_team = _resolve_canonical_team_name(raw_team, home_team_data, away_team_data)
            agg[pid] = {
                "player_id": pid,
                "name": p.get("name") or "",
                "role": p.get("role") or "unknown",
                "image_url": p.get("image_url"),
                "team_id": canonical_team,
                "kills": [],
                "deaths": [],
                "assists": [],
                "game_points": [],
                "gold_diff_15": [],
                "xp_diff_15": [],
            }
        agg[pid]["kills"].append(float(row.get("kills") or 0))
        agg[pid]["deaths"].append(float(row.get("deaths") or 0))
        agg[pid]["assists"].append(float(row.get("assists") or 0))
        if row.get("game_points") is not None:
            agg[pid]["game_points"].append(float(row["game_points"]))
        if row.get("gold_diff_15") is not None:
            agg[pid]["gold_diff_15"].append(float(row["gold_diff_15"]))
        if row.get("xp_diff_15") is not None:
            agg[pid]["xp_diff_15"].append(float(row["xp_diff_15"]))

    series_stats: list[PlayerSeriesStatRow] = []
    for pid, data in agg.items():
        games_played = len(data["kills"])
        series_points = sum(data["game_points"])
        avg_gold = _safe_avg(data["gold_diff_15"]) if data["gold_diff_15"] else None
        avg_xp = _safe_avg(data["xp_diff_15"]) if data["xp_diff_15"] else None
        series_stats.append(
            PlayerSeriesStatRow(
                player_id=pid,
                name=data["name"],
                role=data["role"],
                image_url=data["image_url"],
                team_id=data["team_id"],
                games_played=games_played,
                series_points=round(series_points, 2),
                avg_kills=_safe_avg(data["kills"]),
                avg_deaths=_safe_avg(data["deaths"]),
                avg_assists=_safe_avg(data["assists"]),
                avg_gold_diff_15=avg_gold,
                avg_xp_diff_15=avg_xp,
            )
        )

    series_stats.sort(key=lambda x: ROLE_ORDER.get(x.role, 99))

    return MatchDetailPlayed(
        series_id=series_id,
        status=series.get("status") or "finished",
        score_home=score_home,
        score_away=score_away,
        team_home=TeamDetailInfo(
            id=team_home_id,
            name=home_team_data.get("name") or "",
            logo_url=home_team_data.get("logo_url"),
            score=score_home,
        ),
        team_away=TeamDetailInfo(
            id=team_away_id,
            name=away_team_data.get("name") or "",
            logo_url=away_team_data.get("logo_url"),
            score=score_away,
        ),
        games=games_detail,
        series_stats=series_stats,
    )


def _build_upcoming(supabase: Client, series: dict) -> MatchDetailUpcoming:
    """Build MatchDetailUpcoming with season averages from player_series_stats."""
    series_id = str(series["id"])
    team_home_id = str(series["team_home_id"])
    team_away_id = str(series["team_away_id"])
    competition_id = str(series["competition_id"])
    home_team_data = series.get("home_team") or {}
    away_team_data = series.get("away_team") or {}

    # 1. Fetch all finished series_ids in this competition
    finished_resp = (
        supabase.table("series")
        .select("id")
        .eq("competition_id", competition_id)
        .eq("status", "finished")
        .execute()
    )
    finished_series_ids = [str(r["id"]) for r in (finished_resp.data or [])]

    # 2. Fetch active players for both teams
    # players.team stores a short/alias name (e.g. "G2"), not the full teams.name.
    # Build the full set of aliases for each team so the query matches regardless
    # of which alias was used when the player row was created.
    home_team_name = home_team_data.get("name") or ""
    away_team_name = away_team_data.get("name") or ""
    home_aliases: list[str] = home_team_data.get("aliases") or []
    away_aliases: list[str] = away_team_data.get("aliases") or []
    # Include the canonical name itself (may not be in aliases column)
    all_team_values = list({home_team_name} | set(home_aliases) | {away_team_name} | set(away_aliases))
    players_resp = (
        supabase.table("players")
        .select("id, name, role, image_url, team")
        .in_("team", all_team_values)
        .eq("is_active", True)
        .execute()
    )
    all_players = players_resp.data or []
    player_ids = [str(p["id"]) for p in all_players]

    # 3. Fetch player_series_stats for these players in finished series
    season_avgs: list[PlayerSeasonAvgRow] = []

    if player_ids and finished_series_ids:
        pss_resp = (
            supabase.table("player_series_stats")
            .select(
                "player_id, series_id, games_played, series_points,"
                " avg_kills, avg_deaths, avg_assists, avg_gold_diff_15"
            )
            .in_("player_id", player_ids)
            .in_("series_id", finished_series_ids)
            .execute()
        )
        pss_rows = pss_resp.data or []

        # Aggregate by player_id
        pss_by_player: dict[str, list[dict]] = defaultdict(list)
        for row in pss_rows:
            pss_by_player[str(row["player_id"])].append(row)

        # Build player info lookup
        player_info: dict[str, dict] = {str(p["id"]): p for p in all_players}

        for pid in player_ids:
            info = player_info.get(pid, {})
            rows = pss_by_player.get(pid, [])

            if not rows:
                # Player has no stats — include with zeros
                raw_team = str(info.get("team") or "")
                season_avgs.append(
                    PlayerSeasonAvgRow(
                        player_id=pid,
                        name=info.get("name") or "",
                        role=info.get("role") or "unknown",
                        image_url=info.get("image_url"),
                        team_id=_resolve_canonical_team_name(raw_team, home_team_data, away_team_data),
                        games_played=0,
                        avg_points=None,
                        avg_kills=0.0,
                        avg_deaths=0.0,
                        avg_assists=0.0,
                        avg_gold_diff_15=None,
                        avg_xp_diff_15=None,
                    )
                )
                continue

            total_games = sum(r.get("games_played") or 0 for r in rows)

            # Weighted averages: each series contributes avg * games_played, then divide by
            # total_games. This avoids the "average of averages" problem when series have
            # different game counts (e.g. 3-game series vs 1-game series).
            def _weighted_avg(field: str) -> float:
                total_weighted = 0.0
                total_w = 0
                for r in rows:
                    val = r.get(field)
                    gp = r.get("games_played") or 0
                    if val is not None and gp > 0:
                        total_weighted += float(val) * gp
                        total_w += gp
                return round(total_weighted / total_w, 2) if total_w > 0 else 0.0

            def _weighted_avg_optional(field: str) -> float | None:
                total_weighted = 0.0
                total_w = 0
                for r in rows:
                    val = r.get(field)
                    gp = r.get("games_played") or 0
                    if val is not None and gp > 0:
                        total_weighted += float(val) * gp
                        total_w += gp
                return round(total_weighted / total_w, 2) if total_w > 0 else None

            # avg_points: total points across all series / number of series played
            points_list = [float(r["series_points"]) for r in rows if r.get("series_points") is not None]
            avg_pts = round(sum(points_list) / len(points_list), 2) if points_list else None

            raw_team = str(info.get("team") or "")
            season_avgs.append(
                PlayerSeasonAvgRow(
                    player_id=pid,
                    name=info.get("name") or "",
                    role=info.get("role") or "unknown",
                    image_url=info.get("image_url"),
                    team_id=_resolve_canonical_team_name(raw_team, home_team_data, away_team_data),
                    games_played=total_games,
                    avg_points=avg_pts,
                    avg_kills=_weighted_avg("avg_kills"),
                    avg_deaths=_weighted_avg("avg_deaths"),
                    avg_assists=_weighted_avg("avg_assists"),
                    avg_gold_diff_15=_weighted_avg_optional("avg_gold_diff_15"),
                    avg_xp_diff_15=None,  # not stored in player_series_stats
                )
            )

    season_avgs.sort(key=lambda x: (x.team_id != home_team_name, ROLE_ORDER.get(x.role, 99)))

    return MatchDetailUpcoming(
        series_id=series_id,
        status=series.get("status") or "scheduled",
        scheduled_at=str(series["date"]) if series.get("date") else None,
        team_home=TeamDetailInfo(
            id=team_home_id,
            name=home_team_data.get("name") or "",
            logo_url=home_team_data.get("logo_url"),
            score=0,
        ),
        team_away=TeamDetailInfo(
            id=team_away_id,
            name=away_team_data.get("name") or "",
            logo_url=away_team_data.get("logo_url"),
            score=0,
        ),
        season_averages=season_avgs,
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/{series_id}/match-detail", response_model=MatchDetailEnvelope)
def get_match_detail(
    series_id: UUID,
    league_id: UUID,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> MatchDetailEnvelope:
    """
    Unified match detail endpoint.
    Returns mode='played' for finished/in_progress series with game-by-game stats.
    Returns mode='upcoming' for scheduled series with season averages.
    """
    _check_membership(supabase, str(league_id), user["id"])

    # Fetch series with team info
    series_resp = (
        supabase.table("series")
        .select(
            "id, date, status, team_home_id, team_away_id, competition_id,"
            " home_team:teams!series_team_home_id_fkey(id, name, logo_url, aliases),"
            " away_team:teams!series_team_away_id_fkey(id, name, logo_url, aliases)"
        )
        .eq("id", str(series_id))
        .single()
        .execute()
    )
    if not series_resp.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Serie no encontrada")

    s = series_resp.data
    series_status = s.get("status") or "scheduled"

    if series_status in ("finished", "in_progress"):
        games_rows, player_stats_rows = _fetch_game_stats(supabase, str(series_id))
        played = _build_played(s, games_rows, player_stats_rows)
        return MatchDetailEnvelope(mode="played", played=played, upcoming=None)
    else:
        upcoming = _build_upcoming(supabase, s)
        return MatchDetailEnvelope(mode="upcoming", played=None, upcoming=upcoming)
