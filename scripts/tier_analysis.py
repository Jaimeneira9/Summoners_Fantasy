"""
Análisis comparativo de jugadores por tier.

Comparación 1 — Supports:
  Tier S: Parus (Natus Vincere), Fleshy (Team Vitality)
  Tier B: Labrov (G2), Alvaro (Movistar KOI)

Comparación 2 — Junglas:
  Tier S: SkewMond (G2)
  Tier B: Elyoya (Movistar KOI)

Para cada jugador muestra:
  - Stats promedio por partida: K, D, A, CS/min, GD15, XPD15, Dmg%, Vision, ObjSteals
  - Desglose de puntos por stat (con pesos del engine)
  - Pts/Partida total

Uso:
    cd /home/jaime/LOLFantasy
    python scripts/tier_analysis.py
"""
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

from supabase import create_client
from scoring.engine import calculate_match_points, ROLE_WEIGHTS, Role

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Jugadores a analizar — nombre exacto tal como está en la DB
SUPPORTS = [
    {"name": "Parus",  "tier": "S", "team": "Natus Vincere"},
    {"name": "Fleshy", "tier": "S", "team": "Team Vitality"},
    {"name": "Labrov", "tier": "B", "team": "G2"},
    {"name": "Alvaro", "tier": "B", "team": "Movistar KOI"},
]

JUNGLERS = [
    {"name": "SkewMond", "tier": "S", "team": "G2"},
    {"name": "Elyoya",   "tier": "B", "team": "Movistar KOI"},
]


def fetch_player_stats(player_name: str):
    """Trae todos los registros de player_game_stats para un jugador por nombre."""
    response = (
        supabase
        .table("player_game_stats")
        .select(
            "*, "
            "players!inner(name, role, team), "
            "games(duration_min)"
        )
        .ilike("players.name", player_name)
        .execute()
    )
    return response.data


def safe_avg(values: list):
    filtered = [v for v in values if v is not None]
    if not filtered:
        return None
    return sum(filtered) / len(filtered)


def fmt(val, decimals=2, fallback="-"):
    if val is None:
        return fallback
    return f"{val:.{decimals}f}"


def fmt_pts(val, fallback="-"):
    if val is None:
        return fallback
    sign = "+" if val >= 0 else ""
    return f"{sign}{val:.2f}"


def compute_breakdown(avg_stats: dict, role: Role) -> dict:
    """
    Dado un dict de stats promedio, calcula la contribución de puntos por stat
    usando los pesos del engine (sin normalización de duración, usando 30 min base).
    """
    weights = ROLE_WEIGHTS[role]
    breakdown = {}
    for stat, weight in weights.items():
        val = avg_stats.get(stat) or 0
        breakdown[stat] = round(val * weight, 3)
    return breakdown


def analyze_player(player_info: dict):
    """Devuelve dict con stats promedio, breakdown de pts y total pts/partida."""
    name = player_info["name"]
    records = fetch_player_stats(name)

    if not records:
        return {
            "name": name,
            "tier": player_info["tier"],
            "team": player_info["team"],
            "games": 0,
            "error": f"Sin datos en DB para '{name}'",
        }

    role_raw = records[0].get("players", {}).get("role", "mid") if records else "mid"
    role: Role = role_raw if role_raw in ("top", "jungle", "mid", "adc", "support", "coach") else "mid"
    team_db = records[0].get("players", {}).get("team", player_info["team"]) if records else player_info["team"]

    stat_lists = defaultdict(list)
    points_list = []

    for row in records:
        game_info = row.get("games") or {}
        duration = game_info.get("duration_min") or 30.0

        stats = {
            "kills":            row.get("kills"),
            "deaths":           row.get("deaths"),
            "assists":          row.get("assists"),
            "cs_per_min":       row.get("cs_per_min"),
            "gold_diff_15":     row.get("gold_diff_15"),
            "xp_diff_15":       row.get("xp_diff_15"),
            "damage_share":     row.get("damage_share"),
            "vision_score":     row.get("vision_score"),
            "objective_steals": row.get("objective_steals"),
            "double_kill":      row.get("double_kill"),
            "triple_kill":      row.get("triple_kill"),
            "quadra_kill":      row.get("quadra_kill"),
            "penta_kill":       row.get("penta_kill"),
        }

        pts = calculate_match_points(stats, role, duration)
        points_list.append(pts)

        for stat in ["kills", "deaths", "assists", "cs_per_min", "gold_diff_15",
                     "xp_diff_15", "damage_share", "vision_score", "objective_steals"]:
            stat_lists[stat].append(stats[stat])

    games = len(points_list)
    avg_pts = sum(points_list) / games if games else 0.0

    avg_stats = {stat: safe_avg(vals) for stat, vals in stat_lists.items()}

    # damage_share: se guarda como 0.0–1.0, mostramos como %
    dmg_raw = avg_stats.get("damage_share")
    avg_stats["damage_share_pct"] = (dmg_raw * 100) if dmg_raw is not None else None

    # Para el breakdown usamos damage_share como fracción (así lo recibe el engine)
    breakdown_stats = dict(avg_stats)  # ya tiene damage_share como fracción

    breakdown = compute_breakdown(breakdown_stats, role)

    return {
        "name": name,
        "tier": player_info["tier"],
        "team": team_db,
        "role": role,
        "games": games,
        "avg_k":    avg_stats.get("kills"),
        "avg_d":    avg_stats.get("deaths"),
        "avg_a":    avg_stats.get("assists"),
        "avg_cs":   avg_stats.get("cs_per_min"),
        "avg_gd15": avg_stats.get("gold_diff_15"),
        "avg_xpd15":avg_stats.get("xp_diff_15"),
        "avg_dmg":  avg_stats.get("damage_share_pct"),
        "avg_vis":  avg_stats.get("vision_score"),
        "avg_obj":  avg_stats.get("objective_steals"),
        "breakdown": breakdown,
        "avg_pts":  avg_pts,
    }


