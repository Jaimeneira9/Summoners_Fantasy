#!/usr/bin/env python3
"""
CLI para ingestar equipos de una liga desde gol.gg y seedear scoring_config.

Qué hace este script:
  1. Upsert de la competition en la tabla `competitions`.
  2. Scrapea gol.gg para obtener la lista de equipos del torneo.
  3. Upsert de los equipos en la tabla `teams`.
  4. Seedea `scoring_config` con los pesos por rol del scoring engine.

Qué NO hace:
  - NO inserta players. Los players se ingresan orgánicamente cuando se
    procesan series (series_ingest.py). gol.gg no expone un roster endpoint
    funcional — los jugadores aparecen al ingestar partidas individuales.

Uso:
    python scripts/ingest_league.py --league LEC
    python scripts/ingest_league.py --league LEC --dry-run
"""
import argparse
import asyncio
import os
import sys

from dotenv import load_dotenv

# Load .env from backend directory
_backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
load_dotenv(os.path.join(_backend_dir, ".env"))
sys.path.insert(0, _backend_dir)

from supabase import create_client

from pipeline.gol_gg import fetch_team_list
from scoring.engine import ROLE_WEIGHTS

# ---------------------------------------------------------------------------
# Registry de ligas conocidas
# ---------------------------------------------------------------------------

LEAGUE_REGISTRY: dict[str, dict] = {
    "LEC": {
        "name": "LEC",
        "region": "Europe",
        "tier": 1,
        "gol_gg_slug": "LEC 2026 Spring Season",
    },
    "LCK": {
        "name": "LCK",
        "region": "Korea",
        "tier": 1,
        "gol_gg_slug": "LCK 2026 Spring",
    },
    "LPL": {
        "name": "LPL",
        "region": "China",
        "tier": 1,
        "gol_gg_slug": "LPL 2026 Spring",
    },
    "LCS": {
        "name": "LCS",
        "region": "North America",
        "tier": 1,
        "gol_gg_slug": "LCS 2026 Spring",
    },
}

# Roles que participan en el fantasy (excluye coach por ahora — sistema WIP)
_FANTASY_ROLES = [role for role in ROLE_WEIGHTS if role != "coach"]


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------


def step_upsert_competition(supabase, league_config: dict, dry_run: bool) -> str | None:
    """
    SELECT + INSERT/UPDATE de la competition en la tabla `competitions`.

    No usa upsert con on_conflict porque competitions no tiene UNIQUE constraint
    en gol_gg_slug (PostgREST requiere la constraint para resolver ON CONFLICT).
    En cambio: busca por slug, actualiza si existe, inserta si no existe.
    is_active no se toca en el update — no sobreescribir si ya estaba activa.

    Returns:
        competition_id (uuid string), "dry-run-competition-id" en dry-run,
        o None si falla (el caller debe abortar).
    """
    slug = league_config["gol_gg_slug"]

    if dry_run:
        payload = {
            "name": league_config["name"],
            "region": league_config["region"],
            "tier": league_config["tier"],
            "gol_gg_slug": slug,
            "is_active": False,
        }
        print(f"[DRY RUN] step_upsert_competition — payload: {payload}")
        return "dry-run-competition-id"

    # Buscar si ya existe por slug
    result = supabase.table("competitions").select("id").eq("gol_gg_slug", slug).execute()

    if result.data:
        competition_id = result.data[0]["id"]
        # Update nombre/región/tier pero NO is_active (no sobreescribir si ya estaba activa)
        supabase.table("competitions").update({
            "name": league_config["name"],
            "region": league_config["region"],
            "tier": league_config["tier"],
        }).eq("id", competition_id).execute()
        print(f"  Competition existente actualizada: {league_config['name']} ({competition_id})")
    else:
        # Insert nuevo con is_active=False por defecto
        insert_result = supabase.table("competitions").insert({
            "name": league_config["name"],
            "region": league_config["region"],
            "tier": league_config["tier"],
            "gol_gg_slug": slug,
            "is_active": False,
        }).execute()
        competition_id = insert_result.data[0]["id"]
        print(f"  Competition creada: {league_config['name']} ({competition_id})")

    return competition_id


async def step_scrape_team_list(
    tournament_slug: str, dry_run: bool
) -> list[tuple[str, str]]:
    """
    Scrapea gol.gg para obtener la lista de equipos del torneo.

    El scraping es read-only, así que se ejecuta igual en dry-run.

    Returns:
        Lista de (team_name, gol_gg_numeric_id).
    """
    print(f"  Scraping team list for: {tournament_slug}")
    teams = await fetch_team_list(tournament_slug)
    print(f"  Found {len(teams)} teams")
    if dry_run:
        for name, team_id in teams:
            print(f"  [DRY RUN] Team: {name!r} (gol.gg id: {team_id})")
    return teams


