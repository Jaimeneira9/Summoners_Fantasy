from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from supabase import Client

from auth.dependencies import get_current_user, get_supabase

router = APIRouter()


class SplitOut(BaseModel):
    id: UUID
    name: str
    competition: str
    start_date: str | None
    end_date: str | None
    reset_date: str | None
    is_active: bool


class HistoricalStatsOut(BaseModel):
    split_id: UUID
    split_name: str
    games_played: int
    wins: int
    kills: float
    deaths: float
    assists: float
    kda: float | None
    cspm: float | None
    dpm: float | None
    damage_pct: float | None
    kill_participation: float | None
    wards_per_min: float | None


@router.get("/", response_model=list[SplitOut])
async def list_splits(
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> list[SplitOut]:
    resp = (
        supabase.table("competitions")
        .select("id, name, is_active, start_date, end_date, reset_date")
        .order("created_at", desc=True)
        .execute()
    )
    return [
        SplitOut(
            id=c["id"],
            name=c["name"],
            competition=c["name"],
            start_date=c.get("start_date"),
            end_date=c.get("end_date"),
            reset_date=c.get("reset_date"),
            is_active=c["is_active"],
        )
        for c in (resp.data or [])
    ]


@router.get("/active", response_model=SplitOut | None)
async def get_active_split(
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> SplitOut | None:
    resp = (
        supabase.table("competitions")
        .select("id, name, is_active, start_date, end_date, reset_date")
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    if not resp.data:
        return None
    c = resp.data[0]
    return SplitOut(
        id=c["id"],
        name=c["name"],
        competition=c["name"],
        start_date=c.get("start_date"),
        end_date=c.get("end_date"),
        reset_date=c.get("reset_date"),
        is_active=c["is_active"],
    )


@router.get("/player/{player_id}/history", response_model=list[HistoricalStatsOut])
async def get_player_split_history(
    player_id: UUID,
    supabase: Client = Depends(get_supabase),
    user: dict = Depends(get_current_user),
) -> list[HistoricalStatsOut]:
    """Estadísticas históricas agregadas por competición de un jugador."""
    resp = (
        supabase.table("player_series_stats")
        .select(
            "series_id, games_played, wins, avg_kills, avg_deaths, avg_assists,"
            " avg_cs_per_min, avg_damage_share, avg_dpm, avg_wards_per_min,"
            " kill_participation, series(competition_id, competitions(id, name))"
        )
        .eq("player_id", str(player_id))
        .execute()
    )
    rows = resp.data or []

    # Agrupar por competition_id
    from collections import defaultdict
    comp_data: dict[str, dict] = {}
    comp_names: dict[str, str] = {}

    for row in rows:
        series = row.get("series") or {}
        comp = series.get("competitions") or {}
        comp_id = comp.get("id")
        if not comp_id:
            continue
        comp_names[comp_id] = comp.get("name", "Unknown")
        n = row["games_played"] or 0
        if comp_id not in comp_data:
            comp_data[comp_id] = {
                "total_games": 0,
                "total_wins": 0,
                "sum_kills": 0.0,
                "sum_deaths": 0.0,
                "sum_assists": 0.0,
                "sum_cspm": 0.0,
                "sum_dmg": 0.0,
                "sum_dpm_games": 0.0,
                "dpm_game_count": 0,
                "sum_wards_pm_games": 0.0,
                "wards_pm_game_count": 0,
                "sum_kp_games": 0.0,
                "kp_game_count": 0,
            }
        d = comp_data[comp_id]
        d["total_games"] += n
        d["total_wins"] += row.get("wins") or 0
        d["sum_kills"] += (row.get("avg_kills") or 0) * n
        d["sum_deaths"] += (row.get("avg_deaths") or 0) * n
        d["sum_assists"] += (row.get("avg_assists") or 0) * n
        d["sum_cspm"] += (row.get("avg_cs_per_min") or 0) * n
        d["sum_dmg"] += (row.get("avg_damage_share") or 0) * n
        # Promedios opcionales: solo acumular si el valor existe
        if row.get("avg_dpm") is not None:
            d["sum_dpm_games"] += (row["avg_dpm"]) * n
            d["dpm_game_count"] += n
        if row.get("avg_wards_per_min") is not None:
            d["sum_wards_pm_games"] += (row["avg_wards_per_min"]) * n
            d["wards_pm_game_count"] += n
        if row.get("kill_participation") is not None:
            d["sum_kp_games"] += (row["kill_participation"]) * n
            d["kp_game_count"] += n

    result = []
    for comp_id, d in comp_data.items():
        n = d["total_games"]
        if n == 0:
            continue
        avg_kills = round(d["sum_kills"] / n, 2)
        avg_deaths = round(d["sum_deaths"] / n, 2)
        avg_assists = round(d["sum_assists"] / n, 2)
        kda = round((avg_kills + avg_assists) / max(avg_deaths, 1), 2)
        avg_dpm = (
            round(d["sum_dpm_games"] / d["dpm_game_count"], 2)
            if d["dpm_game_count"] > 0
            else None
        )
        avg_wards_per_min = (
            round(d["sum_wards_pm_games"] / d["wards_pm_game_count"], 3)
            if d["wards_pm_game_count"] > 0
            else None
        )
        avg_kill_participation = (
            round(d["sum_kp_games"] / d["kp_game_count"], 4)
            if d["kp_game_count"] > 0
            else None
        )
        result.append(HistoricalStatsOut(
            split_id=UUID(comp_id),
            split_name=comp_names[comp_id],
            games_played=n,
            wins=d["total_wins"],
            kills=avg_kills,
            deaths=avg_deaths,
            assists=avg_assists,
            kda=kda,
            cspm=round(d["sum_cspm"] / n, 2),
            dpm=avg_dpm,
            damage_pct=round(d["sum_dmg"] / n, 4),
            kill_participation=avg_kill_participation,
            wards_per_min=avg_wards_per_min,
        ))
    return result
