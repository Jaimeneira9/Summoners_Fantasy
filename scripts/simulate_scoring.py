"""
Script temporal para simular ranking de jugadores con los pesos actualizados del engine.

Genera una tabla detallada con promedios de stats por partida y Pts/Partida calculados
con calculate_match_points del engine de scoring.

Uso:
    cd /home/jaime/LOLFantasy
    python scripts/simulate_scoring.py
"""
import os
import sys
from collections import defaultdict

# Aseguramos que el backend esté en el path para importar el engine
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from dotenv import load_dotenv

# Cargar variables de entorno desde backend/.env
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

from supabase import create_client
from scoring.engine import calculate_match_points, Role

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def fetch_all_stats():
    """Trae todos los registros de player_game_stats con join a players y games."""
    response = (
        supabase
        .table("player_game_stats")
        .select(
            "*, "
            "players(name, role, team), "
            "games(duration_min)"
        )
        .execute()
    )
    return response.data


def safe_avg(values: list) -> float | None:
    """Promedio de una lista, ignorando None. Devuelve None si todos son None."""
    filtered = [v for v in values if v is not None]
    if not filtered:
        return None
    return sum(filtered) / len(filtered)


def fmt_float(val: float | None, decimals: int = 2, fallback: str = "-") -> str:
    if val is None:
        return fallback
    return f"{val:.{decimals}f}"


def fmt_int(val: float | None, fallback: str = "-") -> str:
    if val is None:
        return fallback
    return str(int(round(val)))


