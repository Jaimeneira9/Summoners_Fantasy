"""
Script para calcular tiers mixtos: 70% stats (Pts/Partida normalizado) + 30% tier manual.

Algoritmo:
1. Trae Pts/Partida desde Supabase usando calculate_match_points del engine
2. Normaliza por rol (min-max 1-5): mejor del rol = 5.0, peor = 1.0
3. Convierte tier manual a número: S=5, A=4, B=3, C=2, D=1
4. Mixed score = 0.7 * stats_score + 0.3 * manual_tier_score
5. Asigna tiers finales por rol (2 jugadores por tier): rank 1-2=S, 3-4=A, 5-6=B, 7-8=C, 9-10=D
6. Aplica regla de floor: un jugador no puede caer más de un tier respecto a su tier manual
   (Manual S → mínimo A, Manual A → mínimo B, Manual B → mínimo C, Manual C → mínimo D)

Uso:
    cd /home/jaime/LOLFantasy
    python scripts/mixed_tiers.py
"""
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

from supabase import create_client
from scoring.engine import calculate_match_points, Role

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------------------------------------------------------------------
# Tiers manuales del usuario
# Clave: nombre normalizado (lowercase), valor: tier S/A/B/C/D
# ---------------------------------------------------------------------------
MANUAL_TIERS: dict[str, str] = {
    # --- JUNGLE ---
    "skewmond": "S", "yike": "S", "elyoya": "S",
    "rhilech": "A", "lyncas": "A", "isma": "A",
    "sheo": "B", "boukada": "B", "razork": "B",
    "skeanz": "C",
    # --- TOP ---
    "naak nako": "S", "canna": "S", "brokenblade": "S",
    "myrwn": "A", "maynter": "A", "lot": "A",
    "tracyn": "B", "wunder": "B", "rooster": "B",
    "empyros": "C",
    # --- MID ---
    "caps": "S", "kyeahoo": "S", "jojopyun": "S",
    "poby": "A", "humanoid": "A", "serin": "A",
    "jackies": "B", "nuc": "B", "lider": "B",
    "vladi": "C",
    # --- ADC ---
    "caliste": "S", "hans sama": "S", "noah": "S",
    "samd": "A", "carzzy": "A", "ice": "A", "supa": "A",
    "paduck": "B", "jopa": "B", "upset": "B",
    # --- SUPPORT ---
    "busio": "S", "labrov": "S", "alvaro": "S",
    "jun": "A", "lospa": "A", "fleshy": "A", "parus": "A",
    "trymbi": "B",
    "mikyx": "C",
}

TIER_TO_NUM: dict[str, float] = {"S": 5.0, "A": 4.0, "B": 3.0, "C": 2.0, "D": 1.0}
NUM_TO_TIER: dict[int, str] = {1: "S", 2: "A", 3: "B", 4: "C", 5: "D"}

# Floor: tier manual → peor tier permitido (un tier de caída máxima)
MANUAL_FLOOR: dict[str, str] = {"S": "A", "A": "B", "B": "C", "C": "D", "D": "D"}

TIER_ORDER: dict[str, int] = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4}


def apply_floor(assigned_tier: str, manual_tier: str) -> tuple[str, bool]:
    """
    Aplica la regla de floor: el tier final no puede ser peor que (manual - 1).
    Devuelve (tier_final, floor_applied).
    """
    floor_tier = MANUAL_FLOOR.get(manual_tier, "D")
    # Si el tier asignado es peor (número mayor) que el floor → corregir
    if TIER_ORDER[assigned_tier] > TIER_ORDER[floor_tier]:
        return floor_tier, True
    return assigned_tier, False


def fetch_all_stats():
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
    filtered = [v for v in values if v is not None]
    if not filtered:
        return None
    return sum(filtered) / len(filtered)


def get_manual_tier(name: str) -> str:
    """Busca el tier manual por nombre (case-insensitive). Default B si no está."""
    return MANUAL_TIERS.get(name.lower().strip(), "B")


def normalize_minmax(value: float, min_val: float, max_val: float) -> float:
    """Min-max normalization al rango 1-5."""
    if max_val == min_val:
        return 3.0  # todos iguales → punto medio
    return 1.0 + 4.0 * (value - min_val) / (max_val - min_val)


def rank_to_tier(rank: int) -> str:
    """
    Rank 1-2 → S, 3-4 → A, 5-6 → B, 7-8 → C, 9-10 → D
    (2 jugadores por tier, 5 tiers = 10 jugadores max por rol)
    """
    tier_index = (rank - 1) // 2 + 1  # 1..5
    return NUM_TO_TIER.get(min(tier_index, 5), "D")


