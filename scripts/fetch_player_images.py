#!/usr/bin/env python3
"""
Obtiene fotos de jugadores desde Leaguepedia (API Cargo) y actualiza
el campo `image_url` en la tabla `players` de Supabase.

Uso:
    python scripts/fetch_player_images.py
    python scripts/fetch_player_images.py --league LES
    python scripts/fetch_player_images.py --league LES --dry-run
    python scripts/fetch_player_images.py --league LES --force
    python scripts/fetch_player_images.py --force  # sobreescribe todos

Estrategia de resolución de imágenes (3 capas):
    1. Players Cargo table: Player='NOMBRE' → campo Image
    2. Players Cargo table: Player LIKE 'NOMBRE' → campo Image (case-insensitive)
    3. MediaWiki page images: titles=NOMBRE → prop=images → primer File: imagen

Notas sobre Leaguepedia:
    - La tabla Players de Cargo NO siempre tiene Image para jugadores de
      ligas menores (LES, etc). En ese caso, la capa 3 busca images en la
      página del jugador directamente.
    - El rate limit de la API es agresivo: usar SLEEP_BETWEEN_REQUESTS >= 1.5s
      cuando se procesen muchos jugadores de una vez.
"""

import argparse
import os
import sys
import time

import requests
from dotenv import load_dotenv

# Cargar .env desde backend/ (igual que ingest_league.py)
_backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
load_dotenv(os.path.join(_backend_dir, ".env"))
sys.path.insert(0, _backend_dir)

from supabase import create_client  # noqa: E402

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

LEAGUEPEDIA_API = "https://lol.fandom.com/api.php"
# 1.5s entre requests para no saturar Leaguepedia.
# Con el dry-run de 40 jugadores (que usaba 0.5s) nos rate-limitaron.
SLEEP_BETWEEN_REQUESTS = 3.0

# User-Agent recomendado por la política de Wikimedia
_HEADERS = {
    "User-Agent": "SummonersFantasy/1.0 (github.com/summoners-fantasy) python-requests/2.33"
}


# ---------------------------------------------------------------------------
# Leaguepedia helpers
# ---------------------------------------------------------------------------


def _get(params: dict) -> dict | None:
    """
    GET a la API de Leaguepedia con manejo básico de errores.

    Returns:
        Dict con la respuesta JSON, o None si falló la request o vino rate-limited.
    """
    try:
        resp = requests.get(
            LEAGUEPEDIA_API, params=params, timeout=15, headers=_HEADERS
        )
        resp.raise_for_status()
        data = resp.json()

        if "error" in data:
            err_code = data["error"].get("code", "unknown")
            if err_code == "ratelimited":
                print("    [WARN] Rate limited por Leaguepedia — esperando 30s...")
                time.sleep(30)
                # Reintento único
                resp = requests.get(
                    LEAGUEPEDIA_API, params=params, timeout=15, headers=_HEADERS
                )
                data = resp.json()
                if "error" in data:
                    print(f"    [WARN] Sigue rate-limited: {data['error'].get('code')}")
                    return None
            else:
                print(f"    [WARN] API error: {err_code} — {data['error'].get('info', '')[:80]}")
                return None

        return data
    except Exception as exc:
        print(f"    [WARN] Request error: {exc}")
        return None


def _search_cargo_players(player_name: str, use_like: bool = False) -> str | None:
    """
    Busca un jugador en la tabla Players de Cargo y devuelve el filename de Image.

    Args:
        player_name: Nick del jugador.
        use_like: Si True usa LIKE en lugar de igualdad exacta.

    Returns:
        Nombre del archivo de imagen (ej. "Faker 2024.png") o None.
    """
    operator = "LIKE" if use_like else "="
    params = {
        "action": "cargoquery",
        "tables": "Players",
        "fields": "Player,OverviewPage,Image",
        "where": f"Player {operator} '{player_name}'",
        "format": "json",
        "limit": "5",
    }
    data = _get(params)
    if not data:
        return None

    results = data.get("cargoquery", [])
    # Puede haber múltiples results (ej. el mismo nick en distintas épocas).
    # Devolvemos el primero que tenga Image.
    for r in results:
        image = r.get("title", {}).get("Image", "").strip()
        if image:
            return image

    return None


