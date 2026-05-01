#!/usr/bin/env python3
import argparse
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO

_backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
load_dotenv(os.path.join(_backend_dir, ".env"))
sys.path.insert(0, _backend_dir)

from supabase import create_client  # noqa: E402

DOWNLOAD_TIMEOUT = 15
RETRY_COUNT = 3
SLEEP_BETWEEN = 1.0
MAX_SIZE = (200, 200)

_HEADERS = {
    "User-Agent": "SummonersFantasy/1.0 (github.com/summoners-fantasy) python-requests/2.33"
}


def slug(name: str) -> str:
    return name.lower().replace(" ", "-")


def download_image(url: str) -> bytes | None:
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=DOWNLOAD_TIMEOUT)
            resp.raise_for_status()
            return resp.content
        except Exception as exc:
            print(f"    [WARN] Intento {attempt}/{RETRY_COUNT} fallido: {exc}")
            if attempt < RETRY_COUNT:
                time.sleep(SLEEP_BETWEEN)
    return None


def convert_to_webp(data: bytes, output_path: Path) -> bool:
    try:
        img = Image.open(BytesIO(data)).convert("RGBA")
        img.thumbnail(MAX_SIZE, Image.LANCZOS)
        img.save(output_path, "WEBP")
        return True
    except Exception as exc:
        print(f"    [ERROR] No se pudo convertir a webp: {exc}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Descarga imágenes de jugadores desde sus URLs y las convierte a .webp."
    )
    parser.add_argument("--league", default=None, help="Filtrar por liga (ej. LES, LEC).")
    parser.add_argument("--output-dir", default="/tmp/player_photos", help="Carpeta de destino.")
    parser.add_argument("--dry-run", action="store_true", help="Muestra qué haría sin descargar.")
    parser.add_argument("--force", action="store_true", help="Descarga aunque el .webp ya exista.")
    args = parser.parse_args()

    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not supabase_key:
        print("ERROR: SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY son requeridos en backend/.env")
        return 1

    supabase = create_client(supabase_url, supabase_key)

    output_dir = Path(args.output_dir)
    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Obteniendo jugadores de Supabase...")

    query = supabase.table("players").select("id, name, league, team, image_url")

    if args.league:
        query = query.eq("league", args.league)

    if args.force:
        query = query.not_.is_("image_url", "null")
    else:
        query = query.not_.is_("image_url", "null").not_.ilike("image_url", "%supabase.co%")

    result = query.execute()
    players = result.data

    if not players:
        print("No hay jugadores para procesar.")
        return 0

    total = len(players)
    league_label = args.league or "todas las ligas"
    print(f"Procesando {total} jugador(es) de {league_label}...\n")

    ok: list[str] = []
    failed: list[str] = []
    skipped: list[str] = []

    for i, player in enumerate(players, 1):
        name = player["name"]
        image_url = player.get("image_url")
        league = player.get("league", "?")
        team = player.get("team", "?")

        print(f"[{i}/{total}] {name} ({league}, {team})")

        if not image_url:
            print("    [SKIP] Sin image_url.")
            skipped.append(name)
            continue

        filename = slug(name) + ".webp"
        output_path = output_dir / filename

        if not args.force and output_path.exists():
            print(f"    [SKIP] Ya existe: {output_path}")
            skipped.append(name)
            continue

        if args.dry_run:
            print(f"    [DRY RUN] Descargaría {image_url[:80]}{'...' if len(image_url) > 80 else ''}")
            print(f"    [DRY RUN] Guardaría como {output_path}")
            ok.append(name)
            continue

        print(f"    Descargando: {image_url[:80]}{'...' if len(image_url) > 80 else ''}")
        data = download_image(image_url)

        if data is None:
            print("    [ERROR] No se pudo descargar.")
            failed.append(name)
            time.sleep(SLEEP_BETWEEN)
            continue

        if not convert_to_webp(data, output_path):
            failed.append(name)
        else:
            print(f"    -> OK: {output_path}")
            ok.append(name)

        time.sleep(SLEEP_BETWEEN)

    print(f"\n{'=' * 50}")
    print(f"{'[DRY RUN] ' if args.dry_run else ''}=== Resumen ===")
    print(f"  ✓ Descargados:  {len(ok)}/{total}")
    print(f"  ✗ Fallidos:     {len(failed)}/{total}")
    print(f"  ~ Salteados:    {len(skipped)}/{total}")

    if failed:
        print("\n  Jugadores fallidos:")
        for n in failed:
            print(f"    - {n}")

    if args.dry_run:
        print("\n  [DRY RUN] Ningún archivo escrito.")

    return 0 if not failed else 2


if __name__ == "__main__":
    sys.exit(main())
