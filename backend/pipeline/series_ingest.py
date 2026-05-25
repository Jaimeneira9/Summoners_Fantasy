"""
Orquestador de ingestión de series desde gol.gg — Summoner's Fantasy.

Este es el módulo central del pipeline activo. Coordina el flujo completo desde
la matchlist de gol.gg hasta los puntos de cada manager de fantasy.

Fuente de datos:
  gol.gg — scrapeado via Cloudflare Browser Rendering API (módulo gol_gg.py).
  gol.gg agrupa partidas en series (BO1, BO3, BO5) con scores explícitos.

Flujo completo (run_series_ingest):
  1.  Obtener competitions activas (is_active=True) desde la DB
  2.  Por cada competition: fetch matchlist de gol.gg via gol_gg_slug
  3.  Filtrar entries por current_week (procesar solo la jornada actual)
  4.  Agrupar games en series: clave (team_home, team_away, fecha)
  5.  Snapshot de game_ids ya existentes (para evitar price update duplicado)
  6.  Por cada serie:
        a. Resolver IDs de equipos via aliases
        b. Upsert de la serie en la tabla `series`
        c. Por cada game: fetch fullstats + meta, validar game_id, upsert games
        d. Calcular puntos por jugador y upsert player_game_stats
        e. Calcular promedios de serie y upsert player_series_stats
        f. Actualizar winner_id y game_count en la serie
  7.  Actualizar precios de jugadores con nuevas stats (solo games nuevos)
  8.  Auto-avanzar current_week si todas las series de la semana están finished
  9.  Snapshot de alineaciones de managers (idempotente, una vez por semana)
  10. Calcular total_points de managers usando los snapshots

Modelos de DB involucrados:
  competitions → series → games → player_game_stats
  players, teams (resolución por alias)
  player_series_stats (promedios agregados por serie)
  lineup_snapshots (alineaciones semanales de managers)
  league_members.total_points (puntuación acumulada del torneo)
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
from scoring.config_loader import get_multikill_bonuses, get_scoring_weights
from scoring.engine import calculate_match_points

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Team resolution
# ---------------------------------------------------------------------------


def _resolve_team_by_alias(supabase: Client, team_name: str) -> str | None:
    """
    Resuelve el UUID de un equipo buscando team_name en el array aliases.
    Returns UUID str o None si no se encuentra.

    gol.gg usa nombres de equipo que pueden diferir de los nombres canónicos en
    la DB (ej. "NAVI" vs "Natus Vincere", "G2" vs "G2 Esports"). Para manejar
    esto, la tabla teams tiene una columna `aliases` (array de strings) con los
    nombres alternativos de cada equipo.

    Estrategia de búsqueda (dos pasos):
      1. Búsqueda exacta: Supabase .contains() busca el nombre en el array.
      2. Fallback case-insensitive: trae todos los equipos (~20 para LEC) y
         compara manualmente. Es aceptable porque la tabla es pequeña.
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


