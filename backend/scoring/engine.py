"""
Sistema de puntuación por partido.

Pesos distintos por rol (top, jungle, mid, adc, support, coach).
Bonuses: robo de objetivos, multikills, gold_diff@15.

Normalización por minuto: kills, assists, deaths y vision_score se dividen
por game_duration_min antes de aplicar los pesos, eliminando la inflación
de stats en partidas largas. Los pesos están calibrados en unidades "por minuto"
(≈ peso_original × 33.4, donde 33.4 es la duración media histórica en min).

Rebalanceo 2026-03-25 v2: target ~24 pts/partida por rol (±1.2 pts entre roles).
  Proyectado: Top ~24.0 | Jungle ~23.9 | Mid ~25.0 | ADC ~25.1 | Support ~24.1
  Cambios vs v1:
  - damage_share → dpm (pesos calibrados para misma contribución media)
  - Mid: kills 67→84
  - ADC: kills 67→84, assists 40→20
  - Jungle: kills 84→67, assists 67→83
  - Top: turret_damage 0.00043→0.0007 (+~1.8 pts — diferenciador split-push)
"""
from typing import Literal

Role = Literal["top", "jungle", "mid", "adc", "support", "coach"]

# Stats que se normalizan por minuto antes de multiplicar por el peso.
# El resto (cs_per_min, dpm, gold_diff_15, xp_diff_15) ya son métricas
# relativas o absolutas por minuto y NO se tocan.
STATS_TO_NORMALIZE = {"kills", "assists", "deaths", "vision_score"}

# Pesos calibrados para stats/min (kills/min, assists/min, deaths/min, vision/min).
# dpm, cs_per_min, gold_diff_15 y xp_diff_15 se usan tal cual.
ROLE_WEIGHTS: dict[Role, dict[str, float]] = {
    "top": {
        "kills": 84.0,        # 2.5 × ~33.4
        "deaths": -50.0,      # -1.5 × ~33.4
        "assists": 67.0,      # 2.0 × ~33.4
        "cs_per_min": 0.5,
        "gold_diff_15": 0.015,
        "dpm": 0.0046,        # calibrado: avg top 563.8 dpm → ~2.59 pts (= damage_share anterior)
        "turret_damage": 0.0007,  # subido 0.00043→0.0007 — diferenciador top: avg 6913 → ~4.8 pts
        "xp_diff_15": 0.010,
    },
    "jungle": {
        "kills": 67.0,        # bajado 84→67 (2.0 × ~33.4)
        "deaths": -67.0,      # -2.0 × ~33.4
        "assists": 83.0,      # subido 67→83 (2.5 × ~33.4)
        "cs_per_min": 0.5,
        "gold_diff_15": 0.010,
        "dpm": 0.0019,        # calibrado: avg jg 446.3 dpm → ~0.85 pts
        "objective_steals": 10.0,
        "xp_diff_15": 0.010,
    },
    "mid": {
        "kills": 84.0,        # subido 67→84 (2.5 × ~33.4)
        "deaths": -50.0,      # -1.5 × ~33.4
        "assists": 67.0,      # 2.0 × ~33.4
        "cs_per_min": 0.5,
        "gold_diff_15": 0.015,
        "dpm": 0.0069,        # calibrado: avg mid 650.9 dpm → ~4.49 pts
        "xp_diff_15": 0.010,
    },
    "adc": {
        "kills": 84.0,        # subido 67→84 (2.5 × ~33.4)
        "deaths": -50.0,      # -1.5 × ~33.4
        "assists": 20.0,      # bajado 40→20 (~0.6 × ~33.4) — ADC puntúa por kills y daño
        "cs_per_min": 0.75,
        "gold_diff_15": 0.010,
        "dpm": 0.0046,        # calibrado: avg adc 766.1 dpm → ~3.52 pts
        "xp_diff_15": 0.005,
    },
    "support": {
        "kills": 50.0,        # 1.5 × ~33.2
        "deaths": -50.0,      # -1.5 × ~33.2
        "assists": 83.0,      # 2.5 × ~33.2
        "cs_per_min": 0.25,
        "gold_diff_15": 0.005,
        "dpm": 0.0010,        # calibrado: avg supp 193.4 dpm → ~0.19 pts
        "vision_score": 0.80, # 0.024 × ~33.2
        "objective_steals": 3.0,
        "xp_diff_15": 0.0025,
    },
    "coach": {
        # Puntuación basada en pick/ban (fuente: Leaguepedia) — WIP
        "picks_correct": 3.0,
        "bans_effective": 2.0,
    },
}

MULTIKILL_BONUS = {"double_kill": 2.0, "triple_kill": 5.0, "quadra_kill": 8.0, "penta_kill": 15.0}


def calculate_match_points(stats: dict, role: Role, game_duration_min: float) -> float:
    """Calcula los fantasy points de un jugador para un partido concreto.

    Las stats en STATS_TO_NORMALIZE (kills, assists, deaths, vision_score) se
    dividen por game_duration_min antes de aplicar los pesos, de modo que la
    puntuación es independiente de la duración del partido.

    Si game_duration_min es None, 0 o negativo se omite la normalización para
    evitar división por cero (fallback a stats brutas).
    """
    weights = ROLE_WEIGHTS[role]

    can_normalize = game_duration_min is not None and game_duration_min > 0

    points = 0.0
    for stat, weight in weights.items():
        raw = stats.get(stat) or 0
        if can_normalize and stat in STATS_TO_NORMALIZE:
            value = raw / game_duration_min
        else:
            value = raw
        points += value * weight

    # Bonus multikills
    for kill_type, bonus in MULTIKILL_BONUS.items():
        if stats.get(kill_type, False):
            points += bonus

    return round(points, 2)
