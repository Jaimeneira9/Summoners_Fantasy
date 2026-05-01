#!/usr/bin/env python3
"""
Backfill de series, games y player stats para una competition histórica.

Reutiliza las funciones internas del pipeline (_process_series) para ingestar
datos de semanas pasadas sin afectar snapshots, scoring ni precios.

Qué hace este script:
  - Ingesta series, games, player_game_stats y player_series_stats
  - Soporta rango de semanas específico o todas las semanas disponibles
  - Modo --dry-run: lee gol.gg y DB pero NO escribe

Qué NO hace:
  - No crea lineup_snapshots
  - No actualiza league_members.total_points (scoring)
  - No avanza competitions.current_week
  - No actualiza precios de jugadores (player_prices)

Uso:
  python scripts/backfill_series.py --competition-slug "LES 2026 Kick-off Tournament" --weeks 1
  python scripts/backfill_series.py --competition-slug "LES 2026 Kick-off Tournament" --weeks 1-9
  python scripts/backfill_series.py --competition-slug "LES 2026 Kick-off Tournament" --all-weeks
  python scripts/backfill_series.py --competition-slug "LES 2026 Kick-off Tournament" --all-weeks --dry-run
"""
import argparse
import asyncio
import logging
import os
import sys
from collections import defaultdict

from dotenv import load_dotenv

# Cargar .env del backend y agregar el directorio al path
_backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
load_dotenv(os.path.join(_backend_dir, ".env"))
sys.path.insert(0, _backend_dir)

from supabase import create_client

from pipeline.gol_gg import fetch_matchlist
from pipeline.series_ingest import _process_series, _resolve_team_by_alias

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_competition_by_slug(supabase, slug: str) -> dict:
    """
    Busca una competition por gol_gg_slug.
    Sin filtro is_active: el backfill opera con competitions históricas.
    Sale con código 1 si no se encuentra.
    """
    result = (
        supabase.table("competitions")
        .select("id, name, gol_gg_slug, current_week")
        .eq("gol_gg_slug", slug)
        .limit(1)
        .execute()
    )
    if not result.data:
        print(f"[ERROR] Competition con slug '{slug}' no encontrada en DB")
        sys.exit(1)
    return result.data[0]


def parse_week_range(weeks_str: str) -> range:
    """
    Convierte un string 'N' o 'N-M' en un range(N, M+1).
    Sale con código 1 si el formato es inválido o start > end.
    """
    try:
        if "-" in weeks_str:
            parts = weeks_str.split("-", 1)
            start = int(parts[0])
            end = int(parts[1])
        else:
            start = int(weeks_str)
            end = int(weeks_str)
    except ValueError:
        print(f"[ERROR] Formato de semanas inválido: '{weeks_str}'. Use N o N-M (ej: 1, 1-9)")
        sys.exit(1)

    if start > end:
        print(f"[ERROR] Rango inválido: start ({start}) > end ({end})")
        sys.exit(1)

    return range(start, end + 1)


# ---------------------------------------------------------------------------
# Core backfill
# ---------------------------------------------------------------------------