def _resolve_player_id(
    supabase: Client, player_name: str, league: str = "LEC"
) -> str | None:
    """
    Resuelve el UUID del jugador por nombre y liga (case-insensitive).

    El parámetro `league` filtra por players.league para evitar colisiones
    entre jugadores de distintas ligas con el mismo nombre (ej. 'Scout' en LCK y LPL).
    Default 'LEC' para backward compatibility.

    Estrategia de búsqueda (dos pasos):
      1. Match exacto (eq) + filtro de liga — el más frecuente y rápido.
      2. Fallback ilike case-insensitive — para nombres con variaciones de casing
         entre gol.gg y lo registrado en la DB.

    Si el jugador no se encuentra, se loggea como [UNRESOLVED PLAYER] y sus
    stats se descartan para ese game (no se persisten en la DB).
    """
    try:
        # Intento exacto primero (nombre + liga)
        result = (
            supabase.table("players")
            .select("id")
            .eq("name", player_name)
            .eq("league", league)
            .limit(1)
            .execute()
        )
        if result.data:
            return str(result.data[0]["id"])

        # Fallback ilike para case-insensitive (mantiene filtro de liga)
        result = (
            supabase.table("players")
            .select("id")
            .ilike("name", player_name)
            .eq("league", league)
            .limit(1)
            .execute()
        )
        if result.data:
            return str(result.data[0]["id"])

    except Exception as exc:
        logger.error(
            "DB error resolving player '%s' (league=%s): %s",
            player_name, league, exc
        )

    logger.warning("Player not found in DB: '%s' (league=%s)", player_name, league)
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
    Upsert de la serie en la tabla `series`. Devuelve el UUID de la serie o None si falla.

    La UNIQUE constraint es (team_home_id, team_away_id, date): dos equipos solo
    pueden enfrentarse una vez por día en el mismo split, lo que identifica la serie.

    Si el upsert no devuelve datos (el conflicto fue ignorado), hace un SELECT
    para obtener el ID de la serie ya existente. Esto garantiza idempotencia:
    el pipeline puede correr múltiples veces sin crear series duplicadas.
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
    Upsert del game individual en la tabla `games`. Devuelve el UUID o None si falla.

    La UNIQUE constraint es (series_id, game_number): cada game dentro de una
    serie tiene número secuencial (1, 2, 3). Re-runs sobreescriben el registro
    existente (a diferencia de series, donde el upsert ignora el conflicto).

    winner_team_id puede ser None si no se pudo resolver el equipo ganador
    desde el meta de gol.gg (se persiste sin winner y se loggea el warning).
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
    """
    Upsert de los stats del jugador en un game individual en player_game_stats.

    Persiste tanto las stats crudas scrapeadas de gol.gg como los puntos de
    fantasy calculados por el scoring engine. La UNIQUE constraint es
    (player_id, game_id), lo que hace el upsert idempotente.

    game_points es el total de puntos de fantasy para este game específico,
    calculado en _process_game() antes de llamar a esta función.
    """
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
    Orden de prioridad: penta > quadra > triple > double > None.

    Un jugador puede hacer multikills en games distintos de la misma serie;
    este helper toma el máximo across todos los games jugados en esa serie.
    Se usa para poblar el campo best_multikill en player_series_stats, que
    alimenta el bonus de puntos de multikill en el scoring de fantasy.
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

    game_stats_list y game_points_list tienen el mismo orden y longitud (un elemento
    por game jugado en la serie). game_durations_list también es paralela.

    Los promedios calculados son:
      - avg_kills, avg_deaths, avg_assists, avg_cs_per_min: media simple entre games
      - avg_gold_diff_15: media de los games donde este dato existe (puede ser None
        si el game fue corto o gol.gg no reportó el dato)
      - avg_wards_per_min: (wards_placed + wards_destroyed) / duration_min por game,
        luego media. Requiere game_durations_list para normalizar por tiempo.
      - series_points: promedio de game_points — es el valor que usa el scoring
        de managers para calcular total_points semanales

    Kill participation (no calculado acá): depende de los kills totales del equipo,
    que no están disponibles en PlayerRawStats. Se calcula via SQL en el backfill.
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
    """
    Actualiza game_count y winner_id en la tabla `series` al finalizar el procesamiento.

    game_count: total de games jugados en la serie (1 para BO1, 2-3 para BO3, etc.)
    winner_id: UUID del equipo ganador de la serie (el que ganó más games).
               Puede ser None si hubo empate técnico o no se resolvieron los winners.

    Se llama al final de _process_series(), una vez procesados todos los games.
    """
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

    Problema que resuelve:
      gol.gg no garantiza que los game_ids de games 2 y 3 de una serie BO3
      sean consecutivos respecto al game 1. El pipeline construye los IDs como
      base_id+1, base_id+2, pero si hay gaps en la numeración interna de gol.gg,
      estaríamos scrapeando un game de otra serie completamente distinta.

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
    league_tag: str = "LEC",
    competition_id: str | None = None,
) -> tuple[str | None, str | None]:
    """
    Procesa un game individual: fetch stats + meta desde gol.gg, persiste en DB.

    Pasos internos:
      1. Fetch fullstats (10 jugadores) y meta (duración + winner) desde gol.gg
      2. Validar que el game_id corresponde a la serie (guard anti-ID-gap)
      3. Resolver equipo ganador a UUID de DB
      4. Upsert del game en la tabla `games`
      5. Asignar result (1=win, 0=loss) a cada PlayerRawStats según el winner
      6. Por cada jugador: resolver player_id, calcular puntos, upsert player_game_stats
      7. Acumular (stats, puntos, duración) para el cálculo de stats de serie posterior
      8. Registrar player_ids con stats nuevas para el price update post-serie

    Returns:
        (game_db_id, winner_team_id) — ambos pueden ser None si algo falla en el proceso.

    El acumulador series_player_stats se modifica in-place. Al final de todos los
    games de la serie, _process_series() usa ese acumulador para llamar a
    _upsert_player_series_stats().
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
        player_id = _resolve_player_id(supabase, stats.player_name, league=league_tag)
        if not player_id:
            logger.warning(
                "[UNRESOLVED PLAYER] '%s' not found in players table — stats discarded",
                stats.player_name,
            )
            unresolved_players.append(stats.player_name)
            continue

        scoring_weights = get_scoring_weights(supabase, competition_id, stats.role) if competition_id else None
        mk_bonuses = get_multikill_bonuses(supabase, competition_id) if competition_id else None

        game_points = calculate_match_points(
            stats=stats.model_dump(),
            role=stats.role,  # type: ignore[arg-type]
            game_duration_min=meta.duration_min,
            weights=scoring_weights,
            multikill_bonuses=mk_bonuses,
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
    league_tag: str = "LEC",
    scoring_competition_id: str | None = None,
) -> tuple[set[str], str | None]:
    """
    Procesa todos los games de una serie (BO1/BO3/BO5) end-to-end.

    Orquesta el flujo completo para una serie:
      1. Upsert de la serie en la tabla `series`
      2. Procesa cada game en orden numérico via _process_game()
      3. Contabiliza victorias por equipo para determinar winner de la serie
      4. Calcula y persiste player_series_stats (promedios across games)
      5. Actualiza series con game_count y winner_id definitivos
      6. Loggea resumen de jugadores no resueltos (si los hay)

    Returns:
        (set[player_ids procesados], series_id o None si el upsert de serie falló)

    El set de player_ids se usa en _ingest_single_competition() para saber
    qué jugadores tienen stats nuevas y requieren price update.
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
            league_tag=league_tag,  # NUEVO
            competition_id=scoring_competition_id,
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
    current_week: int | None = None,
) -> None:
    """
    Registra el snapshot de alineaciones de todos los managers para esta semana.

    El snapshot captura qué jugadores tiene cada manager como starters al momento
    de cerrar la jornada, junto con el capitán seleccionado. Estos datos son la
    "fotografía" de la alineación que se usa para calcular los puntos de la semana.

    Por qué es necesario:
      Los managers pueden cambiar su alineación durante la semana. El snapshot se
      toma una vez (al procesar las series de esa semana) y congela qué starters
      y capitán correspondían a esa jornada. Sin snapshot, no habría manera de
      saber qué jugadores puntearon para quién en semanas pasadas.

    Idempotente: si ya existe un snapshot para (competition_id, week), no hace nada.
    Guard de backfill: si week != current_week, lanza ValueError para evitar
      sobreescribir snapshots históricos con runs de backfill.

    Escribe en la tabla `lineup_snapshots`:
      una fila por (league_id, member_id, week, slot) — 5 filas por manager.
    """
    if current_week is not None and week != current_week:
        logger.warning(
            "Backfill bloqueado: intento de snapshot para week=%d pero current_week=%d",
            week,
            current_week,
        )
        raise ValueError(
            f"Backfill bloqueado: week={week} es pasado, current_week={current_week}"
        )

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

    # Bulk fetch captain_selections for this week (avoid N+1 per member)
    captain_by_member: dict[str, str | None] = {}
    try:
        cap_resp = (
            supabase.table("captain_selections")
            .select("member_id, captain_player_id")
            .eq("competition_id", competition_id)
            .eq("week", week)
            .execute()
        )
        for cap_row in (cap_resp.data or []):
            captain_by_member[cap_row["member_id"]] = cap_row["captain_player_id"]
    except Exception as exc:
        logger.warning("Failed to fetch captain_selections for snapshot week=%d: %s", week, exc)

    rows = []

    for member in (members_resp.data or []):
        member_id = member["id"]
        league_id = member["league_id"]

        # Get roster_id
        roster_resp = (
            supabase.table("rosters")
            .select("id")
            .eq("member_id", member_id)
            .limit(1)
            .execute()
        )
        if not roster_resp.data:
            continue
        roster_id = roster_resp.data[0]["id"]

        # Get current starter slots
        rp_resp = (
            supabase.table("roster_players")
            .select("slot, player_id")
            .eq("roster_id", roster_id)
            .in_("slot", STARTER_SLOTS)
            .execute()
        )
        filled = {row["slot"]: row["player_id"] for row in (rp_resp.data or [])}

        # Lookup captain for this member (may be None if not set)
        captain_player_id = captain_by_member.get(member_id)

        # Create one row per slot (NULL for empty)
        for slot in STARTER_SLOTS:
            rows.append({
                "league_id": league_id,
                "member_id": member_id,
                "competition_id": competition_id,
                "week": week,
                "slot": slot,
                "player_id": filled.get(slot),
                "captain_player_id": captain_player_id,
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
    competition_id: str,
    week: int | None = None,  # ignorado: la función itera todas las semanas con snapshot
) -> None:
    """
    Calcula y escribe total_points para cada manager de forma absoluta e idempotente.

    Algoritmo de scoring de managers:
      Por cada semana con snapshot en esta competition:
        1. Obtener los 5 starters del manager en esa semana (del snapshot)
        2. Si hay menos de 5 starters → 0 puntos para esa semana
        3. Obtener las series finalizadas de esa semana
        4. Buscar series_points de esos jugadores en esas series
        5. Si el jugador es capitán → sus puntos cuentan x2
        6. Sumar todos los puntos de la semana

      Acumular puntos de todas las semanas → total_points del manager

    Idempotente: el UPDATE es absoluto (sobreescribe el total cada vez).
    Esto permite recalcular correctamente aunque se corra múltiples veces.

    El parámetro `week` está presente por compatibilidad pero se ignora:
    la función siempre recalcula TODAS las semanas con snapshot para garantizar
    consistencia (una semana pasada pudo haber tenido correcciones de datos).

    Bulk queries:
      Para evitar N+1 queries, se hace un único fetch de todos los snapshots
      y un único fetch de series por semana, luego se trabaja en memoria.
    """
    starter_slots = ["starter_1", "starter_2", "starter_3", "starter_4", "starter_5"]

    # 1. Fetch todas las semanas con snapshots en esta competition
    try:
        snapped_weeks_resp = (
            supabase.table("lineup_snapshots")
            .select("week")
            .eq("competition_id", competition_id)
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to fetch snapped weeks for competition %s: %s", competition_id, exc)
        return

    snapped_weeks = sorted({row["week"] for row in (snapped_weeks_resp.data or [])})
    if not snapped_weeks:
        logger.info("[SCORING] No snapshots found for competition %s — nothing to score", competition_id)
        return

    # 2. Fetch todos los snapshots de la competition de una sola vez (bulk)
    try:
        all_snaps_resp = (
            supabase.table("lineup_snapshots")
            .select("week, member_id, slot, player_id, captain_player_id")
            .eq("competition_id", competition_id)
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to fetch all lineup_snapshots for competition %s: %s", competition_id, exc)
        return

    # Índice: snaps_by_week_member[week][member_id] = {slot: player_id}
    snaps_by_week_member: dict[int, dict[str, dict[str, str | None]]] = {}
    # Índice: captain_by_week_member[week][member_id] = captain_player_id | None
    captain_by_week_member: dict[int, dict[str, str | None]] = {}
    for row in (all_snaps_resp.data or []):
        w = row["week"]
        mid = row["member_id"]
        snaps_by_week_member.setdefault(w, {}).setdefault(mid, {})[row["slot"]] = row["player_id"]
        if row.get("captain_player_id") is not None:
            captain_by_week_member.setdefault(w, {}).setdefault(mid, row["captain_player_id"])

    # 3. Fetch series finalizadas por semana (una query por semana para aislar correctamente)
    series_ids_by_week: dict[int, list[str]] = {}
    for w in snapped_weeks:
        try:
            series_resp = (
                supabase.table("series")
                .select("id")
                .eq("competition_id", competition_id)
                .eq("status", "finished")
                .eq("week", w)
                .execute()
            )
            series_ids_by_week[w] = [str(r["id"]) for r in (series_resp.data or [])]
        except Exception as exc:
            logger.error("Failed to fetch finished series for competition %s week=%d: %s", competition_id, w, exc)
            series_ids_by_week[w] = []

    # 4. Acumular puntos por member across todas las semanas
    # total_by_member[member_id] = float acumulado
    total_by_member: dict[str, float] = {}
    # Registrar si algún member tuvo al menos una semana con snapshot (para saber quiénes actualizar)
    all_scored_members: set[str] = set()

    for w in snapped_weeks:
        week_snaps = snaps_by_week_member.get(w, {})
        week_series_ids = series_ids_by_week.get(w, [])
        week_captains = captain_by_week_member.get(w, {})

        for member_id, snap_slots in week_snaps.items():
            all_scored_members.add(member_id)

            starter_player_ids = [
                snap_slots[slot]
                for slot in starter_slots
                if snap_slots.get(slot) is not None
            ]

            if len(starter_player_ids) < 5:
                logger.info(
                    "[SCORING SKIP] member %s week=%d has %d/5 starters — 0 pts for this week",
                    member_id,
                    w,
                    len(starter_player_ids),
                )
                # Esta semana aporta 0; no sumamos nada (el acumulador empieza en 0)
                total_by_member.setdefault(member_id, 0.0)
                continue

            captain_player_id = week_captains.get(member_id)

            # Fallback: buscar captain en captain_selections si no está en snapshot
            if captain_player_id is None:
                try:
                    cap_resp = (
                        supabase.table("captain_selections")
                        .select("captain_player_id")
                        .eq("member_id", member_id)
                        .eq("competition_id", competition_id)
                        .eq("week", w)
                        .limit(1)
                        .execute()
                    )
                    if cap_resp.data:
                        captain_player_id = cap_resp.data[0].get("captain_player_id")
                except Exception as exc:
                    logger.warning(
                        "Failed to fetch captain_selections fallback for member %s week=%d: %s",
                        member_id,
                        w,
                        exc,
                    )

            if not week_series_ids:
                # No hay series finalizadas esta semana → 0 pts
                total_by_member.setdefault(member_id, 0.0)
                continue

            try:
                pss_resp = (
                    supabase.table("player_series_stats")
                    .select("player_id, series_points")
                    .in_("player_id", starter_player_ids)
                    .in_("series_id", week_series_ids)
                    .execute()
                )
            except Exception as exc:
                logger.error(
                    "Failed to fetch player_series_stats for member %s week=%d: %s",
                    member_id,
                    w,
                    exc,
                )
                total_by_member.setdefault(member_id, 0.0)
                continue

            week_pts = sum(
                float(r.get("series_points") or 0) * (
                    2 if captain_player_id is not None
                    and str(r.get("player_id")) == str(captain_player_id)
                    else 1
                )
                for r in (pss_resp.data or [])
            )

            total_by_member[member_id] = total_by_member.get(member_id, 0.0) + week_pts

            logger.debug(
                "[SCORING] member %s week=%d: +%.2f pts%s",
                member_id,
                w,
                week_pts,
                f" [captain x2: player_id={captain_player_id}]" if captain_player_id else "",
            )

    # 5. Escribir total_points absoluto e idempotente para cada member
    for member_id in all_scored_members:
        total = round(total_by_member.get(member_id, 0.0), 2)
        try:
            supabase.table("league_members").update(
                {"total_points": total}
            ).eq("id", member_id).execute()

            logger.info(
                "[SCORING] member %s: total_points=%.2f (across %d weeks)",
                member_id,
                total,
                len(snapped_weeks),
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


async def _ingest_single_competition(supabase: Client, competition: dict) -> None:
    """
    Ejecuta el pipeline completo de ingestión para UNA competition activa.

    Esta es la función de nivel medio: orquesta todo para una competition concreta.
    run_series_ingest() la llama en loop para cada competition activa, con manejo
    de excepciones independiente entre competitions.

    El flujo interno está detallado en el docstring del módulo. Los puntos más
    importantes desde el punto de vista de diseño:

    - Filtrado por current_week: solo se procesan las series de la semana actual.
      Evita re-procesar series pasadas en cada run del scheduler.

    - Snapshot de game_ids existentes: se hace ANTES de procesar cualquier serie.
      Permite detectar si un game ya tenía stats en la DB, para no duplicar el
      price update de ese jugador en re-runs.

    - Continuación ante errores de serie: si una serie falla (ej. gol.gg no
      responde para un game específico), el loop continúa con la siguiente serie
      en lugar de abortar toda la competition.

    - Auto-avance de semana: si después del procesamiento todas las series de
      current_week están "finished", se incrementa current_week automáticamente.

    Raises:
        Cualquier excepción no capturada propagada al caller (run_series_ingest),
        que loggea y continúa con la siguiente competition.
    """
    competition_id: str = str(competition["id"])
    competition_name: str = competition.get("name", "<unnamed>")
    gol_gg_slug: str | None = competition.get("gol_gg_slug")
    # Leer current_week de la DB para filtrar entries y snapshots
    current_week_db: int | None = competition.get("current_week")
    # Extraer league tag desde el nombre de la competition (ej. "LEC 2026 Spring" → "LEC")
    # Fallback a "LEC" si el nombre no empieza con letras o está vacío
    league_tag: str = competition_name.split()[0].upper() if competition_name and competition_name != "<unnamed>" else "LEC"

    # Guard: current_week NULL → WARNING + skip (no asumir semana 1 silenciosamente)
    if current_week_db is None:
        logger.warning(
            "Competition '%s' (id=%s) has current_week=NULL — skipping "
            "(configure current_week first)",
            competition_name,
            competition_id,
        )
        return

    if not gol_gg_slug:
        logger.error(
            "Competition '%s' (id=%s) has no gol_gg_slug configured — skipping",
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

    # TA-3: Filtrar entries por current_week_db para procesar solo la jornada actual
    all_entries = [e for e in all_entries if e.week == current_week_db]
    if not all_entries:
        logger.info(
            "No entries for current_week=%d in slug '%s' — nothing to process",
            current_week_db,
            gol_gg_slug,
        )
        return
    logger.info(
        "Filtered to %d game entries for week=%d", len(all_entries), current_week_db
    )

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
                league_tag=league_tag,
                scoring_competition_id=competition_id,
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

    # TA-4: Auto-avanzar current_week si todas las series de esta semana están finished
    try:
        all_series_resp = (
            supabase.table("series")
            .select("status")
            .eq("competition_id", competition_id)
            .eq("week", current_week_db)
            .execute()
        )
        all_series_statuses = [row["status"] for row in (all_series_resp.data or [])]
        if all_series_statuses and all(s == "finished" for s in all_series_statuses):
            next_week = current_week_db + 1
            supabase.table("competitions").update({"current_week": next_week}).eq("id", competition_id).execute()
            logger.info(
                "Avanzando competition %s a week=%d (todas las series de week=%d finished)",
                competition_id,
                next_week,
                current_week_db,
            )
    except Exception as exc:
        logger.warning("Auto-advance current_week failed (non-blocking): %s", exc)

    # 6a. Snapshot de alineaciones para esta semana (idempotente, corre una vez por semana)
    snap_week: int | None = None
    if processed_series_ids and processed_weeks:
        snap_week = max(set(processed_weeks), key=processed_weeks.count)
        try:
            # TA-5: Pasar current_week_db (no snap_week) para no neutralizar el guard de idempotencia
            _take_lineup_snapshot_if_needed(supabase, snap_week, competition_id, current_week=current_week_db)
        except Exception as exc:
            logger.error(
                "Lineup snapshot failed (non-blocking): %s", exc, exc_info=True
            )
            snap_week = None

    # 6b. Actualizar total_points de managers (absoluto, idempotente)
    if snap_week is not None:
        try:
            _update_manager_total_points(supabase, competition_id, snap_week)
        except Exception as exc:
            logger.error(
                "Manager scoring failed after series ingest (non-blocking): %s",
                exc,
                exc_info=True,
            )


async def run_series_ingest(supabase: Client) -> None:
    """
    Punto de entrada del pipeline de ingestión de series. Es la función pública
    de este módulo, llamada por el scheduler (main.py) cada hora.

    Consulta TODAS las competitions activas (is_active=True) y procesa cada una
    de forma independiente via _ingest_single_competition(). Si una competition
    falla con excepción no capturada, el loop continúa con la siguiente para
    no bloquear el procesamiento del resto.

    Para forzar manualmente: POST /debug/series-ingest (dev) o con X-Debug-Secret (prod).
    """
    logger.info("Starting series ingest pipeline")

    # 1. Obtener todas las competitions activas
    try:
        comp_resp = (
            supabase.table("competitions")
            .select("id, name, gol_gg_slug, current_week")
            .eq("is_active", True)
            .execute()
        )
    except Exception as exc:
        logger.error("Failed to query competitions: %s", exc)
        return

    competitions = comp_resp.data or []
    if not competitions:
        logger.error("No active competition found in DB (is_active=True)")
        return

    logger.info(
        "Processing %d active competition(s): %s",
        len(competitions),
        [c.get("name", "<unnamed>") for c in competitions],
    )

    for competition in competitions:
        competition_id = str(competition["id"])
        competition_name = competition.get("name", "<unnamed>")
        try:
            await _ingest_single_competition(supabase, competition)
        except Exception as exc:
            logger.error(
                "Competition '%s' (id=%s) failed with unhandled exception: %s",
                competition_name,
                competition_id,
                exc,
                exc_info=True,
            )

    logger.info("Series ingest pipeline complete")
