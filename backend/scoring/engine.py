"""
Sistema de puntuación por partido.

Pesos distintos por rol (top, jungle, mid, adc, support, coach).
Bonuses: robo de objetivos, multikills, gold_diff@15.
Normalización anti-snowball para partidas largas.
"""
from typing import Literal

Role = Literal["top", "jungle", "mid", "adc", "support", "coach"]

# Pesos base por estadística y rol — valores a calibrar con datos reales
ROLE_WEIGHTS: dict[Role, dict[str, float]] = {
    "top": {
        "kills": 2.0,
        "deaths": -1.5,
        "assists": 4.0,
        "cs_per_min": 0.5,
        "gold_diff_15": 0.015,
        "damage_share": 5.0,
        "xp_diff_15": 0.010,
    },
    "jungle": {
        "kills": 2.5,
        "deaths": -2.0,
        "assists": 3.0,
        "cs_per_min": 0.5,
        "gold_diff_15": 0.010,
        "damage_share": 5.0,
        "objective_steals": 10.0,
        "xp_diff_15": 0.010,
    },
    "mid": {
        "kills": 2.0,
        "deaths": -1.5,
        "assists": 4.0,
        "cs_per_min": 0.5,
        "gold_diff_15": 0.015,
        "damage_share": 10.0,
        "xp_diff_15": 0.010,
    },
    "adc": {
        "kills": 2.0,
        "deaths": -1.5,
        "assists": 0.75,
        "cs_per_min": 0.75,
        "gold_diff_15": 0.010,
        "damage_share": 10.0,
        "xp_diff_15": 0.005,
    },
    "support": {
        "kills": 1.5,
        "deaths": -1.5,
        "assists": 2.0,
        "cs_per_min": 0.25,
        "gold_diff_15": 0.005,
        "damage_share": 2.5,
        "vision_score": 0.1,
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
GAME_LENGTH_NORMALIZATION_THRESHOLD_MIN = 30  # partidas > 30 min aplican factor


def calculate_match_points(stats: dict, role: Role, game_duration_min: float) -> float:
    """Calcula los fantasy points de un jugador para un partido concreto."""
    weights = ROLE_WEIGHTS[role]
    # stats.get() puede devolver None para campos opcionales (gold_diff_15, xp_diff_15).
    # Tratamos None como 0 para evitar TypeError en la multiplicación.
    points = sum((stats.get(stat) or 0) * weight for stat, weight in weights.items())

    # Bonus multikills
    for kill_type, bonus in MULTIKILL_BONUS.items():
        if stats.get(kill_type, False):
            points += bonus

    # Normalización anti-snowball: reduce ventaja de partidas muy largas
    if game_duration_min > GAME_LENGTH_NORMALIZATION_THRESHOLD_MIN:
        excess = game_duration_min - GAME_LENGTH_NORMALIZATION_THRESHOLD_MIN
        points = points / (1 + excess * 0.01)

    return round(points, 2)
