"""
Recalcula game_points en player_game_stats usando el engine de puntuación actual,
luego actualiza series_points en player_series_stats y avg_points_baseline en players.

Uso:
  backend/venv/bin/python scripts/recalculate_points.py [--dry-run]
"""
import argparse
import os
import sys

from dotenv import load_dotenv

# Cargar .env del backend y agregar el directorio al path
_backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
load_dotenv(os.path.join(_backend_dir, ".env"))
sys.path.insert(0, _backend_dir)

from supabase import create_client
from scoring.engine import calculate_match_points


def main(dry_run: bool = False) -> None:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    supabase = create_client(url, key)

    # ------------------------------------------------------------------
    # 1. Traer todos los registros de player_game_stats con rol y duration
    # ------------------------------------------------------------------
    print("Fetching player_game_stats...")

    # Paginamos de a 1000 para no reventar la memoria
    PAGE_SIZE = 1000
    all_rows: list[dict] = []
    offset = 0

    while True:
        resp = (
            supabase.table("player_game_stats")
            .select(
                "id, player_id, game_id, kills, deaths, assists, cs_per_min, "
                "gold_diff_15, xp_diff_15, dpm, vision_score, turret_damage, "
                "objective_steals, double_kill, triple_kill, quadra_kill, penta_kill, "
                "players(role), games(duration_min)"
            )
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
        )
        batch = resp.data or []
        all_rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    total = len(all_rows)
    print(f"Total registros encontrados: {total}")

    if total == 0:
        print("No hay registros para procesar.")
        return

    # ------------------------------------------------------------------
    # 2. Recalcular game_points para cada registro
    # ------------------------------------------------------------------
    updated_game_stats = 0
    skipped = 0

    for row in all_rows:
        role = (row.get("players") or {}).get("role")
        duration_raw = (row.get("games") or {}).get("duration_min")

        if not role or duration_raw is None:
            skipped += 1
            continue

        duration_min = float(duration_raw)

        stats = {
            "kills":            row.get("kills") or 0,
            "deaths":           row.get("deaths") or 0,
            "assists":          row.get("assists") or 0,
            "cs_per_min":       row.get("cs_per_min") or 0,
            "gold_diff_15":     row.get("gold_diff_15"),
            "xp_diff_15":       row.get("xp_diff_15"),
            "dpm":              row.get("dpm") or 0,
            "vision_score":     row.get("vision_score"),
            "turret_damage":    row.get("turret_damage") or 0,
            "objective_steals": row.get("objective_steals") or 0,
            "double_kill":      row.get("double_kill") or False,
            "triple_kill":      row.get("triple_kill") or False,
            "quadra_kill":      row.get("quadra_kill") or False,
            "penta_kill":       row.get("penta_kill") or False,
        }

        new_points = calculate_match_points(stats=stats, role=role, game_duration_min=duration_min)

        if not dry_run:
            supabase.table("player_game_stats").update(
                {"game_points": new_points}
            ).eq("id", row["id"]).execute()

        updated_game_stats += 1

    print(f"\n[PASO 1] game_points recalculados: {updated_game_stats} / {total}  (skipped: {skipped})")

    # ------------------------------------------------------------------
    # 3. Recalcular series_points en player_series_stats
    #    = SUM(game_points) de todos los juegos de esa serie para ese jugador
    # ------------------------------------------------------------------
    print("\nFetching player_series_stats...")
    pss_resp = (
        supabase.table("player_series_stats")
        .select("id, player_id, series_id")
        .execute()
    )
    pss_rows = pss_resp.data or []
    print(f"Total registros player_series_stats: {len(pss_rows)}")

    updated_series_stats = 0

    for pss in pss_rows:
        player_id = pss["player_id"]
        series_id = pss["series_id"]
        pss_id = pss["id"]

        # Buscar todos los game_points de este jugador en juegos de esta serie
        games_resp = (
            supabase.table("player_game_stats")
            .select("game_points, games(series_id)")
            .eq("player_id", player_id)
            .execute()
        )
        game_rows = games_resp.data or []

        # Filtrar solo los juegos que pertenecen a esta serie
        series_points = sum(
            float(g.get("game_points") or 0)
            for g in game_rows
            if (g.get("games") or {}).get("series_id") == series_id
        )
        series_points = round(series_points, 2)

        if not dry_run:
            supabase.table("player_series_stats").update(
                {"series_points": series_points}
            ).eq("id", pss_id).execute()

        updated_series_stats += 1

    print(f"[PASO 2] series_points actualizados: {updated_series_stats}")

    # ------------------------------------------------------------------
    # 4. Actualizar avg_points_baseline en players
    #    = AVG(game_points) de todos los juegos del jugador
    # ------------------------------------------------------------------
    print("\nCalculando avg_points_baseline por jugador...")

    # Agrupar game_points por player_id desde los datos ya cargados
    from collections import defaultdict
    points_by_player: dict[str, list[float]] = defaultdict(list)

    for row in all_rows:
        gp = row.get("game_points")
        pid = row.get("player_id")
        if pid and gp is not None:
            points_by_player[pid].append(float(gp))

    # Si estamos en dry_run no tenemos los nuevos valores en DB, así que calculamos
    # desde la lista in-memory que acabamos de recalcular
    if dry_run:
        # Reconstruir desde los valores recalculados
        points_by_player_recalc: dict[str, list[float]] = defaultdict(list)
        for row in all_rows:
            role = (row.get("players") or {}).get("role")
            duration_raw = (row.get("games") or {}).get("duration_min")
            pid = row.get("player_id")
            if not role or duration_raw is None or not pid:
                continue
            stats = {
                "kills":            row.get("kills") or 0,
                "deaths":           row.get("deaths") or 0,
                "assists":          row.get("assists") or 0,
                "cs_per_min":       row.get("cs_per_min") or 0,
                "gold_diff_15":     row.get("gold_diff_15"),
                "xp_diff_15":       row.get("xp_diff_15"),
                "dpm":              row.get("dpm") or 0,
                "vision_score":     row.get("vision_score"),
                "turret_damage":    row.get("turret_damage") or 0,
                "objective_steals": row.get("objective_steals") or 0,
                "double_kill":      row.get("double_kill") or False,
                "triple_kill":      row.get("triple_kill") or False,
                "quadra_kill":      row.get("quadra_kill") or False,
                "penta_kill":       row.get("penta_kill") or False,
            }
            pts = calculate_match_points(stats=stats, role=role, game_duration_min=float(duration_raw))
            points_by_player_recalc[pid].append(pts)
        points_by_player = points_by_player_recalc
    else:
        # En modo real, leer los nuevos game_points frescos de DB
        fresh_resp = (
            supabase.table("player_game_stats")
            .select("player_id, game_points")
            .execute()
        )
        points_by_player = defaultdict(list)
        for r in (fresh_resp.data or []):
            if r.get("game_points") is not None:
                points_by_player[r["player_id"]].append(float(r["game_points"]))

    updated_baselines = 0

    for player_id, pts_list in points_by_player.items():
        if not pts_list:
            continue
        avg_baseline = round(sum(pts_list) / len(pts_list), 2)

        if not dry_run:
            supabase.table("players").update(
                {"avg_points_baseline": avg_baseline}
            ).eq("id", player_id).execute()

        updated_baselines += 1

    print(f"[PASO 3] avg_points_baseline actualizados: {updated_baselines} jugadores")

    # ------------------------------------------------------------------
    # Resumen final
    # ------------------------------------------------------------------
    mode = "[DRY-RUN — sin cambios en DB]" if dry_run else "[REAL — cambios aplicados]"
    print(f"\n=== RESUMEN {mode} ===")
    print(f"  player_game_stats procesados : {updated_game_stats} / {total}")
    print(f"  player_game_stats skipped    : {skipped}")
    print(f"  player_series_stats updated  : {updated_series_stats}")
    print(f"  players (baseline) updated   : {updated_baselines}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Recalcula puntos históricos en DB")
    parser.add_argument("--dry-run", action="store_true", help="No escribe en DB, solo muestra el plan")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
