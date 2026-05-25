"""
Cliente Leaguepedia (MediaWiki Cargo API) — Summoner's Fantasy.

Responsabilidad única: detectar partidas LEC terminadas.
NO extrae stats de jugadores — eso es responsabilidad de Oracle's Elixir.

Fuente de datos:
  Leaguepedia es la wiki oficial de esports de League of Legends. Expone sus
  datos vía la Cargo API de MediaWiki, que permite hacer queries SQL-like sobre
  tablas como Tournaments, ScoreboardGames, etc.

Cómo se usa en el pipeline:
  1. LeaguepediaClient.get_active_tournament() detecta el torneo LEC en curso.
  2. LeaguepediaClient.get_recent_games() obtiene los GameSummary de ese torneo.
  3. pipeline.ingest.mark_pending_games() persiste esos games como pending_stats.
  4. El pipeline nocturno (Oracle's Elixir) procesa los pending_stats.

Nota sobre IDs:
  Cada game tiene dos IDs:
  - game_id: identificador interno de Leaguepedia (ej. "ESPORTSTMNT01_1234")
  - riot_platform_game_id: ID de Riot/región (ej. "EUW1_7123456"), usado para
    cruzar con Oracle's Elixir donde el CSV usa este segundo ID como "gameid".
"""
import logging
import time
from datetime import datetime

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

CARGO_API = "https://lol.fandom.com/api.php"
HEADERS = {"User-Agent": "SummonersFantasy/1.0 (fantasy league project)"}
REQUEST_DELAY_S = 1.5
MAX_RETRIES = 3


class GameSummary(BaseModel):
    """Resumen de un game individual extraído de Leaguepedia ScoreboardGames."""

    game_id: str                   # Leaguepedia GameId, ej: "ESPORTSTMNT01_1234"
    riot_platform_game_id: str     # Para cruzar con Oracle's Elixir, ej: "EUW1_7123456"
    team1: str
    team2: str
    winner: int                    # 1 o 2 (qué equipo ganó)
    duration_min: float            # Gamelength_Number (duración en minutos)
    scheduled_at: datetime         # DateTime_UTC del game
    team1_picks: list[str]
    team2_picks: list[str]
    team1_bans: list[str]
    team2_bans: list[str]