def main():
    print("Conectando a Supabase y trayendo datos...")
    records = fetch_all_stats()
    print(f"Total de registros obtenidos: {len(records)}")

    if not records:
        print("No hay datos en player_game_stats.")
        return

    # Acumular puntos por jugador
    player_data: dict[str, dict] = defaultdict(lambda: {
        "name": "", "role": "", "team": "", "points": [],
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

        game_info = row.get("games") or {}
        game_duration_min = game_info.get("duration_min") or 30.0

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
            "picks_correct":    row.get("picks_correct"),
            "bans_effective":   row.get("bans_effective"),
        }

        pts = calculate_match_points(stats, role, game_duration_min)

        d = player_data[player_id]
        d["name"] = name
        d["role"] = role
        d["team"] = team
        d["points"].append(pts)

    # Calcular avg_pts por jugador
    players: list[dict] = []
    for player_id, d in player_data.items():
        games = len(d["points"])
        avg_pts = sum(d["points"]) / games if games > 0 else 0.0
        manual_tier_str = get_manual_tier(d["name"])
        manual_tier_num = TIER_TO_NUM[manual_tier_str]
        players.append({
            "name":             d["name"],
            "role":             d["role"],
            "team":             d["team"],
            "games":            games,
            "avg_pts":          avg_pts,
            "manual_tier":      manual_tier_str,
            "manual_tier_num":  manual_tier_num,
        })

    # Filtrar coaches
    players = [p for p in players if p["role"] != "coach"]

    # Normalizar stats por rol y calcular mixed score
    roles = ["top", "jungle", "mid", "adc", "support"]
    final_results: list[dict] = []

    for role in roles:
        role_players = [p for p in players if p["role"] == role]
        if not role_players:
            continue

        pts_values = [p["avg_pts"] for p in role_players]
        min_pts = min(pts_values)
        max_pts = max(pts_values)

        for p in role_players:
            stats_score = normalize_minmax(p["avg_pts"], min_pts, max_pts)
            mixed = 0.7 * stats_score + 0.3 * p["manual_tier_num"]
            p["stats_score"] = stats_score
            p["mixed_score"] = mixed

        # Ordenar por mixed_score descendente y asignar tier final
        role_players.sort(key=lambda x: x["mixed_score"], reverse=True)
        for rank, p in enumerate(role_players, start=1):
            raw_tier = rank_to_tier(rank)
            final_tier, floor_applied = apply_floor(raw_tier, p["manual_tier"])
            p["raw_tier"] = raw_tier
            p["final_tier"] = final_tier
            p["floor_applied"] = floor_applied
            p["rank"] = rank
            final_results.append(p)

    # Ordenar resultado final: por tier (S→D) y dentro por rol
    ROLE_ORDER = {"top": 0, "jungle": 1, "mid": 2, "adc": 3, "support": 4}
    final_results.sort(key=lambda x: (TIER_ORDER[x["final_tier"]], ROLE_ORDER.get(x["role"], 9), -x["mixed_score"]))

    # --- Imprimir tabla ---
    try:
        from tabulate import tabulate

        headers = [
            "Tier", "Jugador", "Rol", "Equipo", "Partidas",
            "Pts/P", "Tier Manual", "Stats Score", "Mixed Score", "Tier Raw", "Floor Applied"
        ]
        rows = []
        for p in final_results:
            rows.append([
                p["final_tier"],
                p["name"],
                p["role"],
                p["team"],
                p["games"],
                f"{p['avg_pts']:.2f}",
                p["manual_tier"],
                f"{p['stats_score']:.3f}",
                f"{p['mixed_score']:.3f}",
                p["raw_tier"],
                "SI" if p["floor_applied"] else "-",
            ])

        print()
        print(tabulate(rows, headers=headers, tablefmt="rounded_outline"))

    except ImportError:
        # Formateo manual
        col = {"tier": 5, "name": 22, "role": 8, "team": 18, "games": 8,
               "pts": 8, "man": 11, "stats": 11, "mixed": 11}
        header = (
            f"{'Tier':<{col['tier']}} "
            f"{'Jugador':<{col['name']}} "
            f"{'Rol':<{col['role']}} "
            f"{'Equipo':<{col['team']}} "
            f"{'Partidas':>{col['games']}} "
            f"{'Pts/P':>{col['pts']}} "
            f"{'Tier Manual':>{col['man']}} "
            f"{'Stats Score':>{col['stats']}} "
            f"{'Mixed Score':>{col['mixed']}}"
        )
        sep = "-" * len(header)
        print()
        print(header)
        print(sep)
        prev_tier = None
        for p in final_results:
            if prev_tier and p["final_tier"] != prev_tier:
                print(sep)
            prev_tier = p["final_tier"]
            print(
                f"{p['final_tier']:<{col['tier']}} "
                f"{p['name']:<{col['name']}} "
                f"{p['role']:<{col['role']}} "
                f"{p['team']:<{col['team']}} "
                f"{p['games']:>{col['games']}} "
                f"{p['avg_pts']:>{col['pts']}.2f} "
                f"{p['manual_tier']:>{col['man']}} "
                f"{p['stats_score']:>{col['stats']}.3f} "
                f"{p['mixed_score']:>{col['mixed']}.3f}"
            )

    print()
    print(f"Total jugadores procesados: {len(final_results)}")


if __name__ == "__main__":
    main()