def _search_page_images(player_name: str) -> str | None:
    """
    Busca imágenes en la página wiki del jugador usando prop=images.

    Leaguepedia tiene páginas wiki para cada jugador (ej. /wiki/Flakked).
    La API `action=query&titles=Flakked&prop=images` devuelve todos los
    File: que aparecen en esa página. Filtramos el primero que tenga el
    nombre del jugador en el filename (case-insensitive) o el primero que
    no sea un ícono/logo.

    Returns:
        Nombre del archivo de imagen o None.
    """
    params = {
        "action": "query",
        "titles": player_name,
        "prop": "images",
        "imlimit": "20",
        "format": "json",
    }
    data = _get(params)
    if not data:
        return None

    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        # Página no encontrada → tiene pageId negativo
        if page.get("pageid", -1) < 0:
            return None

        images = page.get("images", [])
        if not images:
            return None

        player_lower = player_name.lower()

        # Prioridad: imagen cuyo título contenga el nick del jugador
        for img in images:
            title = img.get("title", "")
            filename = title.replace("File:", "").strip()
            if player_lower in filename.lower():
                return filename

        # Fallback: primera imagen que tenga extensión de foto
        for img in images:
            title = img.get("title", "")
            filename = title.replace("File:", "").strip()
            if any(filename.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg")):
                return filename

    return None


def _resolve_image_url(image_filename: str) -> str | None:
    """
    Convierte un nombre de archivo en la URL directa del CDN de Leaguepedia.

    Usa action=query&prop=imageinfo en la API de MediaWiki.

    Returns:
        URL directa a la imagen o None.
    """
    params = {
        "action": "query",
        "titles": f"File:{image_filename}",
        "prop": "imageinfo",
        "iiprop": "url",
        "format": "json",
    }
    data = _get(params)
    if not data:
        return None

    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        imageinfo = page.get("imageinfo", [])
        if imageinfo:
            url = imageinfo[0].get("url", "").strip()
            if url:
                return url

    return None


def fetch_player_image_url(player_name: str) -> tuple[str | None, str]:
    """
    Resuelve la URL de imagen de un jugador con estrategia de 3 capas.

    Returns:
        (url, method) donde method es "cargo-exact", "cargo-like",
        "page-images", o "unresolved".
    """
    # Capa 1: Players cargo, búsqueda exacta
    filename = _search_cargo_players(player_name, use_like=False)
    time.sleep(SLEEP_BETWEEN_REQUESTS)

    if not filename:
        # Capa 2: Players cargo, búsqueda LIKE (case-insensitive)
        filename = _search_cargo_players(player_name, use_like=True)
        time.sleep(SLEEP_BETWEEN_REQUESTS)

        if filename:
            method = "cargo-like"
        else:
            # Capa 3: page images de la wiki del jugador
            filename = _search_page_images(player_name)
            time.sleep(SLEEP_BETWEEN_REQUESTS)
            method = "page-images" if filename else "unresolved"
    else:
        method = "cargo-exact"

    if not filename:
        return None, "unresolved"

    # Resolver URL CDN desde el filename
    url = _resolve_image_url(filename)
    time.sleep(SLEEP_BETWEEN_REQUESTS)

    if url:
        return url, method
    else:
        return None, "unresolved"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Obtiene fotos de jugadores desde Leaguepedia y actualiza Supabase."
    )
    parser.add_argument(
        "--league",
        default=None,
        help="Filtrar por liga (ej. LES, LEC). Sin este flag procesa todos.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Sobreescribir image_url aunque ya tenga valor.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostrar qué haría sin escribir en DB.",
    )
    args = parser.parse_args()

    # Inicializar Supabase
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not supabase_key:
        print("ERROR: SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY son requeridos en el .env")
        return 1

    supabase = create_client(supabase_url, supabase_key)

    # Obtener jugadores de Supabase
    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Obteniendo jugadores de Supabase...")

    query = supabase.table("players").select("id, name, team, league")

    if args.league:
        query = query.eq("league", args.league)

    if not args.force:
        query = query.is_("image_url", "null")

    result = query.execute()
    players = result.data

    if not players:
        print("No hay jugadores para procesar (ya tienen imagen o no existen).")
        print("Usa --force para sobreescribir jugadores que ya tienen imagen.")
        return 0

    total = len(players)
    league_label = args.league or "todas las ligas"
    print(f"Procesando {total} jugador(es) de {league_label}...\n")
    print(f"Delay entre requests: {SLEEP_BETWEEN_REQUESTS}s\n")

    resolved: list[dict] = []
    unresolved: list[dict] = []

    for i, player in enumerate(players, 1):
        player_name = player["name"]
        player_id = player["id"]
        player_league = player.get("league", "?")
        player_team = player.get("team", "?")

        print(f"[{i}/{total}] {player_name} ({player_league}, {player_team})")

        image_url, method = fetch_player_image_url(player_name)

        if image_url:
            print(f"  -> OK [{method}]: {image_url[:80]}{'...' if len(image_url) > 80 else ''}")

            if args.dry_run:
                print("  [DRY RUN] No se escribe en DB.")
            else:
                try:
                    supabase.table("players").update(
                        {"image_url": image_url}
                    ).eq("id", player_id).execute()
                    print("  -> Guardado en DB.")
                except Exception as exc:
                    print(f"  [ERROR] No se pudo guardar en DB: {exc}")
                    unresolved.append(player)
                    continue

            resolved.append(player)
        else:
            print("  -> [UNRESOLVED]")
            unresolved.append(player)

    # Resumen final
    print(f"\n{'=' * 50}")
    print(f"{'[DRY RUN] ' if args.dry_run else ''}=== Resumen ===")
    print(f"  ✓ Resueltos:    {len(resolved)}/{total}")
    print(f"  ✗ Sin resolver: {len(unresolved)}/{total}")

    if unresolved:
        print("\n  Jugadores sin resolver:")
        for p in unresolved:
            print(f"    - {p['name']} ({p.get('league', '?')}, {p.get('team', '?')})")

    if args.dry_run and resolved:
        print("\n  [DRY RUN] Ningún cambio escrito en DB.")
        print("  Corré sin --dry-run para aplicar los cambios.")

    return 0 if not unresolved else 2


if __name__ == "__main__":
    sys.exit(main())
