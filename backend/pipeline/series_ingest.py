"""
Orquestador de ingestión de series desde gol.gg.

Flujo principal:
  1. Obtener gol_gg_slug de competitions WHERE is_active=True
  2. Fetch matchlist → lista de GameEntry
  3. Resolver team_home_id y team_away_id via teams.aliases
  4. Upsert series (UNIQUE: team_home_id, team_away_id, date)
  5. Por cada game: fetch fullstats + meta
  6. Upsert games
  7. Por cada jugador: resolver player_id, calcular puntos, upsert player_game_stats
  8. Calcular promedios de serie → upsert player_series_stats
  9. Actualizar series.game_count y series.winner_id
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import date
from typing import List

from supabase import Client

from pipeline.gol_gg import (
    GameEntry,
    GameMeta,
    PlayerRawStats,
    fetch_game_fullstats,
    fetch_game_meta,
    fetch_matchlist,
)
from scoring.engine import calculate_match_points

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Team resolution
# ---------------------------------------------------------------------------


def _resolve_team_by_alias(supabase: Client, team_name: str) -> str | None:
    """
    Resuelve el UUID de un equipo buscando team_name en el array aliases.
    Usa búsqueda case-insensitive con ilike sobre el array serializado.

    Returns UUID str o None si no se encuentra.
    """
    try:
        # Supabase no soporta ilike directo en arrays, usamos cs (contains)
        # primero intentamos match exacto en el array
        result = (
            supabase.table("teams")
            .select("id, name, aliases")
            .contains("aliases", [team_name])
            .limit(1)
            .execute()
        )
        if result.data:
            return str(result.data[0]["id"])

        # Fallback: comparación case-insensitive trayendo todos los equipos
        # (la tabla de equipos es pequeña ~20 equipos LEC)
        all_teams = supabase.table("teams").select("id, name, aliases").execute()
        for team in all_teams.data or []:
            aliases: list[str] = team.get("aliases") or []
            # Incluir el nombre del equipo también como alias implícito
            all_names = [team["name"]] + aliases
            for alias in all_names:
                if alias.strip().lower() == team_name.strip().lower():
                    return str(team["id"])

    except Exception as exc:
        logger.error("DB error resolving team '%s': %s", team_name, exc)

    logger.warning("Team not found by alias: '%s'", team_name)
    return None


# ---------------------------------------------------------------------------
# Player resolution
# ---------------------------------------------------------------------------


def _resolve_player_id(supabase: Client, player_name: str) -> str | None:
    """
    Resuelve el UUID del jugador por nombre (case-insensitive).
    """
    try:
        # Intento exacto primero
        result = (
            supabase.table("players")
            .select("id")
            .eq("name", player_name)
            .limit(1)
            .execute()
        )
        if result.data:
            return str(result.data[0]["id"])

        # Fallback ilike para case-insensitive
        result = (
            supabase.table("players")
            .select("id")
            .ilike("name", player_name)
            .limit(1)
            .execute()
        )
        if result.data:
            return str(result.data[0]["id"])

    except Exception as exc:
        logger.error("DB error resolving player '%s': %s", player_name, exc)

    logger.warning("Player not found in DB: '%s'", player_name)
    return None


# ---------------------------------------------------------------------------
# Series upsert
# ---------------------------------------------------------------------------


def _upsert_series(
    supabase: Client,
    competition_id: str,
    team_home_id: str,
    team_away_id: str,
    game_date: date,
    week: int,
) -> str | None:
    """
    Upsert de la serie. Devuelve el UUID de la serie o None si falla.
    UNIQUE constraint: (team_home_id, team_away_id, date)
    """
    payload = {
        "competition_id": competition_id,
        "team_home_id": team_home_id,
        "team_away_id": team_away_id,
        "date": game_date.isoformat(),
        "week": week,
        "status": "finished",
    }
    try:
        result = (
            supabase.table("series")
            .upsert(
                payload,
                on_conflict="team_home_id,team_away_id,date",
            )
            .execute()
        )
        if result.data:
            return str(result.data[0]["id"])

        # Si el upsert no devolvió data (duplicate ignorado), buscar el existente
        existing = (
            supabase.table("series")
            .select("id")
            .eq("team_home_id", team_home_id)
            .eq("team_away_id", team_away_id)
            .eq("date", game_date.isoformat())
            .limit(1)
            .execute()
        )
        if existing.data:
            return str(existing.data[0]["id"])

    except Exception as exc:
        logger.error(
            "Failed to upsert series (home=%s, away=%s, date=%s): %s",
            team_home_id,
            team_away_id,
            game_date,
            exc,
        )
    return None


# ---------------------------------------------------------------------------
# Game upsert
# ---------------------------------------------------------------------------


def _upsert_game(
    supabase: Client,
    series_id: str,
    game_number: int,
    team_home_id: str,
    team_away_id: str,
    meta: GameMeta,
    winner_team_id: str | None,
) -> str | None:
    """
    Upsert del game. Devuelve el UUID del game o None si falla.
    UNIQUE constraint: (series_id, game_number)
    """
    payload = {
        "series_id": series_id,
        "game_number": game_number,
        "team_home_id": team_home_id,
        "team_away_id": team_away_id,
        "duration_min": meta.duration_min,
        "winner_id": winner_team_id,
        "status": "finished",
    }
    try:
        result = (
            supabase.table("games")
            .upsert(
                payload,
                on_conflict="series_id,game_number",
            )
            .execute()
        )
        if result.data:
            return str(result.data[0]["id"])

        existing = (
            supabase.table("games")
            .select("id")
            .eq("series_id", series_id)
            .eq("game_number", game_number)
            .limit(1)
            .execute()
        )
        if existing.data:
            return str(existing.data[0]["id"])

    except Exception as exc:
        logger.error(
            "Failed to upsert game (series=%s, game_number=%d): %s",
            series_id,
            game_number,
            exc,
        )
    return None


# ---------------------------------------------------------------------------
# Player game stats upsert
# ---------------------------------------------------------------------------


def _upsert_player_game_stats(
    supabase: Client,
    player_id: str,
    game_id: str,
    stats: PlayerRawStats,
    game_points: float,
) -> None:
    """Upsert de player_game_stats."""
    payload = {
        "player_id": player_id,
        "game_id": game_id,
        "kills": stats.kills,
        "deaths": stats.deaths,
        "assists": stats.assists,
        "cs_per_min": stats.cs_per_min,
        "gold_diff_15": stats.gold_diff_15,
        "vision_score": stats.vision_score,
        "damage_share": stats.damage_share,
        "objective_steals": stats.objective_steals,
        "double_kill": stats.double_kill,
        "triple_kill": stats.triple_kill,
        "quadra_kill": stats.quadra_kill,
        "penta_kill": stats.penta_kill,
        "dpm": stats.dpm,
        "wards_placed": stats.wards_placed,
        "wards_destroyed": stats.wards_destroyed,
        "solo_kills": stats.solo_kills,
        "xp_diff_15": stats.xp_diff_15,
        "turret_damage": stats.turret_damage,
        "result": stats.result,
        "game_points": game_points,
    }
    try:
        supabase.table("player_game_stats").upsert(
            payload,
            on_conflict="player_id,game_id",
        ).execute()
    except Exception as exc:
        logger.error(
            "Failed to upsert player_game_stats (player=%s, game=%s): %s",
            player_id,
            game_id,
            exc,
        )


# ---------------------------------------------------------------------------
# Series stats calculation
# ---------------------------------------------------------------------------


def _best_multikill(game_stats_list: list[PlayerRawStats]) -> str | None:
    """
    Retorna el mejor multikill conseguido en cualquier game de la serie.
    Orden: penta > quadra > triple > double > None
    """
    if any(s.penta_kill for s in game_stats_list):
        return "penta"
    if any(s.quadra_kill for s in game_stats_list):
        return "quadra"
    if any(s.triple_kill for s in game_stats_list):
        return "triple"
    if any(s.double_kill for s in game_stats_list):
        return "double"
    return None


def _upsert_player_series_stats(
    supabase: Client,
    player_id: str,
    series_id: str,
    game_stats_list: list[PlayerRawStats],
    game_points_list: list[float],
    game_durations_list: list[float] | None = None,
) -> None:
    """
    Calcula promedios de la serie y hace upsert de player_series_stats.

    game_durations_list: duración en minutos de cada game (mismo orden que game_stats_list).
    Se usa para calcular avg_wards_per_min.
    """
    n = len(game_stats_list)
    if n == 0:
        return

    def _avg(values: list[float | int]) -> float:
        return round(sum(values) / n, 4)

    def _avg_optional(values: list[int | None]) -> float | None:
        valid = [v for v in values if v is not None]
        if not valid:
            return None
        return round(sum(valid) / len(valid), 4)

    # avg_dpm: promedio de dpm por game en la serie
    avg_dpm: float | None = None
    dpm_values = [s.dpm for s in game_stats_list if s.dpm is not None and s.dpm > 0]
    if dpm_values:
        avg_dpm = round(sum(dpm_values) / len(dpm_values), 2)

    # avg_wards_per_min: (wards_placed + wards_destroyed) / duration_min por game, luego promedio
    avg_wards_per_min: float | None = None
    if game_durations_list and len(game_durations_list) == n:
        wpm_values: list[float] = []
        for s, dur in zip(game_stats_list, game_durations_list):
            if dur and dur > 0:
                wpm = (s.wards_placed + s.wards_destroyed) / dur
                wpm_values.append(wpm)
        if wpm_values:
            avg_wards_per_min = round(sum(wpm_values) / len(wpm_values), 3)

    payload = {
        "player_id": player_id,
        "series_id": series_id,
        "games_played": n,
        "avg_kills": _avg([s.kills for s in game_stats_list]),
        "avg_deaths": _avg([s.deaths for s in game_stats_list]),
        "avg_assists": _avg([s.assists for s in game_stats_list]),
        "avg_cs_per_min": _avg([s.cs_per_min for s in game_stats_list]),
        "avg_gold_diff_15": _avg_optional([s.gold_diff_15 for s in game_stats_list]),
        "avg_vision_score": _avg([s.vision_score for s in game_stats_list]),
        "avg_damage_share": _avg([s.damage_share for s in game_stats_list]),
        "avg_objective_steals": _avg([s.objective_steals for s in game_stats_list]),
        "wins": sum(1 for s in game_stats_list if s.result == 1),
        "best_multikill": _best_multikill(game_stats_list),
        "series_points": round(sum(game_points_list) / len(game_points_list), 2) if game_points_list else 0.0,
        "avg_dpm": avg_dpm,
        "avg_wards_per_min": avg_wards_per_min,
        # kill_participation requiere team_kills, que no está disponible en PlayerRawStats.
        # Se calcula en el backfill SQL via player_game_stats JOIN games.
    }
    try:
        supabase.table("player_series_stats").upsert(
            payload,
            on_conflict="player_id,series_id",
        ).execute()
    except Exception as exc:
        logger.error(
            "Failed to upsert player_series_stats (player=%s, series=%s): %s",
            player_id,
            series_id,
            exc,
        )


# ---------------------------------------------------------------------------
# Serie winner y game_count update
# ---------------------------------------------------------------------------


def _update_series_result(
    supabase: Client,
    series_id: str,
    game_count: int,
    winner_id: str | None,
) -> None:
    """Actualiza game_count y winner_id en la serie."""
    payload: dict = {"game_count": game_count}
    if winner_id:
        payload["winner_id"] = winner_id
    try:
        supabase.table("series").update(payload).eq("id", series_id).execute()
    except Exception as exc:
        logger.error("Failed to update series %s result: %s", series_id, exc)


# ---------------------------------------------------------------------------
# Validación de game_id
# ---------------------------------------------------------------------------


def _game_belongs_to_series(
    supabase: Client,
    meta: GameMeta,
    team_home_id: str,
    team_away_id: str,
) -> bool:
    """
    Verifica que el game scrapeado pertenezca a la serie esperada.

    Resuelve los nombres scrapeados del game (winner_team / loser_team) a UUIDs
    de equipo via aliases — igual que se hace para los equipos del matchlist —
    y compara los IDs resultantes contra team_home_id y team_away_id.

    Esto evita el problema de substring matching entre nombres cortos del
    matchlist ("NAVI") y nombres completos del game page ("Natus Vincere"):
      "navi" in "natus vincere" → False  (bug anterior)
      resolve("Natus Vincere") == resolve("NAVI") → True  (fix)

    Devuelve True si al menos un equipo del game coincide con alguno de los
    equipos esperados de la serie.
    Devuelve False si ninguno coincide — señal de que el game_id es incorrecto.

    Si no hay suficiente información en el meta (winner_team y loser_team ambos
    vacíos), no puede validar y asume válido para no descartar games legítimos.
    """
    # Sin información suficiente: no podemos validar, asumir válido
    if not meta.winner_team and not meta.loser_team:
        return True

    series_ids = {team_home_id, team_away_id}

    for scraped_name in (meta.winner_team, meta.loser_team):
        if not scraped_name:
            continue
        resolved_id = _resolve_team_by_alias(supabase, scraped_name)
        if resolved_id and resolved_id in series_ids:
            return True

    return False


# ---------------------------------------------------------------------------
# Procesamiento de un game individual
# ---------------------------------------------------------------------------


async def _process_game(
    supabase: Client,
    series_id: str,
    game_number: int,
    entry: GameEntry,
    team_home_id: str,
    team_away_id: str,
    # acumulador para stats de serie (player_id → list[(stats, points, duration_min)])
    series_player_stats: dict[str, list[tuple[PlayerRawStats, float, float]]],
    unresolved_players: List[str],
    # game_ids que ya tenían stats en la DB antes de este run
    existing_game_ids: set[str],
    # acumulador de player_ids con stats NUEVAS (para price update)
    new_price_player_ids: set[str],
) -> tuple[str | None, str | None]:
    """
    Procesa un game individual: fetch stats + meta, upsert games y player_game_stats.

    Returns:
        (game_db_id, winner_team_id) — ambos pueden ser None si algo falla.
    """
    game_id = entry.game_id

    # Fetch secuencial para respetar rate limit de Cloudflare
    try:
        fullstats = await fetch_game_fullstats(game_id)
        meta = await fetch_game_meta(game_id)
    except Exception as exc:
        logger.error("Failed to fetch data for game %s: %s", game_id, exc)
        return None, None

    # Validar que el game_id corresponda a esta serie.
    # gol.gg no garantiza IDs consecutivos: el ID del game 1 viene del HTML del
    # matchlist, pero los IDs de game 2, 3, etc. se construyen como base_id+1,
    # base_id+2. Si hay gaps en los IDs, se scrapearía un game de otra serie.
    if not _game_belongs_to_series(supabase, meta, team_home_id, team_away_id):
        logger.error(
            "[INVALID GAME ID] game_id=%s scraped teams (winner='%s', loser='%s') "
            "do not match expected series home_id=%s vs away_id=%s — skipping game",
            game_id,
            meta.winner_team,
            meta.loser_team,
            team_home_id,
            team_away_id,
        )
        return None, None

    # Resolver equipo ganador
    winner_team_id: str | None = None
    if meta.winner_team:
        winner_name_lower = meta.winner_team.strip().lower()
        # Intentar match con home o away
        home_resp = supabase.table("teams").select("name").eq("id", team_home_id).single().execute()
        away_resp = supabase.table("teams").select("name").eq("id", team_away_id).single().execute()
        home_name = (home_resp.data or {}).get("name", "").lower()
        away_name = (away_resp.data or {}).get("name", "").lower()

        if winner_name_lower in home_name or home_name in winner_name_lower:
            winner_team_id = team_home_id
        elif winner_name_lower in away_name or away_name in winner_name_lower:
            winner_team_id = team_away_id
        else:
            # Intentar resolución por alias completa
            winner_team_id = _resolve_team_by_alias(supabase, meta.winner_team)

        if winner_team_id is None:
            logger.warning(
                "[WINNER UNRESOLVED] game %s — winner_team='%s' no matchea home='%s' ni away='%s'",
                entry.game_id,
                meta.winner_team,
                home_name,
                away_name,
            )

    # Upsert game en DB
    game_db_id = _upsert_game(
        supabase,
        series_id=series_id,
        game_number=game_number,
        team_home_id=team_home_id,
        team_away_id=team_away_id,
        meta=meta,
        winner_team_id=winner_team_id,
    )
    if not game_db_id:
        logger.error("Could not upsert game %s in DB", game_id)
        return None, winner_team_id

    # Setear result en cada PlayerRawStats (1=win, 0=loss)
    for i, stats in enumerate(fullstats):
        # Los primeros 5 son home team, los últimos 5 son away team
        is_home = i < 5
        if winner_team_id == team_home_id:
            stats.result = 1 if is_home else 0
        elif winner_team_id == team_away_id:
            stats.result = 0 if is_home else 1
        else:
            stats.result = None  # desconocido → no contaminar con derrota falsa

    # Upsert player_game_stats
    for stats in fullstats:
        player_id = _resolve_player_id(supabase, stats.player_name)
        if not player_id:
            logger.warning(
                "[UNRESOLVED PLAYER] '%s' not found in players table — stats discarded",
                stats.player_name,
            )
            unresolved_players.append(stats.player_name)
            continue

        game_points = calculate_match_points(
            stats=stats.model_dump(),
            role=stats.role,  # type: ignore[arg-type]
            game_duration_min=meta.duration_min,
        )

        _upsert_player_game_stats(supabase, player_id, game_db_id, stats, game_points)

        # Acumular para series stats (stats, puntos, duración del game)
        series_player_stats[player_id].append((stats, game_points, meta.duration_min))

        # Solo marcar para price update si este game es NUEVO (no estaba en la DB antes del run)
        if game_db_id not in existing_game_ids:
            new_price_player_ids.add(player_id)

    return game_db_id, winner_team_id


# ---------------------------------------------------------------------------
# Procesamiento de una serie completa
# ---------------------------------------------------------------------------


async def _process_series(
    supabase: Client,
    competition_id: str,
    series_entries: list[GameEntry],
    team_home_id: str,
    team_away_id: str,
    existing_game_ids: set[str],
    new_price_player_ids: set[str],
) -> tuple[set[str], str | None]:
    """
    Procesa todos los games de una serie:
    - Upsert series
    - Procesa cada game en orden
    - Calcula stats de serie
    - Actualiza series con winner y game_count

    Returns:
        Tuple (set de player_ids procesados, series_id o None si falló).
    """
    if not series_entries:
        return set(), None

    first = series_entries[0]
    series_id = _upsert_series(
        supabase,
        competition_id=competition_id,
        team_home_id=team_home_id,
        team_away_id=team_away_id,
        game_date=first.date,
        week=first.week,
    )
    if not series_id:
        logger.error(
            "Could not upsert series for %s vs %s on %s",
            first.team_home,
            first.team_away,
            first.date,
        )
        return set(), None

    # Acumulador: player_id → [(PlayerRawStats, game_points, duration_min), ...]
    series_player_stats: dict[str, list[tuple[PlayerRawStats, float, float]]] = defaultdict(list)

    # Acumulador de jugadores no resueltos para loggear resumen al final
    unresolved_players: List[str] = []

    # Conteo de victorias por equipo para determinar winner de la serie
    home_wins = 0
    away_wins = 0

    for game_number, entry in enumerate(series_entries, start=1):
        _, winner_team_id = await _process_game(
            supabase,
            series_id=series_id,
            game_number=game_number,
            entry=entry,
            team_home_id=team_home_id,
            team_away_id=team_away_id,
            series_player_stats=series_player_stats,
            unresolved_players=unresolved_players,
            existing_game_ids=existing_game_ids,
            new_price_player_ids=new_price_player_ids,
        )
        if winner_team_id == team_home_id:
            home_wins += 1
        elif winner_team_id == team_away_id:
            away_wins += 1

    # Determinar winner de la serie
    series_winner_id: str | None = None
    if home_wins > away_wins:
        series_winner_id = team_home_id
    elif away_wins > home_wins:
        series_winner_id = team_away_id

    # Upsert player_series_stats
    for player_id, game_data in series_player_stats.items():
        stats_list = [d[0] for d in game_data]
        points_list = [d[1] for d in game_data]
        durations_list = [d[2] for d in game_data]
        _upsert_player_series_stats(
            supabase, player_id, series_id, stats_list, points_list, durations_list
        )

    # Actualizar series con resultado final
    total_games = len(series_entries)
    _update_series_result(supabase, series_id, total_games, series_winner_id)

    if unresolved_players:
        unique_unresolved = sorted(set(unresolved_players))
        logger.warning(
            "[UNRESOLVED PLAYERS SUMMARY] %d unresolved player name(s) in series %s vs %s (%s): %s",
            len(unique_unresolved),
            first.team_home,
            first.team_away,
            first.date,
            ", ".join(f"'{p}'" for p in unique_unresolved),
        )

    logger.info(
        "Series %s vs %s (%s) processed: %d games, winner=%s",
        first.team_home,
        first.team_away,
        first.date,
        total_games,
        series_winner_id,
    )

    return set(series_player_stats.keys()), series_id


# ---------------------------------------------------------------------------
# Lineup snapshot (idempotente — se toma una vez por semana)
# ---------------------------------------------------------------------------


def _take_lineup_snapshot_if_needed(
    supabase: Client,
    week: int,
    competition_id: str,
) -> None:
    """Take a one-time snapshot of all managers' starter slots for this week.
    Idempotent: exits immediately if snapshot already exists for (competition_id, week).
    """
    # Check if snapshot already exists
    existing = (
        supabase.table("lineup_snapshots")
        .select("id")
        .eq("competition_id", competition_id)
        .eq("week", week)
        .limit(1)
        .execute()
    )
    if existing.data:
        logger.info("Lineup snapshot already exists for week=%d — skipping", week)
        return

    # Fetch all leagues for this competition (via fantasy_leagues; filter by competition text or
    # just take all active league_members since fantasy_leagues has no competition_id FK)
    # Strategy: snapshot ALL league_members regardless of competition — they all share the
    # same active competition, so competition_id scoping is handled at query time.
    members_resp = (
        supabase.table("league_members")
        .select("id, league_id")
        .execute()
    )

    STARTER_SLOTS = ["starter_1", "starter_2", "starter_3", "starter_4", "starter_5"]
    rows = []

    for member in (members_resp.data or []):
        member_id = member["id"]
        league_id = member["league_id"]

        # Get roster_id
        roster_resp = (
            supabase.table("rosters")
            .select("id")
            .eq("member_id", member_id)
            .single()
            .execute()
        )
        if not roster_resp.data:
            continue
        roster_id = roster_resp.data["id"]

        # Get current starter slots
        rp_resp = (
            supabase.table("roster_players")
            .select("slot, player_id")
            .eq("roster_id", roster_id)
            .in_("slot", STARTER_SLOTS)
            .execute()
        )
        filled = {row["slot"]: row["player_id"] for row in (rp_resp.data or [])}

        # Create one row per slot (NULL for empty)
        for slot in STARTER_SLOTS:
            rows.append({
                "league_id": league_id,
                "member_id": member_id,
                "competition_id": competition_id,
                "week": week,
                "slot": slot,
                "player_id": filled.get(slot),
            })

    if rows:
        supabase.table("lineup_snapshots").upsert(
            rows, on_conflict="league_id,member_id,week,slot"
        ).execute()
        logger.info("Lineup snapshot taken: week=%d, %d rows written", week, len(rows))


# ---------------------------------------------------------------------------
# Scoring de managers post-serie
# ---------------------------------------------------------------------------


def _update_manager_total_points(
    supabase: Client,
    series_ids: list[str],
    week: int | None = None,
    competition_id: str | None = None,
) -> None:
    """
    Actualiza total_points en league_members sumando los series_points de sus
    jugadores titulares para las series recién procesadas.

    Regla: si el manager tiene menos de 5 titulares (starter_1..starter_5)
    en su roster (o en el snapshot), NO se suman puntos esa jornada.
    Los player_series_stats se guardan igual — solo se omite la acumulación.

    Si week y competition_id están presentes, lee los titulares desde
    lineup_snapshots en lugar de roster_players (scoring histórico correcto).
    Si no hay snapshot para esa semana, cae al roster actual con WARNING.
    """
    if not series_ids:
        return

    starter_slots = {"starter_1", "starter_2", "starter_3", "starter_4", "starter_5"}

    # 1. Fetch todos los league_members con sus rosters
    try:
        members_resp = (
            supabase.table("league_members")
            .select("id, total_points")
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to fetch league_members for scoring: %s", exc)
        return

    # 2. Pre-fetch snapshot rows for this week if available (bulk, avoid N+1)
    snapshot_by_member: dict[str, dict[str, str | None]] = {}
    if week is not None and competition_id is not None:
        try:
            snap_resp = (
                supabase.table("lineup_snapshots")
                .select("member_id, slot, player_id")
                .eq("competition_id", competition_id)
                .eq("week", week)
                .execute()
            )
            for row in (snap_resp.data or []):
                mid = row["member_id"]
                if mid not in snapshot_by_member:
                    snapshot_by_member[mid] = {}
                snapshot_by_member[mid][row["slot"]] = row["player_id"]
        except Exception as exc:
            logger.warning(
                "Failed to fetch lineup_snapshots for week=%s — will fall back to current roster: %s",
                week, exc,
            )

    for member in (members_resp.data or []):
        member_id: str = member["id"]
        current_total: float = float(member.get("total_points") or 0)

        try:
            # Determine starter player_ids: prefer snapshot, fall back to current roster
            snap_slots = snapshot_by_member.get(member_id)

            if snap_slots is not None:
                # Use snapshot
                filled_starters = {slot for slot in snap_slots if slot in starter_slots}
                if len(filled_starters) < 5:
                    logger.info(
                        "[SCORING SKIP] member %s snapshot has %d/5 starters — no points added for week=%s",
                        member_id,
                        len(filled_starters),
                        week,
                    )
                    continue
                starter_player_ids = [
                    snap_slots[slot]
                    for slot in starter_slots
                    if snap_slots.get(slot)
                ]
            else:
                # No snapshot for this week: manager had no starters → 0 points
                if week is not None:
                    logger.info(
                        "[SCORING] No snapshot for member %s week=%s — 0 points (no starters that week)",
                        member_id,
                        week,
                    )
                continue

            if not starter_player_ids:
                continue

            # 5. Sumar series_points de los titulares en las series procesadas
            pss_resp = (
                supabase.table("player_series_stats")
                .select("series_points")
                .in_("player_id", starter_player_ids)
                .in_("series_id", series_ids)
                .execute()
            )
            earned = sum(
                float(r.get("series_points") or 0)
                for r in (pss_resp.data or [])
            )
            if earned == 0:
                continue

            # 6. Actualizar total_points
            supabase.table("league_members").update(
                {"total_points": round(current_total + earned, 2)}
            ).eq("id", member_id).execute()

            logger.info(
                "[SCORING] member %s: +%.2f pts (total: %.2f)",
                member_id,
                earned,
                current_total + earned,
            )

        except Exception as exc:
            logger.error(
                "Failed to update total_points for member %s: %s",
                member_id,
                exc,
            )


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------


async def run_series_ingest(supabase: Client) -> None:
    """
    Pipeline completo de ingestión de series desde gol.gg.

    Obtiene el slug de la competition activa (is_active=True) desde la DB,
    fetch la matchlist, agrupa los games por (home, away, date) formando
    series, y procesa cada serie en orden.
    """
    logger.info("Starting series ingest pipeline")

    # 1. Obtener gol_gg_slug de la competition activa (sin filtrar por nombre)
    try:
        comp_resp = (
            supabase.table("competitions")
            .select("id, name, gol_gg_slug")
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to query competitions: %s", exc)
        return

    if not comp_resp.data:
        logger.error("No active competition found in DB (is_active=True)")
        return

    competition = comp_resp.data[0]
    competition_id: str = str(competition["id"])
    competition_name: str = competition.get("name", "<unnamed>")
    gol_gg_slug: str | None = competition.get("gol_gg_slug")

    if not gol_gg_slug:
        logger.error(
            "Active competition '%s' (id=%s) has no gol_gg_slug configured",
            competition_name,
            competition_id,
        )
        return

    logger.info(
        "Using competition '%s' (id=%s, slug=%s)",
        competition_name,
        competition_id,
        gol_gg_slug,
    )

    # 2. Fetch matchlist
    try:
        all_entries = await fetch_matchlist(gol_gg_slug)
    except Exception as exc:
        logger.error("Failed to fetch matchlist for slug '%s': %s", gol_gg_slug, exc)
        return

    if not all_entries:
        logger.warning("Matchlist is empty for slug '%s'", gol_gg_slug)
        return

    logger.info("Fetched %d game entries from matchlist", len(all_entries))

    # 3. Agrupar games en series: key = (team_home, team_away, date)
    series_map: dict[tuple[str, str, date], list[GameEntry]] = defaultdict(list)
    for entry in all_entries:
        key = (entry.team_home, entry.team_away, entry.date)
        series_map[key].append(entry)

    # Ordenar games dentro de cada serie por game_id (numérico)
    for entries in series_map.values():
        entries.sort(key=lambda e: int(e.game_id))

    logger.info("Grouped into %d series", len(series_map))

    # 4a. Snapshot de game_ids que ya tienen stats en la DB antes de este run.
    #     Sólo los players con stats de games NUEVOS recibirán price update.
    #     Esto evita que re-runs acumulen el price update múltiples veces.
    existing_game_ids: set[str] = set()
    try:
        existing_resp = (
            supabase.table("player_game_stats")
            .select("game_id")
            .execute()
        )
        existing_game_ids = {str(row["game_id"]) for row in (existing_resp.data or [])}
        logger.info(
            "Pre-run snapshot: %d game_ids already have player_game_stats",
            len(existing_game_ids),
        )
    except Exception as exc:
        logger.warning(
            "Could not snapshot existing game_ids — price update will be skipped this run "
            "to avoid compounding prices: %s",
            exc,
        )
        # Ante la duda, marcar todos los IDs como existentes para no actualizar precios
        existing_game_ids = None  # type: ignore[assignment]

    # 4b. Procesar cada serie
    processed_player_ids: set[str] = set()
    new_price_player_ids: set[str] = set()
    processed_series_ids: list[str] = []
    processed_weeks: list[int] = []
    for (team_home_name, team_away_name, game_date), entries in series_map.items():
        # Resolver IDs de equipos
        team_home_id = _resolve_team_by_alias(supabase, team_home_name)
        team_away_id = _resolve_team_by_alias(supabase, team_away_name)

        if not team_home_id:
            logger.warning(
                "Skipping series: team_home '%s' not found", team_home_name
            )
            continue
        if not team_away_id:
            logger.warning(
                "Skipping series: team_away '%s' not found", team_away_name
            )
            continue

        try:
            series_player_ids, series_id = await _process_series(
                supabase,
                competition_id=competition_id,
                series_entries=entries,
                team_home_id=team_home_id,
                team_away_id=team_away_id,
                existing_game_ids=existing_game_ids if existing_game_ids is not None else set(),
                new_price_player_ids=new_price_player_ids,
            )
            processed_player_ids.update(series_player_ids)
            if series_id:
                processed_series_ids.append(series_id)
            if entries:
                processed_weeks.append(entries[0].week)
            await asyncio.sleep(1)
        except Exception as exc:
            logger.error(
                "Unexpected error processing series %s vs %s (%s): %s",
                team_home_name,
                team_away_name,
                game_date,
                exc,
                exc_info=True,
            )
            # Continuamos con la siguiente serie en lugar de abortar todo

    # 5. Actualizar precios post-serie SOLO para jugadores con stats de games NUEVOS.
    #    Si existing_game_ids es None (falló el snapshot), se omite para no componer.
    if existing_game_ids is None:
        logger.warning(
            "Price update skipped — could not snapshot pre-run game_ids safely"
        )
    elif new_price_player_ids:
        logger.info(
            "Price update will run for %d player(s) with new game stats",
            len(new_price_player_ids),
        )
        # Determine the most common week among newly processed series
        processed_week: int | None = None
        if processed_weeks:
            processed_week = max(set(processed_weeks), key=processed_weeks.count)
            logger.info("Passing week=%d to price update", processed_week)
        try:
            from market.price_updater import update_player_prices_post_series
            update_player_prices_post_series(supabase, list(new_price_player_ids), week=processed_week)
        except Exception as exc:
            logger.error(
                "Price update failed after series ingest (non-blocking): %s",
                exc,
                exc_info=True,
            )
    else:
        logger.info("No new game stats inserted — price update skipped")

    # 6a. Snapshot de alineaciones para esta semana (idempotente, corre una vez por semana)
    snap_week: int | None = None
    if processed_series_ids and processed_weeks:
        snap_week = max(set(processed_weeks), key=processed_weeks.count)
        try:
            _take_lineup_snapshot_if_needed(supabase, snap_week, competition_id)
        except Exception as exc:
            logger.error(
                "Lineup snapshot failed (non-blocking): %s", exc, exc_info=True
            )
            snap_week = None

    # 6b. Actualizar total_points de managers para las series procesadas
    if processed_series_ids:
        try:
            _update_manager_total_points(
                supabase,
                processed_series_ids,
                week=snap_week,
                competition_id=competition_id,
            )
        except Exception as exc:
            logger.error(
                "Manager scoring failed after series ingest (non-blocking): %s",
                exc,
                exc_info=True,
            )

    logger.info("Series ingest pipeline complete")