def main():
    print("Conectando a Supabase y trayendo datos...")
    records = fetch_all_stats()
    print(f"Total de registros obtenidos: {len(records)}")

    if not records:
        print("No hay datos en player_game_stats.")
        return

    # Acumuladores por jugador
    # {player_id: {name, role, team, listas de stats}}
    player_data: dict[str, dict] = defaultdict(lambda: {
        "name": "",
        "role": "",
        "team": "",
        "kills": [],
        "deaths": [],
        "assists": [],
        "cs_per_min": [],
        "gold_diff_15": [],
        "xp_diff_15": [],
        "damage_share": [],
        "vision_score": [],
        "objective_steals": [],
        "points": [],
    })

    for row in records:
        player_info = row.get("players")
        if not player_info:
            continue

        player_id = row.get("player_id") or row.get("id", "unknown")
        name = player_info.get("name", "Unknown")
        role: Role = player_info.get("role", "mid")
        team = player_info.get("team", "?")

        if role not in ("top", "jungle", "mid", "adc", "support", "coach"):
            role = "mid"

        # duration_min viene de games(duration_min)
        game_info = row.get("games") or {}
        game_duration_min = game_info.get("duration_min") or 30.0

        stats = {
            "kills": row.get("kills"),
            "deaths": row.get("deaths"),
            "assists": row.get("assists"),
            "cs_per_min": row.get("cs_per_min"),
            "gold_diff_15": row.get("gold_diff_15"),
            "xp_diff_15": row.get("xp_diff_15"),
            "damage_share": row.get("damage_share"),
            "vision_score": row.get("vision_score"),
            "objective_steals": row.get("objective_steals"),
            "double_kill": row.get("double_kill"),
            "triple_kill": row.get("triple_kill"),
            "quadra_kill": row.get("quadra_kill"),
            "penta_kill": row.get("penta_kill"),
            "picks_correct": row.get("picks_correct"),
            "bans_effective": row.get("bans_effective"),
        }

        pts = calculate_match_points(stats, role, game_duration_min)

        d = player_data[player_id]
        d["name"] = name
        d["role"] = role
        d["team"] = team
        d["kills"].append(stats["kills"])
        d["deaths"].append(stats["deaths"])
        d["assists"].append(stats["assists"])
        d["cs_per_min"].append(stats["cs_per_min"])
        d["gold_diff_15"].append(stats["gold_diff_15"])
        d["xp_diff_15"].append(stats["xp_diff_15"])
        d["damage_share"].append(stats["damage_share"])
        d["vision_score"].append(stats["vision_score"])
        d["objective_steals"].append(stats["objective_steals"])
        d["points"].append(pts)

    # Calcular promedios por jugador
    results = []
    for player_id, d in player_data.items():
        games = len(d["points"])
        avg_pts = sum(d["points"]) / games if games > 0 else 0.0

        # damage_share se guarda como fracción (0.0–1.0), mostramos como porcentaje
        raw_dmg = safe_avg(d["damage_share"])
        avg_dmg_pct = (raw_dmg * 100) if raw_dmg is not None else None

        results.append({
            "name": d["name"],
            "role": d["role"],
            "team": d["team"],
            "games": games,
            "avg_k": safe_avg(d["kills"]),
            "avg_d": safe_avg(d["deaths"]),
            "avg_a": safe_avg(d["assists"]),
            "avg_cs": safe_avg(d["cs_per_min"]),
            "avg_gd15": safe_avg(d["gold_diff_15"]),
            "avg_xpd15": safe_avg(d["xp_diff_15"]),
            "avg_dmg": avg_dmg_pct,
            "avg_vis": safe_avg(d["vision_score"]),
            "avg_obj": safe_avg(d["objective_steals"]),
            "avg_pts": avg_pts,
        })

    # Ordenar por Pts/Partida descendente
    results.sort(key=lambda x: x["avg_pts"], reverse=True)

    # --- Tabla con tabulate si está disponible, sino formateo manual ---
    try:
        from tabulate import tabulate

        headers = [
            "Jugador", "Rol", "Equipo", "Partidas",
            "K", "D", "A", "CS/m",
            "GD15", "XPD15", "Dmg%", "Vision",
            "ObjSteals", "Pts/Part"
        ]
        rows = []
        for r in results:
            rows.append([
                r["name"],
                r["role"],
                r["team"],
                r["games"],
                fmt_float(r["avg_k"], 1),
                fmt_float(r["avg_d"], 1),
                fmt_float(r["avg_a"], 1),
                fmt_float(r["avg_cs"], 1),
                fmt_int(r["avg_gd15"]),
                fmt_int(r["avg_xpd15"]),
                fmt_float(r["avg_dmg"], 1),
                fmt_float(r["avg_vis"], 1),
                fmt_float(r["avg_obj"], 2),
                fmt_float(r["avg_pts"], 2),
            ])

        print()
        print(tabulate(rows, headers=headers, tablefmt="rounded_outline"))

    except ImportError:
        # Formateo manual con f-strings
        col_widths = {
            "name": 22, "role": 8, "team": 16, "games": 8,
            "k": 5, "d": 5, "a": 5, "cs": 6,
            "gd15": 7, "xpd15": 7, "dmg": 7, "vis": 7,
            "obj": 10, "pts": 9,
        }
        header = (
            f"{'Jugador':<{col_widths['name']}} "
            f"{'Rol':<{col_widths['role']}} "
            f"{'Equipo':<{col_widths['team']}} "
            f"{'Partidas':>{col_widths['games']}} "
            f"{'K':>{col_widths['k']}} "
            f"{'D':>{col_widths['d']}} "
            f"{'A':>{col_widths['a']}} "
            f"{'CS/m':>{col_widths['cs']}} "
            f"{'GD15':>{col_widths['gd15']}} "
            f"{'XPD15':>{col_widths['xpd15']}} "
            f"{'Dmg%':>{col_widths['dmg']}} "
            f"{'Vision':>{col_widths['vis']}} "
            f"{'ObjSteals':>{col_widths['obj']}} "
            f"{'Pts/Part':>{col_widths['pts']}}"
        )
        sep = "-" * len(header)
        print()
        print(header)
        print(sep)
        for r in results:
            print(
                f"{r['name']:<{col_widths['name']}} "
                f"{r['role']:<{col_widths['role']}} "
                f"{r['team']:<{col_widths['team']}} "
                f"{r['games']:>{col_widths['games']}} "
                f"{fmt_float(r['avg_k'], 1):>{col_widths['k']}} "
                f"{fmt_float(r['avg_d'], 1):>{col_widths['d']}} "
                f"{fmt_float(r['avg_a'], 1):>{col_widths['a']}} "
                f"{fmt_float(r['avg_cs'], 1):>{col_widths['cs']}} "
                f"{fmt_int(r['avg_gd15']):>{col_widths['gd15']}} "
                f"{fmt_int(r['avg_xpd15']):>{col_widths['xpd15']}} "
                f"{fmt_float(r['avg_dmg'], 1):>{col_widths['dmg']}} "
                f"{fmt_float(r['avg_vis'], 1):>{col_widths['vis']}} "
                f"{fmt_float(r['avg_obj'], 2):>{col_widths['obj']}} "
                f"{fmt_float(r['avg_pts'], 2):>{col_widths['pts']}}"
            )

    print()
    print(f"Total jugadores: {len(results)}")


if __name__ == "__main__":
    main()