def print_section(title: str, players_info: list):
    print()
    print("=" * 80)
    print(f"  {title}")
    print("=" * 80)

    results = [analyze_player(p) for p in players_info]

    for r in results:
        if r.get("error"):
            print(f"\n  [{r['tier']}] {r['name']} ({r['team']}) — {r['error']}")
            continue

        print(f"\n  [{r['tier']}] {r['name']}  |  {r['team']}  |  Rol: {r['role']}  |  Partidas: {r['games']}")
        print(f"  {'─' * 70}")

        # Tabla de stats
        stats_header = f"  {'Stat':<20} {'Promedio/Partida':>18}"
        print(stats_header)
        print(f"  {'─' * 40}")

        stat_labels = [
            ("Kills (K)",          "avg_k",    lambda v: fmt(v, 2)),
            ("Deaths (D)",         "avg_d",    lambda v: fmt(v, 2)),
            ("Assists (A)",        "avg_a",    lambda v: fmt(v, 2)),
            ("CS/min",             "avg_cs",   lambda v: fmt(v, 2)),
            ("GD@15",              "avg_gd15", lambda v: fmt(v, 0) if v is not None else "-"),
            ("XPD@15",             "avg_xpd15",lambda v: fmt(v, 0) if v is not None else "-"),
            ("Damage Share %",     "avg_dmg",  lambda v: fmt(v, 1) + "%" if v is not None else "-"),
            ("Vision Score",       "avg_vis",  lambda v: fmt(v, 1) if v is not None else "-"),
            ("Objective Steals",   "avg_obj",  lambda v: fmt(v, 2) if v is not None else "-"),
        ]

        for label, key, formatter in stat_labels:
            val = r.get(key)
            print(f"  {label:<20} {formatter(val):>18}")

        # Desglose de puntos por stat
        print()
        print(f"  {'── Desglose de puntos por stat ──':}")
        breakdown_labels = {
            "kills":            "kills × peso",
            "deaths":           "deaths × peso",
            "assists":          "assists × peso",
            "cs_per_min":       "cs_per_min × peso",
            "gold_diff_15":     "gold_diff_15 × peso",
            "xp_diff_15":       "xp_diff_15 × peso",
            "damage_share":     "damage_share × peso",
            "vision_score":     "vision_score × peso",
            "objective_steals": "objective_steals × peso",
        }
        weights = ROLE_WEIGHTS[r["role"]]
        total_breakdown = 0.0
        for stat, pts_val in r["breakdown"].items():
            label = breakdown_labels.get(stat, stat)
            weight = weights.get(stat, 0)
            avg_val = r.get(f"avg_{stat.replace('_diff_15', 'd15').replace('cs_per_min', 'cs').replace('damage_share', 'dmg').replace('vision_score', 'vis').replace('objective_steals', 'obj').replace('gold', 'g').replace('xp', 'x')}")

            # Mostrar valor promedio y peso
            # Buscar el valor correcto del promedio para la stat
            raw_avg = None
            if stat == "kills":         raw_avg = r.get("avg_k")
            elif stat == "deaths":      raw_avg = r.get("avg_d")
            elif stat == "assists":     raw_avg = r.get("avg_a")
            elif stat == "cs_per_min":  raw_avg = r.get("avg_cs")
            elif stat == "gold_diff_15":raw_avg = r.get("avg_gd15")
            elif stat == "xp_diff_15":  raw_avg = r.get("avg_xpd15")
            elif stat == "damage_share":
                dmg_pct = r.get("avg_dmg")
                raw_avg = (dmg_pct / 100) if dmg_pct is not None else None
            elif stat == "vision_score": raw_avg = r.get("avg_vis")
            elif stat == "objective_steals": raw_avg = r.get("avg_obj")

            raw_str = fmt(raw_avg, 3) if raw_avg is not None else "-"
            print(f"  {label:<28} {raw_str:>8} × {weight:>6}  =  {fmt_pts(pts_val):>8}")
            total_breakdown += pts_val if pts_val else 0

        print(f"  {'─' * 60}")
        print(f"  {'Subtotal (breakdown)':.<48} {fmt_pts(total_breakdown):>8}")
        print(f"  {'Pts/Partida TOTAL (con multikills + norm)':.<48} {fmt(r['avg_pts'], 2):>8}")

    print()


def main():
    print()
    print("╔══════════════════════════════════════════════════════════════════════════════╗")
    print("║           LOLFantasy — Análisis de Tiers: Stat vs Stat                     ║")
    print("╚══════════════════════════════════════════════════════════════════════════════╝")

    print_section("COMPARACIÓN 1 — SUPPORTS: Tier S vs Tier B", SUPPORTS)
    print_section("COMPARACIÓN 2 — JUNGLAS: Tier S vs Tier B", JUNGLERS)

    print()
    print("Análisis completado.")
    print()


if __name__ == "__main__":
    main()
