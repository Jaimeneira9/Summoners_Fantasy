"""
gol.gg scraper via Cloudflare Browser Rendering API (/markdown endpoint).

Funciones públicas:
  fetch_matchlist(gol_gg_slug)    → list[GameEntry]
  fetch_game_fullstats(game_id)   → list[PlayerRawStats]
  fetch_game_meta(game_id)        → GameMeta
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import date
from typing import Optional

import httpx
from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cloudflare Browser Rendering config
# ---------------------------------------------------------------------------

# Las credenciales se resuelven en tiempo de ejecución (no al importar)
# para evitar que el módulo explote en entornos sin .env (ej. tests).
_CF_BASE_URL_TEMPLATE = (
    "https://api.cloudflare.com/client/v4/accounts/{account_id}/browser-rendering"
)

MAX_RETRIES = 3

# ---------------------------------------------------------------------------
# Role normalization
# ---------------------------------------------------------------------------

_ROLE_MAP: dict[str, str] = {
    "top": "top",
    "jungle": "jungle",
    "jgl": "jungle",
    "mid": "mid",
    "bot": "adc",
    "adc": "adc",
    "support": "support",
    "sup": "support",
}


def _normalize_role(raw: str) -> str:
    return _ROLE_MAP.get(raw.strip().lower(), raw.strip().lower())


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class GameEntry(BaseModel):
    """Una entrada de la matchlist de gol.gg — representa un game individual."""

    game_id: str
    team_home: str
    team_away: str
    winner: str
    week: int
    date: date


class PlayerRawStats(BaseModel):
    """Stats crudos de un jugador extraídos de /page-fullstats/."""

    player_name: str
    role: str  # normalizado: top/jungle/mid/adc/support
    kills: int
    deaths: int
    assists: int
    cs_per_min: float
    gold_diff_15: Optional[int] = None
    vision_score: int
    damage_share: float  # decimal: 27.3% → 0.273
    dpm: int
    wards_placed: int
    wards_destroyed: int
    solo_kills: int
    double_kill: bool
    triple_kill: bool
    quadra_kill: bool
    penta_kill: bool
    xp_diff_15: Optional[int] = None
    objective_steals: int
    turret_damage: int
    result: Optional[int] = None  # 1=win, 0=loss, None=desconocido

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, v: str) -> str:
        return _normalize_role(v)


class GameMeta(BaseModel):
    """Metadatos de un game: duración, equipo ganador y perdedor."""

    duration_min: float
    winner_team: str
    loser_team: str = ""  # vacío si no se pudo extraer del HTML


# ---------------------------------------------------------------------------
# HTTP helper con retry
# ---------------------------------------------------------------------------


async def _fetch_markdown(url: str) -> str:
    """
    POST /markdown para obtener el contenido renderizado como markdown.
    Retry automático con backoff exponencial. Maneja 429 con Retry-After.

    Las credenciales de Cloudflare se leen en tiempo de ejecución (lazy)
    para no explotar al importar el módulo sin variables de entorno cargadas.
    """
    cf_account_id = os.environ.get("CF_ACCOUNT_ID")
    cf_api_token = os.environ.get("CF_API_TOKEN")

    if not cf_account_id or not cf_api_token:
        raise RuntimeError(
            "CF_ACCOUNT_ID y CF_API_TOKEN deben estar configurados en el entorno. "
            "Verificá que el archivo .env esté cargado antes de llamar al scraper."
        )

    base_url = _CF_BASE_URL_TEMPLATE.format(account_id=cf_account_id)
    headers = {
        "Authorization": f"Bearer {cf_api_token}",
        "Content-Type": "application/json",
    }
    payload = {"url": url}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    f"{base_url}/markdown",
                    headers=headers,
                    json=payload,
                )
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", "10"))
                    logger.warning(
                        "Rate limited (429) on attempt %d/%d for %s. "
                        "Waiting %ds.",
                        attempt,
                        MAX_RETRIES,
                        url,
                        retry_after,
                    )
                    await asyncio.sleep(retry_after)
                    continue

                resp.raise_for_status()
                data = resp.json()

                if not data.get("success"):
                    raise RuntimeError(
                        f"CF markdown API returned success=false for {url}: {data}"
                    )

                # La API devuelve {"success": true, "result": "...markdown..."}
                result = data.get("result", "")
                # result puede ser string directamente o dict con "markdown" key
                if isinstance(result, dict):
                    return result.get("markdown", "") or result.get("content", "")
                return str(result)

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (401, 403):
                logger.error(
                    "Auth error — verificá CF_API_TOKEN y CF_ACCOUNT_ID: %s", exc
                )
                raise
            logger.warning(
                "HTTP error on attempt %d/%d for %s: %s",
                attempt,
                MAX_RETRIES,
                url,
                exc,
            )
            if attempt < MAX_RETRIES:
                await asyncio.sleep(2**attempt)
        except Exception as exc:
            logger.warning(
                "Error on attempt %d/%d for %s: %s",
                attempt,
                MAX_RETRIES,
                url,
                exc,
            )
            if attempt < MAX_RETRIES:
                await asyncio.sleep(2**attempt)
            else:
                raise

    raise RuntimeError(f"Failed to fetch markdown for {url} after {MAX_RETRIES} retries")


# ---------------------------------------------------------------------------
# Parsers internos
# ---------------------------------------------------------------------------


def _parse_optional_int(value: str | None) -> int | None:
    """Parsea un int que puede venir como '\\-1234' o vacío."""
    if not value:
        return None
    cleaned = value.strip().replace("\\-", "-").replace(",", "")
    if cleaned in ("", "-", "N/A", "—", "n/a"):
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def _parse_int(value: str | None, default: int = 0) -> int:
    result = _parse_optional_int(value)
    return result if result is not None else default


def _parse_float(value: str | None, default: float = 0.0) -> float:
    if not value:
        return default
    cleaned = value.strip().replace("\\-", "-").replace(",", "")
    if cleaned in ("", "-", "N/A", "—"):
        return default
    try:
        return float(cleaned)
    except ValueError:
        return default


def _parse_damage_share(value: str | None) -> float:
    """Convierte '27.3%' → 0.273."""
    if not value:
        return 0.0
    cleaned = value.strip().replace("%", "")
    try:
        return round(float(cleaned) / 100.0, 6)
    except ValueError:
        return 0.0


def _parse_bool_int(value: str | None) -> bool:
    """Convierte 0/1/vacío → bool."""
    if not value:
        return False
    stripped = value.strip()
    if stripped in ("", "0", "-"):
        return False
    try:
        return int(stripped) > 0
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Matchlist parser
# ---------------------------------------------------------------------------

# Patrón para extraer game_id del link markdown.
# El formato real incluye un title attribute opcional:
#   [Team A vs Team B](../game/stats/12345/page-game/ "Team A vs Team B stats")
# Por eso usamos [^)]* para consumir todo hasta el cierre del paréntesis.
_MATCHLIST_LINK_RE = re.compile(
    r"\[(.+?)\]\(\.\./game/stats/(\d+)/page-game/[^)]*\)"
)

# Patrón para extraer la semana: WEEK4 → 4
_WEEK_RE = re.compile(r"WEEK(\d+)", re.IGNORECASE)

# Patrón para la fecha: dd/mm/yyyy o yyyy-mm-dd
_DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})|(\d{4})-(\d{2})-(\d{2})")

# Score como "(2-1)" para detectar series
_SCORE_RE = re.compile(r"\((\d+)-(\d+)\)")


def _parse_matchlist(markdown: str) -> list[GameEntry]:
    """
    Parsea el markdown de la matchlist de gol.gg.

    Cada fila de la tabla tiene la forma:
      | [Team A vs Team B](../game/stats/{game_id}/page-game/) | Winner | Score (1-0) | Loser | WEEK{n} | patch | date |

    Nota: La matchlist lista SERIES, cada serie con un link que apunta al
    primer game. Para obtener todos los games de la serie necesitamos
    detectar el score y construir los game_ids subsiguientes.

    ADVERTENCIA: gol.gg NO garantiza IDs consecutivos entre games de una misma
    serie. El ID del link apunta al primer game; los games 2, 3, etc. se asumen
    consecutivos (base_id+1, base_id+2). Esta asunción se valida en
    series_ingest._process_game() comparando los equipos del game fetcheado
    contra los equipos de la serie — si no coinciden se loggea [INVALID GAME ID]
    y ese game se descarta.
    """
    entries: list[GameEntry] = []

    for line in markdown.splitlines():
        # Buscar líneas de tabla que tengan el link al game
        link_match = _MATCHLIST_LINK_RE.search(line)
        if not link_match:
            continue

        title = link_match.group(1)  # "Team A vs Team B"
        game_id = link_match.group(2)

        # Extraer equipos del title
        if " vs " not in title:
            continue
        parts = title.split(" vs ", 1)
        team_home = parts[0].strip()
        team_away = parts[1].strip()

        # Extraer semana
        week_match = _WEEK_RE.search(line)
        week = int(week_match.group(1)) if week_match else 0

        # Extraer fecha
        date_match = _DATE_RE.search(line)
        if date_match:
            if date_match.group(1):  # dd/mm/yyyy
                day = int(date_match.group(1))
                month = int(date_match.group(2))
                year = int(date_match.group(3))
            else:  # yyyy-mm-dd
                year = int(date_match.group(4))
                month = int(date_match.group(5))
                day = int(date_match.group(6))
            game_date = date(year, month, day)
        else:
            logger.warning("No date found in matchlist row for game %s", game_id)
            continue

        # Extraer winner — es la celda después del link
        # Formato: | [link] | Winner | Score | Loser | WEEK | patch | date |
        cells = [c.strip() for c in line.split("|") if c.strip()]
        winner = ""

        # La primera celda es el link, la segunda debería ser el winner
        if len(cells) >= 2:
            # cells[0] contiene el link completo, cells[1] es el winner
            winner = cells[1].strip()

        # Extraer score para detectar cuántos games tiene la serie
        score_match = _SCORE_RE.search(line)
        if score_match:
            score_a = int(score_match.group(1))
            score_b = int(score_match.group(2))
            total_games = score_a + score_b
        else:
            total_games = 1

        # Generar un GameEntry por cada game de la serie.
        # ASUNCIÓN (no garantizada): gol.gg asigna IDs consecutivos.
        # La validación real ocurre en series_ingest._process_game().
        base_id = int(game_id)
        for i in range(total_games):
            current_game_id = str(base_id + i)
            # El winner de game individual lo determinamos con fetch_game_meta
            # Acá ponemos el winner de la serie como placeholder
            entries.append(
                GameEntry(
                    game_id=current_game_id,
                    team_home=team_home,
                    team_away=team_away,
                    winner=winner,  # winner de serie; se sobreescribe con game_meta
                    week=week,
                    date=game_date,
                )
            )

    logger.info("Parsed %d game entries from matchlist", len(entries))
    return entries


# ---------------------------------------------------------------------------
# Fullstats parser
# ---------------------------------------------------------------------------

# Mapa de headers de gol.gg → campo del modelo
# Las columnas en page-fullstats son filas (stat) × columnas (jugadores)
_STAT_ROW_HEADERS = {
    "player": "player_name",
    "role": "role",
    "kills": "kills",
    "deaths": "deaths",
    "assists": "assists",
    "csm": "cs_per_min",
    "cs/m": "cs_per_min",
    "gd@15": "gold_diff_15",
    "gold diff@15": "gold_diff_15",
    "vision score": "vision_score",
    "dmg%": "damage_share",
    "damage%": "damage_share",
    "dpm": "dpm",
    "wards placed": "wards_placed",
    "wards destroyed": "wards_destroyed",
    "solo kills": "solo_kills",
    "double kills": "double_kill",
    "triple kills": "triple_kill",
    "quadra kills": "quadra_kill",
    "penta kills": "penta_kill",
    "xpd@15": "xp_diff_15",
    "xp diff@15": "xp_diff_15",
    "objectives stolen": "objective_steals",
    "objective steals": "objective_steals",
    "objectives steals": "objective_steals",
    "damage dealt to turrets": "turret_damage",
    "turret damage": "turret_damage",
}


def _parse_fullstats_table(markdown: str) -> list[dict]:
    """
    Parsea la tabla de fullstats de gol.gg.

    La tabla tiene filas = stats, columnas = jugadores (10 columnas).
    Devuelve lista de dicts con keys = campo del modelo.
    """
    lines = [l for l in markdown.splitlines() if "|" in l]
    if not lines:
        return []

    # Buscar la tabla principal — la que tiene "Player" o "Role" como primera fila
    table_lines: list[str] = []
    in_table = False
    for line in lines:
        cells = [c.strip() for c in line.split("|")]
        cells = [c for c in cells if c != ""]  # quitar vacíos de extremos

        if not cells:
            if in_table and table_lines:
                break
            continue

        # Detectar inicio de tabla: primera celda es "Player" o stat header conocido
        first_cell_lower = cells[0].lower()
        if first_cell_lower in _STAT_ROW_HEADERS or first_cell_lower == "player":
            in_table = True

        if in_table:
            # Ignorar líneas separadoras (contienen solo guiones)
            if all(set(c.replace("-", "").replace(":", "")) <= set(" ") for c in cells):
                continue
            table_lines.append(line)

    if not table_lines:
        logger.warning("No stats table found in fullstats markdown")
        return []

    # Procesar filas: cada fila es un stat, las columnas son los jugadores
    # Estructura: | StatName | P1 | P2 | P3 | P4 | P5 | P6 | P7 | P8 | P9 | P10 |
    # donde P1-P5 son equipo home, P6-P10 son equipo away

    # Primero identificar cuántos jugadores hay (debería ser 10)
    num_players = 0
    player_row: list[str] = []
    for line in table_lines:
        cells = [c.strip() for c in line.split("|")]
        cells = [c for c in cells if c != ""]
        if cells and cells[0].lower() == "player":
            player_row = cells[1:]  # quitar la primera celda (header de la columna)
            num_players = len(player_row)
            break

    if num_players == 0:
        # Intentar inferir de la primera fila
        first_cells = [c.strip() for c in table_lines[0].split("|")]
        first_cells = [c for c in first_cells if c != ""]
        num_players = len(first_cells) - 1  # -1 por la columna de stat name
        player_row = [""] * num_players

    # Inicializar dicts para cada jugador
    players_data: list[dict] = [{} for _ in range(num_players)]

    for line in table_lines:
        cells = [c.strip() for c in line.split("|")]
        cells = [c for c in cells if c != ""]
        if not cells:
            continue

        stat_name = cells[0].lower().strip()
        values = cells[1:]

        field = _STAT_ROW_HEADERS.get(stat_name)
        if not field:
            continue

        for i, val in enumerate(values[:num_players]):
            if i < len(players_data):
                players_data[i][field] = val

    # Rellenar player_name si vino de la fila "Player"
    if player_row:
        for i, name in enumerate(player_row[:num_players]):
            if i < len(players_data) and "player_name" not in players_data[i]:
                players_data[i]["player_name"] = name

    return players_data


def _build_player_stats(
    raw: dict, team_side: str, winner_team: str
) -> PlayerRawStats | None:
    """Construye un PlayerRawStats desde un dict crudo de la tabla."""
    player_name = raw.get("player_name", "").strip()
    role = raw.get("role", "").strip()

    if not player_name or not role:
        return None

    # Determinar result: necesitamos saber qué equipo ganó
    # team_side es "home" o "away", winner_team también
    # Esta lógica se resuelve después en el orquestador con GameMeta
    result = 0  # placeholder; se setea en series_ingest

    return PlayerRawStats(
        player_name=player_name,
        role=role,
        kills=_parse_int(raw.get("kills")),
        deaths=_parse_int(raw.get("deaths")),
        assists=_parse_int(raw.get("assists")),
        cs_per_min=_parse_float(raw.get("cs_per_min")),
        gold_diff_15=_parse_optional_int(raw.get("gold_diff_15")),
        vision_score=_parse_int(raw.get("vision_score")),
        damage_share=_parse_damage_share(raw.get("damage_share")),
        dpm=_parse_int(raw.get("dpm")),
        wards_placed=_parse_int(raw.get("wards_placed")),
        wards_destroyed=_parse_int(raw.get("wards_destroyed")),
        solo_kills=_parse_int(raw.get("solo_kills")),
        double_kill=_parse_bool_int(raw.get("double_kill")),
        triple_kill=_parse_bool_int(raw.get("triple_kill")),
        quadra_kill=_parse_bool_int(raw.get("quadra_kill")),
        penta_kill=_parse_bool_int(raw.get("penta_kill")),
        xp_diff_15=_parse_optional_int(raw.get("xp_diff_15")),
        objective_steals=_parse_int(raw.get("objective_steals")),
        turret_damage=_parse_int(raw.get("turret_damage")),
        result=result,
    )


# ---------------------------------------------------------------------------
# page-game parser (duration + winner)
# ---------------------------------------------------------------------------

# Duración: aparece como heading H1 "# MM:SS" (ej. "# 29:03")
_DURATION_HEADING_RE = re.compile(r"^#\s+(\d+):(\d+)\s*$")

# Winner/Loser: línea con patrón [TeamName](url) \- WIN o \- LOSS
# El markdown de gol.gg usa \- como escaped dash, pero puede venir como - también
_WINNER_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)\s*\\?-\s*WIN", re.IGNORECASE)
_LOSER_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)\s*\\?-\s*LOSS", re.IGNORECASE)


def _parse_game_meta(markdown: str) -> GameMeta:
    """
    Extrae duration_min, winner_team y loser_team del markdown de page-game de gol.gg.

    Estructura real del markdown:
      Game Time
      # 29:03                          ← duración como H1 con formato MM:SS
      ...
      [UCAM Esports](...) \\- LOSS     ← equipo perdedor
      ...
      [Galions](...) \\- WIN            ← equipo ganador

    Ambos equipos (winner_team + loser_team) se usan en series_ingest para
    validar que el game_id scrapeado corresponde a la serie esperada.
    """
    duration_min = 0.0
    winner_team = ""
    loser_team = ""

    for line in markdown.splitlines():
        line_stripped = line.strip()

        # Buscar duración: línea "# MM:SS"
        if duration_min == 0.0:
            dur_match = _DURATION_HEADING_RE.match(line_stripped)
            if dur_match:
                minutes = int(dur_match.group(1))
                seconds = int(dur_match.group(2))
                duration_min = round(minutes + seconds / 60.0, 4)

        # Buscar winner: [TeamName](...) \- WIN
        if not winner_team:
            win_match = _WINNER_RE.search(line_stripped)
            if win_match:
                winner_team = win_match.group(1).strip()

        # Buscar loser: [TeamName](...) \- LOSS
        if not loser_team:
            loss_match = _LOSER_RE.search(line_stripped)
            if loss_match:
                loser_team = loss_match.group(1).strip()

    return GameMeta(duration_min=duration_min, winner_team=winner_team, loser_team=loser_team)


# ---------------------------------------------------------------------------
# Funciones públicas
# ---------------------------------------------------------------------------


async def fetch_matchlist(gol_gg_slug: str) -> list[GameEntry]:
    """
    Obtiene y parsea la matchlist de un torneo de gol.gg.

    Args:
        gol_gg_slug: slug del torneo (ej. "LEC-2024-Winter-Split-1")

    Returns:
        Lista de GameEntry, uno por game individual (expandido de series).
    """
    url = f"https://gol.gg/tournament/tournament-matchlist/{gol_gg_slug}/"
    logger.info("Fetching matchlist for slug %s", gol_gg_slug)
    markdown = await _fetch_markdown(url)
    return _parse_matchlist(markdown)


async def fetch_game_fullstats(game_id: str) -> list[PlayerRawStats]:
    """
    Scrapea la página page-fullstats y devuelve stats de los 10 jugadores.

    Args:
        game_id: ID numérico del game en gol.gg

    Returns:
        Lista de PlayerRawStats (hasta 10, uno por jugador).
        El campo `result` viene en 0 — debe setearse en el orquestador
        una vez que se conoce el winner del game vía fetch_game_meta.
    """
    url = f"https://gol.gg/game/stats/{game_id}/page-fullstats/"
    logger.info("Fetching fullstats for game %s", game_id)
    markdown = await _fetch_markdown(url)

    raw_players = _parse_fullstats_table(markdown)
    if not raw_players:
        logger.warning("No player data parsed for game %s", game_id)
        return []

    stats: list[PlayerRawStats] = []
    for i, raw in enumerate(raw_players):
        # Los primeros 5 son home team, los últimos 5 son away team
        side = "home" if i < 5 else "away"
        player_stat = _build_player_stats(raw, side, winner_team="")
        if player_stat is not None:
            stats.append(player_stat)
        else:
            logger.warning(
                "Could not build PlayerRawStats for player index %d in game %s", i, game_id
            )

    logger.info("Parsed %d player stats for game %s", len(stats), game_id)
    return stats


async def fetch_game_meta(game_id: str) -> GameMeta:
    """
    Scrapea page-game para obtener duración y equipo ganador.

    Args:
        game_id: ID numérico del game en gol.gg

    Returns:
        GameMeta con duration_min y winner_team.
    """
    url = f"https://gol.gg/game/stats/{game_id}/page-game/"
    logger.info("Fetching game meta for game %s", game_id)
    markdown = await _fetch_markdown(url)
    return _parse_game_meta(markdown)