class LeaguepediaClient:
    """
    Cliente HTTP para la Cargo API de Leaguepedia.

    Uso recomendado como context manager para asegurar cierre del cliente HTTP:
        with LeaguepediaClient() as lp:
            games = lp.get_recent_games(...)
    """

    def __init__(self) -> None:
        self._client = httpx.Client(headers=HEADERS, timeout=30)

    def _cargo_query(
        self,
        tables: str,
        fields: str,
        where: str,
        order_by: str = "",
        limit: int = 50,
    ) -> list[dict]:
        """
        Ejecuta una consulta Cargo con paginación y retry automático.

        La Cargo API de MediaWiki devuelve resultados paginados (máx. 500 por request).
        Este método itera páginas hasta obtener todos los resultados.
        Si un request falla, reintenta hasta MAX_RETRIES veces con backoff lineal.
        """
        results: list[dict] = []
        offset = 0

        while True:
            params: dict = {
                "action": "cargoquery",
                "format": "json",
                "tables": tables,
                "fields": fields,
                "where": where,
                "limit": str(limit),
                "offset": str(offset),
            }
            if order_by:
                params["order_by"] = order_by

            for attempt in range(MAX_RETRIES):
                try:
                    resp = self._client.get(CARGO_API, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                    break
                except (httpx.HTTPError, Exception) as exc:
                    if attempt == MAX_RETRIES - 1:
                        logger.error("Cargo query failed after %d retries: %s", MAX_RETRIES, exc)
                        raise
                    logger.warning("Cargo query attempt %d failed: %s", attempt + 1, exc)
                    time.sleep(1.0 * (attempt + 1))

            page_results = [item["title"] for item in data.get("cargoquery", [])]
            results.extend(page_results)

            if len(page_results) < limit:
                break

            offset += limit
            time.sleep(REQUEST_DELAY_S)

        return results

    def get_active_tournament(self, league: str = "LEC") -> str:
        """
        Devuelve el OverviewPage del torneo LEC activo (season o playoffs).
        Fallback: torneo más reciente si estamos entre splits.

        El OverviewPage es el identificador de torneo en Leaguepedia, con la
        forma "LEC/2026 Season/Spring Split". Se usa luego en get_recent_games()
        para filtrar los games de ese torneo.

        Estrategia de búsqueda (dos pasos):
          1. Torneo en curso: DateStart <= hoy <= Date (fecha fin)
          2. Si no hay ninguno en curso (entre splits), devuelve el más reciente.

        Nota: el campo League no es filtrable directamente en Cargo (es un
        wikilink). Se filtra por OverviewPage LIKE "LEC/%" que identifica
        unívocamente los torneos de la LEC.
        """
        today = datetime.utcnow().strftime("%Y-%m-%d")
        league_filter = f'Tournaments.OverviewPage LIKE "%{league}/%"'

        # 1. Torneo en curso ahora mismo (DateStart <= hoy <= Date)
        result = self._cargo_query(
            tables="Tournaments",
            fields="OverviewPage,League,DateStart,Date",
            where=(
                f'{league_filter}'
                f' AND Tournaments.DateStart<="{today}"'
                f' AND Tournaments.Date>="{today}"'
            ),
            order_by="Tournaments.DateStart DESC",
            limit=1,
        )
        if result:
            logger.info("Active tournament: %s", result[0]["OverviewPage"])
            return result[0]["OverviewPage"]

        # 2. Fallback: torneo más reciente (entre splits)
        result = self._cargo_query(
            tables="Tournaments",
            fields="OverviewPage,League,DateStart,Date",
            where=(
                f'{league_filter}'
                f' AND Tournaments.DateStart<="{today}"'
            ),
            order_by="Tournaments.Date DESC",
            limit=1,
        )
        if result:
            logger.info("Most recent tournament: %s", result[0]["OverviewPage"])
            return result[0]["OverviewPage"]

        raise RuntimeError(f"No active or recent tournament found for league: {league}")

    def get_recent_games(
        self,
        overview_page: str,
        since: datetime | None = None,
    ) -> list[GameSummary]:
        """
        Devuelve las partidas terminadas en el torneo dado.
        Si `since` se proporciona, solo devuelve partidas posteriores a esa fecha.

        El parámetro `since` se usa para evitar re-procesar partidas ya conocidas:
        el scheduler pasa la fecha del último match en DB, de modo que solo
        se ingresan las partidas nuevas desde ese momento.

        Los games sin game_id se descartan silenciosamente (no sirven para
        cruzar con Oracle's Elixir ni para persistir en la tabla matches).
        """
        where = f'ScoreboardGames.OverviewPage="{overview_page}"'
        if since:
            since_str = since.strftime("%Y-%m-%d %H:%M:%S")
            where += f' AND ScoreboardGames.DateTime_UTC>"{since_str}"'

        rows = self._cargo_query(
            tables="ScoreboardGames",
            fields=(
                "ScoreboardGames.GameId=game_id,"
                "ScoreboardGames.RiotPlatformGameId=riot_platform_game_id,"
                "ScoreboardGames.Team1=team1,"
                "ScoreboardGames.Team2=team2,"
                "ScoreboardGames.Winner=winner,"
                "ScoreboardGames.Gamelength_Number=duration_min,"
                "ScoreboardGames.DateTime_UTC=scheduled_at,"
                "ScoreboardGames.Team1Picks=team1_picks,"
                "ScoreboardGames.Team2Picks=team2_picks,"
                "ScoreboardGames.Team1Bans=team1_bans,"
                "ScoreboardGames.Team2Bans=team2_bans"
            ),
            where=where,
            order_by="ScoreboardGames.DateTime_UTC DESC",
            limit=50,
        )

        games: list[GameSummary] = []
        for row in rows:
            try:
                game = GameSummary(
                    game_id=row.get("game_id") or "",
                    riot_platform_game_id=row.get("riot_platform_game_id") or "",
                    team1=row.get("team1") or "",
                    team2=row.get("team2") or "",
                    winner=int(row.get("winner") or 0),
                    duration_min=float(row.get("duration_min") or 0),
                    scheduled_at=datetime.fromisoformat(row["scheduled_at"].replace(" ", "T"))
                    if row.get("scheduled_at")
                    else datetime.utcnow(),
                    team1_picks=_parse_pipe_list(row.get("team1_picks")),
                    team2_picks=_parse_pipe_list(row.get("team2_picks")),
                    team1_bans=_parse_pipe_list(row.get("team1_bans")),
                    team2_bans=_parse_pipe_list(row.get("team2_bans")),
                )
                # Omitir partidas sin riot_platform_game_id (no se pueden cruzar con OE)
                if game.game_id:
                    games.append(game)
            except Exception as exc:
                logger.warning("Could not parse game row %s: %s", row, exc)

        logger.info("Found %d games for %s (since=%s)", len(games), overview_page, since)
        return games

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "LeaguepediaClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _parse_pipe_list(value: str | None) -> list[str]:
    """
    Convierte 'A,B,C' o 'A|B|C' en ['A', 'B', 'C'].

    Leaguepedia usa pipe como separador en campos multi-valor (picks, bans),
    pero algunos exports históricos usan coma. Se detecta el separador presente.
    """
    if not value:
        return []
    sep = "|" if "|" in value else ","
    return [v.strip() for v in value.split(sep) if v.strip()]