def step_upsert_teams(
    supabase,
    teams: list[tuple[str, str]],
    competition_id: str,
    dry_run: bool,
) -> int:
    """
    Upsert de los equipos en la tabla `teams`.

    Usa on_conflict="code,competition_id" (constraint aplicado en migración
    20260417000002_fix_teams_code_unique.sql).

    El `code` se genera como slug del nombre (ej. "g2-esports").
    El `gol_gg_id` (numeric id de gol.gg) se guarda si la tabla lo tiene.

    Returns:
        Cantidad de teams procesados.
    """
    count = 0
    for team_name, gol_gg_numeric_id in teams:
        # Generar code como slug: "G2 Esports" → "g2-esports"
        code = team_name.lower().replace(" ", "-")

        payload = {
            "name": team_name,
            "code": code,
            "competition_id": competition_id,
        }

        if dry_run:
            print(
                f"  [DRY RUN] step_upsert_teams — "
                f"team: {team_name!r}, code: {code!r}, "
                f"gol_gg_id: {gol_gg_numeric_id}, competition_id: {competition_id}"
            )
            count += 1
            continue

        try:
            supabase.table("teams").upsert(
                payload, on_conflict="code,competition_id"
            ).execute()
            print(f"  Team upserted: {team_name} ({code})")
            count += 1
        except Exception as exc:
            print(f"  [WARN] Failed to upsert team {team_name!r}: {exc}")

    return count


def step_seed_scoring_config(
    supabase, competition_id: str, dry_run: bool
) -> int:
    """
    Upsert de scoring_config para todos los roles fantasy.

    Usa on_conflict="competition_id,role" (constraint en scoring_config tabla).
    Los pesos vienen de ROLE_WEIGHTS del scoring engine — fuente única de verdad.
    multikill_bonuses se deja en None (hereda el default del engine en runtime).

    Returns:
        Cantidad de rows seeded.
    """
    count = 0
    for role in _FANTASY_ROLES:
        weights = ROLE_WEIGHTS[role]
        payload = {
            "competition_id": competition_id,
            "role": role,
            "weights": weights,
            "multikill_bonuses": None,
        }

        if dry_run:
            print(
                f"  [DRY RUN] step_seed_scoring_config — "
                f"role: {role!r}, weights keys: {list(weights.keys())}"
            )
            count += 1
            continue

        try:
            supabase.table("scoring_config").upsert(
                payload, on_conflict="competition_id,role"
            ).execute()
            print(f"  Scoring config seeded: {role}")
            count += 1
        except Exception as exc:
            print(f"  [WARN] Failed to seed scoring_config for role {role!r}: {exc}")

    return count


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> int:
    """
    Orquesta los steps de ingestion.

    Exit codes:
        0 — todo OK
        1 — uno o más steps fallaron con errores
    """
    parser = argparse.ArgumentParser(
        description="Ingesta equipos de una liga desde gol.gg y seedea scoring_config."
    )
    parser.add_argument(
        "--league",
        required=True,
        choices=list(LEAGUE_REGISTRY.keys()),
        help="Liga a ingestar (ej. LEC, LCK, LPL, LCS)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula sin escribir en DB. El scraping de gol.gg se ejecuta igual (read-only).",
    )
    args = parser.parse_args()

    league_config = LEAGUE_REGISTRY[args.league]
    dry_run: bool = args.dry_run

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Ingestando: {args.league}")
    print(f"  gol.gg slug: {league_config['gol_gg_slug']}")
    print()

    errors: list[str] = []

    # Crear Supabase client (solo si no es dry-run total — igual se crea para simplificar)
    if not dry_run:
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        if not supabase_url or not supabase_key:
            print("ERROR: SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY son requeridos.")
            return 1
        supabase = create_client(supabase_url, supabase_key)
    else:
        supabase = None

    # ── Step 1: Upsert competition ────────────────────────────────────────
    print("Step 1: Upsert competition...")
    competition_id: str | None = None
    try:
        competition_id = step_upsert_competition(supabase, league_config, dry_run)
    except Exception as exc:
        msg = f"step_upsert_competition failed: {exc}"
        print(f"  [ERROR] {msg}")
        errors.append(msg)

    if competition_id is None:
        print("[ERROR] No se pudo obtener competition_id, abortando.")
        return 1

    # ── Step 2: Scrape team list ──────────────────────────────────────────
    print("\nStep 2: Scrape team list from gol.gg...")
    teams: list[tuple[str, str]] = []
    try:
        teams = await step_scrape_team_list(league_config["gol_gg_slug"], dry_run)
    except Exception as exc:
        msg = f"step_scrape_team_list failed: {exc}"
        print(f"  [ERROR] {msg}")
        errors.append(msg)

    # ── Step 3: Upsert teams ──────────────────────────────────────────────
    print("\nStep 3: Upsert teams...")
    teams_count = 0
    try:
        teams_count = step_upsert_teams(supabase, teams, competition_id, dry_run)
    except Exception as exc:
        msg = f"step_upsert_teams failed: {exc}"
        print(f"  [ERROR] {msg}")
        errors.append(msg)

    # ── Step 4: Seed scoring config ───────────────────────────────────────
    print("\nStep 4: Seed scoring_config...")
    configs_seeded = 0
    try:
        configs_seeded = step_seed_scoring_config(supabase, competition_id, dry_run)
    except Exception as exc:
        msg = f"step_seed_scoring_config failed: {exc}"
        print(f"  [ERROR] {msg}")
        errors.append(msg)

    # ── Resumen ───────────────────────────────────────────────────────────
    print(f"\n{'[DRY RUN] ' if dry_run else ''}=== Resumen ===")
    print(f"  Competition ID : {competition_id}")
    print(f"  Teams upserted : {teams_count}")
    print(f"  Configs seeded : {configs_seeded}")
    if errors:
        print(f"  Errores ({len(errors)}):")
        for err in errors:
            print(f"    - {err}")
        return 1

    print("  Sin errores.")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