async def run_backfill(
    supabase,
    competition: dict,
    week_filter: range | None,
    dry_run: bool,
) -> tuple[int, int, list[str], dict[int, str]]:
    """
    Ejecuta el backfill de series/games/player_stats para la competition dada.

    Returns:
        (total_series, total_games, unresolved_players, errors_by_week)
    """
    competition_id = str(competition["id"])
    competition_name = competition.get("name", "<unnamed>")
    gol_gg_slug = competition.get("gol_gg_slug")
    league_tag = competition_name.split()[0].upper() if competition_name and competition_name != "<unnamed>" else "LEC"

    if not gol_gg_slug:
        print(f"[ERROR] Competition '{competition_name}' no tiene gol_gg_slug configurado")
        sys.exit(1)

    if dry_run:
        print(f"[DRY RUN] Competition: {competition_name} (id={competition_id})")
    else:
        print(f"Competition: {competition_name} (id={competition_id})")

    # Fetch matchlist completo (siempre, incluso con --dry-run)
    print(f"Fetching matchlist para slug: {gol_gg_slug}")
    try:
        all_entries = await fetch_matchlist(gol_gg_slug)
    except Exception as exc:
        print(f"[ERROR] No se pudo obtener el matchlist: {exc}")
        sys.exit(1)

    if not all_entries:
        print(f"[WARN] Matchlist vacío para slug '{gol_gg_slug}'")
        return 0, 0, [], {}

    # Filtrar por semana si aplica
    if week_filter is not None:
        all_entries = [e for e in all_entries if e.week in week_filter]

    if not all_entries:
        week_desc = f"semanas {week_filter.start}-{week_filter.stop - 1}" if week_filter else "todas las semanas"
        print(f"[WARN] No hay entries para {week_desc}")
        return 0, 0, [], {}

    if dry_run:
        print(f"[DRY RUN] Matchlist fetched: {len(all_entries)} entries filtradas")
    else:
        print(f"Matchlist fetched: {len(all_entries)} entries")

    # Agrupar por semana
    entries_by_week: dict[int, list] = defaultdict(list)
    for entry in all_entries:
        entries_by_week[entry.week].append(entry)

    # Snapshot de game_ids existentes (para dry-run también — reportar nuevo vs existente)
    print("Leyendo game_ids existentes en DB...")
    try:
        resp = supabase.table("player_game_stats").select("game_id").execute()
        existing_game_ids: set[str] = {str(r["game_id"]) for r in (resp.data or [])}
        print(f"  {len(existing_game_ids)} game_ids ya tienen stats en DB")
    except Exception as exc:
        print(f"[WARN] No se pudo leer game_ids existentes: {exc}")
        existing_game_ids = set()

    # Acumuladores de reporting
    total_series = 0
    total_games = 0
    unresolved_players: list[str] = []
    errors_by_week: dict[int, str] = {}
    new_price_player_ids: set[str] = set()  # acumular pero no usar en backfill

    for week in sorted(entries_by_week.keys()):
        week_entries = entries_by_week[week]
        print(f"\nProcesando semana {week}: {len(week_entries)} entries encontradas")

        # Agrupar en series: key = (team_home, team_away, date)
        series_map = defaultdict(list)
        for entry in week_entries:
            key = (entry.team_home, entry.team_away, entry.date)
            series_map[key].append(entry)

        # Ordenar games dentro de cada serie por game_id (numérico)
        for entries in series_map.values():
            entries.sort(key=lambda e: int(e.game_id))

        week_series = 0
        week_games = 0

        try:
            for (team_home_name, team_away_name, game_date), entries in series_map.items():
                # Resolver IDs de equipos
                team_home_id = _resolve_team_by_alias(supabase, team_home_name)
                team_away_id = _resolve_team_by_alias(supabase, team_away_name)

                if not team_home_id:
                    logger.warning("Skipping series: team_home '%s' not found", team_home_name)
                    unresolved_players.append(f"team:{team_home_name}")
                    continue
                if not team_away_id:
                    logger.warning("Skipping series: team_away '%s' not found", team_away_name)
                    unresolved_players.append(f"team:{team_away_name}")
                    continue

                if dry_run:
                    print(
                        f"  [DRY RUN] Serie: {team_home_name} vs {team_away_name} "
                        f"({game_date}) — {len(entries)} games"
                    )
                    for entry in entries:
                        status = "YA EXISTE" if entry.game_id in existing_game_ids else "NUEVO"
                        print(f"    Game {entry.game_id}: {status}")
                    week_series += 1
                    week_games += len(entries)
                    continue

                # Live: llamar _process_series
                try:
                    series_player_ids, series_id = await _process_series(
                        supabase,
                        competition_id=competition_id,
                        series_entries=entries,
                        team_home_id=team_home_id,
                        team_away_id=team_away_id,
                        existing_game_ids=existing_game_ids,
                        new_price_player_ids=new_price_player_ids,
                        league_tag=league_tag,
                        scoring_competition_id=competition_id,
                    )
                    week_series += 1
                    week_games += len(entries)
                    await asyncio.sleep(1)
                except Exception as exc:
                    logger.error(
                        "Error procesando serie %s vs %s (%s): %s",
                        team_home_name,
                        team_away_name,
                        game_date,
                        exc,
                        exc_info=True,
                    )

        except Exception as exc:
            errors_by_week[week] = str(exc)
            logger.error("Error procesando semana %d: %s", week, exc, exc_info=True)

        total_series += week_series
        total_games += week_games
        prefix = "[DRY RUN] " if dry_run else ""
        print(f"  {prefix}Semana {week}: {week_series} series, {week_games} games procesados")

    return total_series, total_games, unresolved_players, errors_by_week


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill series, games y player stats para una competition histórica."
    )
    parser.add_argument(
        "--competition-slug",
        required=True,
        help='gol_gg_slug exacto de la competition (ej. "LES 2026 Kick-off Tournament")',
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--weeks",
        metavar="N|N-M",
        help="Semana única (1) o rango inclusivo (1-9)",
    )
    group.add_argument(
        "--all-weeks",
        action="store_true",
        help="Procesa todas las semanas disponibles en el matchlist",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Lee gol.gg y DB pero NO escribe en DB",
    )

    args = parser.parse_args()

    # Validar credenciales
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not supabase_key:
        print("[ERROR] SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY son requeridos.")
        return 1

    supabase = create_client(supabase_url, supabase_key)

    # Resolver competition
    competition = get_competition_by_slug(supabase, args.competition_slug)
    competition_id = str(competition["id"])
    competition_name = competition.get("name", "<unnamed>")

    # Parsear rango de semanas
    week_filter: range | None = None
    if not args.all_weeks:
        week_filter = parse_week_range(args.weeks)
        week_desc = (
            f"semana {week_filter.start}"
            if len(week_filter) == 1
            else f"semanas {week_filter.start}-{week_filter.stop - 1}"
        )
        print(f"\nBackfill de {week_desc} para: {competition_name}")
    else:
        print(f"\nBackfill de TODAS las semanas para: {competition_name}")

    if args.dry_run:
        print("Modo: DRY RUN (no se escribirá nada en DB)\n")
    else:
        print()

    # Ejecutar backfill
    total_series, total_games, unresolved, errors_by_week = await run_backfill(
        supabase=supabase,
        competition=competition,
        week_filter=week_filter,
        dry_run=args.dry_run,
    )

    # Resumen final
    prefix = "[DRY RUN] " if args.dry_run else ""
    print(f"\n{prefix}=== RESUMEN BACKFILL ===")
    print(f"{prefix}Competition : {competition_name} (id={competition_id})")
    print(f"{prefix}Total series: {total_series}")
    print(f"{prefix}Total games : {total_games}")

    if errors_by_week:
        print(f"{prefix}Errores por semana:")
        for week, err in sorted(errors_by_week.items()):
            print(f"  Semana {week}: {err}")
    else:
        print(f"{prefix}Errores      : ninguno")

    if unresolved:
        print(f"{prefix}No resueltos : {unresolved}")
    else:
        print(f"{prefix}No resueltos : ninguno")

    return 1 if errors_by_week else 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
