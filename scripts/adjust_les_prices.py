#!/usr/bin/env python3
"""
Ajusta current_price de jugadores LES usando min-max scaling sobre avg series_points.

Uso:
    python scripts/adjust_les_prices.py --competitions "LES 2026 Kick-off Tournament"
    python scripts/adjust_les_prices.py --leagues LES --dry-run
    python scripts/adjust_les_prices.py --competitions "LES 2026 Spring,LES 2026 Kick-off Tournament"
"""
import argparse
import os
import sys
from datetime import date

from dotenv import load_dotenv

_backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
load_dotenv(os.path.join(_backend_dir, ".env"))
sys.path.insert(0, _backend_dir)

from supabase import create_client

LEAGUE_PREFIXES: dict[str, str] = {
    "LES": "LES",
    "LEC": "LEC",
    "LCK": "LCK",
    "LPL": "LPL",
    "LCS": "LCS",
}


def fetch_avg_points(supabase, competition_names: list[str]) -> dict[str, float]:
    """
    Devuelve {player_id: avg_points} para jugadores con stats en las competiciones dadas.
    Agrega en Python para no depender de funciones SQL del cliente.
    """
    comp_result = (
        supabase.table("competitions")
        .select("id,name")
        .in_("name", competition_names)
        .execute()
    )
    if not comp_result.data:
        print(f"[ERROR] No se encontraron competiciones: {competition_names}")
        sys.exit(1)

    found_names = [r["name"] for r in comp_result.data]
    missing = [n for n in competition_names if n not in found_names]
    if missing:
        print(f"[WARN] Competiciones no encontradas en DB: {missing}")

    competition_ids = [r["id"] for r in comp_result.data]
    print(f"  Competiciones encontradas: {found_names}")

    series_result = (
        supabase.table("series")
        .select("id")
        .in_("competition_id", competition_ids)
        .execute()
    )
    if not series_result.data:
        print("[ERROR] No hay series para esas competiciones.")
        sys.exit(1)

    series_ids = [r["id"] for r in series_result.data]
    print(f"  Series encontradas: {len(series_ids)}")

    all_stats: list[dict] = []
    page_size = 1000
    offset = 0
    while True:
        batch = (
            supabase.table("player_series_stats")
            .select("player_id,series_points")
            .in_("series_id", series_ids)
            .range(offset, offset + page_size - 1)
            .execute()
            .data or []
        )
        all_stats.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size

    if not all_stats:
        print("[ERROR] No hay stats para esas series.")
        sys.exit(1)

    print(f"  Registros de stats: {len(all_stats)}")

    totals: dict[str, list[float]] = {}
    for row in all_stats:
        if row["series_points"] is None:
            continue
        totals.setdefault(row["player_id"], []).append(float(row["series_points"]))

    return {pid: sum(pts) / len(pts) for pid, pts in totals.items()}


def fetch_players(supabase, leagues: list[str]) -> list[dict]:
    return (
        supabase.table("players")
        .select("id,name,league,current_price,price_history")
        .in_("league", leagues)
        .execute()
        .data or []
    )


def resolve_competitions_from_leagues(supabase, leagues: list[str]) -> list[str]:
    all_comps = supabase.table("competitions").select("name").execute().data or []
    prefixes = [LEAGUE_PREFIXES.get(lg.upper(), lg) for lg in leagues]
    names = [
        c["name"]
        for c in all_comps
        if any(c["name"].startswith(p) for p in prefixes)
    ]
    if not names:
        print(f"[ERROR] No se encontraron competiciones para leagues: {leagues}")
        sys.exit(1)
    return names


def scale_price(avg_pts: float, max_avg: float, min_price: float, max_price: float) -> float:
    clamped = max(0.0, avg_pts)
    price = min_price + (clamped / max_avg) * (max_price - min_price)
    price = round(price, 2)
    return max(min_price, min(max_price, price))


def print_table(rows: list[dict]) -> None:
    col = max((len(r["name"]) for r in rows), default=4)
    col = max(col, 20)
    header = f"{'nombre':<{col}}  {'avg_pts':>8}  {'precio_anterior':>15}  {'precio_nuevo':>12}"
    print(header)
    print("-" * len(header))
    for r in sorted(rows, key=lambda x: x["new_price"], reverse=True):
        print(
            f"{r['name']:<{col}}  "
            f"{r['avg_pts']:>8.2f}  "
            f"{r['old_price']:>15.2f}  "
            f"{r['new_price']:>12.2f}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ajusta current_price de jugadores via min-max scaling sobre avg series_points."
    )
    parser.add_argument(
        "--leagues",
        default="LES",
        help="Liga(s) de jugadores separadas por coma (default: LES). Usado si no se pasa --competitions.",
    )
    parser.add_argument(
        "--competitions",
        default=None,
        help='Nombres exactos de competición separados por coma. Override de --leagues.',
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--min-price", type=float, default=8.0)
    parser.add_argument("--max-price", type=float, default=37.0)
    args = parser.parse_args()

    if args.min_price >= args.max_price:
        print(f"[ERROR] --min-price ({args.min_price}) debe ser menor que --max-price ({args.max_price}).")
        return 1

    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not supabase_key:
        print("ERROR: SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY son requeridos en backend/.env")
        return 1

    supabase = create_client(supabase_url, supabase_key)

    leagues = [lg.strip() for lg in args.leagues.split(",") if lg.strip()]

    if args.competitions:
        competition_names = [c.strip() for c in args.competitions.split(",") if c.strip()]
    else:
        competition_names = resolve_competitions_from_leagues(supabase, leagues)

    min_price: float = args.min_price
    max_price: float = args.max_price
    dry_run: bool = args.dry_run

    print(f"\n{'[DRY RUN] ' if dry_run else ''}=== Ajuste de precios ===")
    print(f"  Ligas         : {', '.join(leagues)}")
    print(f"  Competiciones : {', '.join(competition_names)}")
    print(f"  Rango         : [{min_price}M, {max_price}M]")
    print()

    # ── Paso 1: avg_points por jugador ────────────────────────────────────
    print("Paso 1: Calculando avg_points...")
    avg_by_player = fetch_avg_points(supabase, competition_names)
    print(f"  Jugadores con stats: {len(avg_by_player)}")

    if not avg_by_player:
        print("[ERROR] No hay datos de puntos para calcular precios.")
        return 1

    max_avg = max(max(0.0, v) for v in avg_by_player.values())
    if max_avg <= 0:
        print("[ERROR] max_avg es 0 — todos los avg_points son <= 0, no se puede escalar.")
        return 1

    print(f"  max_avg_points: {max_avg:.4f}")

    # ── Paso 2: jugadores de las ligas ────────────────────────────────────
    print(f"\nPaso 2: Cargando jugadores de ligas: {', '.join(leagues)}...")
    players = fetch_players(supabase, leagues)
    print(f"  Jugadores encontrados: {len(players)}")

    if not players:
        print("[WARN] No hay jugadores para esas ligas.")
        return 0

    # ── Paso 3: calcular nuevos precios ───────────────────────────────────
    print("\nPaso 3: Calculando nuevos precios...")

    today_iso = date.today().isoformat()
    to_update: list[dict] = []
    skipped: list[str] = []

    for player in players:
        pid = player["id"]
        name = player["name"]
        old_price = float(player.get("current_price") or min_price)

        if pid not in avg_by_player:
            print(f"  [WARN] Sin stats: {name} — skip.")
            skipped.append(name)
            continue

        avg_pts = avg_by_player[pid]
        new_price = scale_price(avg_pts, max_avg, min_price, max_price)

        existing_history = player.get("price_history") or []
        updated_history = existing_history + [
            {"price": new_price, "date": today_iso, "reason": "kickoff_adjustment"}
        ]

        to_update.append({
            "id": pid,
            "name": name,
            "avg_pts": avg_pts,
            "old_price": old_price,
            "new_price": new_price,
            "price_history": updated_history,
        })

    # ── Paso 4: tabla ─────────────────────────────────────────────────────
    print()
    if to_update:
        print_table(to_update)
    else:
        print("  No hay jugadores para actualizar.")

    # ── Paso 5: escribir en DB ────────────────────────────────────────────
    errors: list[str] = []
    if not dry_run and to_update:
        print("\nPaso 4: Actualizando DB...")
        for row in to_update:
            try:
                supabase.table("players").update(
                    {
                        "current_price": row["new_price"],
                        "price_history": row["price_history"],
                    }
                ).eq("id", row["id"]).execute()
            except Exception as exc:
                msg = f"{row['name']}: {exc}"
                print(f"  [ERROR] {msg}")
                errors.append(msg)

    # ── Resumen ───────────────────────────────────────────────────────────
    print(f"\n{'[DRY RUN] ' if dry_run else ''}=== Resumen ===")
    print(f"  Procesados   : {len(to_update)}")
    print(f"  Skipped      : {len(skipped)} (sin stats)")
    if skipped:
        for name in skipped:
            print(f"    - {name}")
    if errors:
        print(f"  Errores DB   : {len(errors)}")
        for e in errors:
            print(f"    - {e}")
        return 1
    if dry_run:
        print("  DB no modificada (dry-run)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
