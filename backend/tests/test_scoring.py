import pytest

from scoring.engine import (
    MULTIKILL_BONUS,
    ROLE_WEIGHTS,
    STATS_TO_NORMALIZE,
    calculate_match_points,
)


def test_mid_basic_stats():
    stats = {"kills": 5, "deaths": 2, "assists": 3, "cs_per_min": 8.5}
    pts = calculate_match_points(stats, "mid", 25.0)
    # kills, deaths, assists se normalizan por game_duration_min
    expected = (5 / 25.0) * 84.0 + (2 / 25.0) * (-50.0) + (3 / 25.0) * 67.0 + 8.5 * 0.5
    assert pts == round(expected, 2)


def test_adc_basic_stats():
    stats = {"kills": 8, "deaths": 1, "assists": 2, "cs_per_min": 10.0, "dpm": 700.0}
    pts = calculate_match_points(stats, "adc", 25.0)
    expected = (8 / 25.0) * 84.0 + (1 / 25.0) * (-50.0) + (2 / 25.0) * 20.0 + 10.0 * 0.75 + 700.0 * 0.0046
    assert pts == round(expected, 2)


def test_support_vision_and_assists():
    stats = {"kills": 1, "deaths": 2, "assists": 10, "vision_score": 50}
    pts = calculate_match_points(stats, "support", 25.0)
    # vision_score también está en STATS_TO_NORMALIZE
    expected = (1 / 25.0) * 50.0 + (2 / 25.0) * (-50.0) + (10 / 25.0) * 83.0 + (50 / 25.0) * 0.80
    assert pts == round(expected, 2)


def test_jungle_objective_steal():
    stats = {"kills": 3, "deaths": 1, "assists": 5, "objective_steals": 2}
    pts = calculate_match_points(stats, "jungle", 25.0)
    # objective_steals NO está en STATS_TO_NORMALIZE — se usa tal cual
    expected = (3 / 25.0) * 67.0 + (1 / 25.0) * (-67.0) + (5 / 25.0) * 83.0 + 2 * 10.0
    assert pts == round(expected, 2)


def test_penta_kill_bonus():
    stats = {"kills": 5, "deaths": 0, "penta_kill": True}
    pts = calculate_match_points(stats, "adc", 25.0)
    # kills normalizados + bonus penta
    expected = (5 / 25.0) * 84.0 + MULTIKILL_BONUS["penta_kill"]
    assert pts == round(expected, 2)


def test_double_kill_bonus():
    stats = {"kills": 2, "deaths": 0, "double_kill": True}
    pts = calculate_match_points(stats, "mid", 25.0)
    expected = (2 / 25.0) * 84.0 + MULTIKILL_BONUS["double_kill"]
    assert pts == round(expected, 2)


def test_normalization_scales_with_duration():
    """Partidas más largas con mismas stats brutas producen menos puntos."""
    stats = {"kills": 5, "deaths": 2, "assists": 3, "cs_per_min": 8.5}
    pts_short = calculate_match_points(stats, "mid", 25.0)
    pts_long = calculate_match_points(stats, "mid", 40.0)
    # En partida larga, kills/assists/deaths normalizados → menos puntos de combate
    assert pts_long < pts_short


def test_normalization_always_applies():
    """La normalización se aplica para cualquier duración > 0."""
    stats = {"kills": 5, "deaths": 2, "assists": 3, "cs_per_min": 8.5}
    pts_10 = calculate_match_points(stats, "mid", 10.0)
    pts_20 = calculate_match_points(stats, "mid", 20.0)
    pts_40 = calculate_match_points(stats, "mid", 40.0)
    # Puntos decrecen a medida que aumenta la duración (stats/min bajan)
    assert pts_10 > pts_20 > pts_40


def test_unknown_stats_ignored():
    stats = {"kills": 3, "unknown_stat": 999}
    pts = calculate_match_points(stats, "top", 25.0)
    assert pts == round((3 / 25.0) * 84.0, 2)


def test_empty_stats_returns_zero():
    pts = calculate_match_points({}, "mid", 25.0)
    assert pts == 0.0


def test_stats_to_normalize_contains_expected_keys():
    """Verifica que STATS_TO_NORMALIZE tiene las stats que se normalizan."""
    assert "kills" in STATS_TO_NORMALIZE
    assert "assists" in STATS_TO_NORMALIZE
    assert "deaths" in STATS_TO_NORMALIZE
    assert "vision_score" in STATS_TO_NORMALIZE
    # cs_per_min y dpm NO se normalizan — ya son relativas
    assert "cs_per_min" not in STATS_TO_NORMALIZE
    assert "dpm" not in STATS_TO_NORMALIZE


# ---------------------------------------------------------------------------
# Edge cases: game_duration_min inválido → fallback a stats brutas
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_duration", [0, None, -1, -30.5])
def test_fallback_to_raw_stats_when_duration_invalid(bad_duration):
    """Si game_duration_min es 0, None o negativo, se usan stats brutas sin dividir."""
    stats = {"kills": 5, "deaths": 2, "assists": 3}
    # Con stats brutas y pesos mid: kills×84 + deaths×(-50) + assists×67
    expected_raw = 5 * 84.0 + 2 * (-50.0) + 3 * 67.0
    pts = calculate_match_points(stats, "mid", bad_duration)
    assert pts == round(expected_raw, 2), (
        f"Con duration={bad_duration!r} se esperaba fallback a stats brutas "
        f"(expected={round(expected_raw, 2)}), pero se obtuvo {pts}"
    )


def test_zero_duration_does_not_raise():
    """game_duration_min=0 no debe lanzar ZeroDivisionError."""
    stats = {"kills": 5, "deaths": 2, "assists": 3}
    try:
        calculate_match_points(stats, "mid", 0)
    except ZeroDivisionError:
        pytest.fail("calculate_match_points lanzó ZeroDivisionError con duration=0")


def test_none_duration_does_not_raise():
    """game_duration_min=None no debe lanzar TypeError ni AttributeError."""
    stats = {"kills": 5, "deaths": 2, "assists": 3}
    try:
        calculate_match_points(stats, "mid", None)
    except (TypeError, AttributeError) as exc:
        pytest.fail(f"calculate_match_points lanzó {type(exc).__name__} con duration=None")


# ---------------------------------------------------------------------------
# Test de regresión del bug crítico: stats brutas ≠ stats normalizadas
#
# Contexto del bug (fixeado 2026-03-25):
#   stat_breakdown multiplicaba kills/assists/deaths BRUTOS por los pesos.
#   Los pesos están calibrados en unidades/min (≈ peso_original × 33.4).
#   Resultado: ~400 pts en vez de ~12 pts por partida típica.
# ---------------------------------------------------------------------------

def test_regression_raw_vs_normalized_points_differ():
    """
    Regresión: stats brutas × peso ≠ stats normalizadas × peso.
    Con stats típicas de mid (kills=5, duration=33.4), el puntaje normalizado
    debe diferir significativamente del puntaje con duration=1 (equivalente a brutas).
    """
    stats = {"kills": 5, "deaths": 2, "assists": 3, "cs_per_min": 8.5}

    # Puntos con normalización correcta (33.4 min = duración media histórica)
    pts_normalized = calculate_match_points(stats, "mid", 33.4)

    # Simulación del bug: usar duration=1 es equivalente a multiplicar stats brutas por el peso
    pts_bug = calculate_match_points(stats, "mid", 1.0)

    # El bug producía ~400 pts; la versión correcta da ~12-25 pts
    assert pts_normalized < pts_bug, (
        "Con duration=33.4 los puntos deben ser menores que con duration=1 "
        "(los pesos están calibrados en /min)"
    )
    assert pts_bug > pts_normalized * 10, (
        f"La diferencia entre bug ({pts_bug}) y correcto ({pts_normalized}) "
        "debe ser de al menos 10x para stats brutas × pesos calibrados/min"
    )


def test_regression_normalized_points_in_realistic_range():
    """
    Partida típica de mid no debe superar ~40 pts con normalización correcta.
    Valores >100 indican que se están usando stats brutas en lugar de stats/min.
    Target del diseño: ~24 pts/partida (±varios pts).
    """
    # Stats representativas de una partida normal de mid
    stats = {
        "kills": 5,
        "deaths": 2,
        "assists": 3,
        "cs_per_min": 8.5,
        "dpm": 650.0,
        "gold_diff_15": 300.0,
        "xp_diff_15": 200.0,
    }
    pts = calculate_match_points(stats, "mid", 33.4)
    assert pts < 40.0, (
        f"Puntos ({pts}) fuera de rango para stats típicas de mid. "
        "Si supera 40 pts, probablemente stats brutas × pesos calibrados/min (el bug)."
    )
    assert pts > 0.0, "Puntos no pueden ser cero con stats reales"


def test_regression_all_roles_realistic_range():
    """
    Todos los roles deben producir puntos en rango realista con stats típicas y duration normal.
    Target de diseño: ~24 pts/partida por rol (rebalanceo v2, 2026-03-25).
    """
    # Stats genéricas razonables para cualquier rol
    stats_by_role = {
        "top":     {"kills": 3, "deaths": 2, "assists": 3, "cs_per_min": 8.0, "dpm": 560.0, "gold_diff_15": 200.0, "xp_diff_15": 150.0, "turret_damage": 5000.0},
        "jungle":  {"kills": 4, "deaths": 2, "assists": 6, "cs_per_min": 5.5, "dpm": 440.0, "gold_diff_15": 100.0, "xp_diff_15": 100.0, "objective_steals": 1},
        "mid":     {"kills": 5, "deaths": 2, "assists": 3, "cs_per_min": 8.5, "dpm": 650.0, "gold_diff_15": 300.0, "xp_diff_15": 200.0},
        "adc":     {"kills": 6, "deaths": 1, "assists": 2, "cs_per_min": 9.5, "dpm": 760.0, "gold_diff_15": 250.0, "xp_diff_15": 80.0},
        "support": {"kills": 1, "deaths": 2, "assists": 9, "cs_per_min": 1.5, "dpm": 190.0, "gold_diff_15": -100.0, "xp_diff_15": -50.0, "vision_score": 60.0},
    }
    for role, stats in stats_by_role.items():
        pts = calculate_match_points(stats, role, 33.4)
        assert pts < 60.0, (
            f"Rol {role}: {pts} pts supera el límite de 60 pts para stats típicas. "
            "Posible uso de stats brutas × pesos calibrados/min (el bug)."
        )
        assert pts > -20.0, f"Rol {role}: {pts} pts negativos excesivos — revisar pesos"


# ---------------------------------------------------------------------------
# Tests adicionales: multikills combinados
# ---------------------------------------------------------------------------

def test_triple_kill_bonus():
    stats = {"kills": 3, "deaths": 0, "triple_kill": True}
    pts = calculate_match_points(stats, "mid", 25.0)
    expected = (3 / 25.0) * 84.0 + MULTIKILL_BONUS["triple_kill"]
    assert pts == round(expected, 2)


def test_quadra_kill_bonus():
    stats = {"kills": 4, "deaths": 0, "quadra_kill": True}
    pts = calculate_match_points(stats, "adc", 25.0)
    expected = (4 / 25.0) * 84.0 + MULTIKILL_BONUS["quadra_kill"]
    assert pts == round(expected, 2)


def test_multiple_multikill_bonuses_stack():
    """Si el mismo jugador tiene double_kill y triple_kill en el mismo juego, ambos suman."""
    stats = {"kills": 5, "deaths": 0, "double_kill": True, "triple_kill": True}
    pts = calculate_match_points(stats, "mid", 25.0)
    expected = (5 / 25.0) * 84.0 + MULTIKILL_BONUS["double_kill"] + MULTIKILL_BONUS["triple_kill"]
    assert pts == round(expected, 2)


def test_multikill_false_does_not_add_bonus():
    """Multikill con valor False no suma bonus."""
    stats = {"kills": 5, "deaths": 0, "penta_kill": False}
    pts_with_false = calculate_match_points(stats, "mid", 25.0)
    pts_without = calculate_match_points({"kills": 5, "deaths": 0}, "mid", 25.0)
    assert pts_with_false == pts_without


# ---------------------------------------------------------------------------
# Tests de roles: top y jungle (cubren stats específicas de esos roles)
# ---------------------------------------------------------------------------

def test_top_turret_damage():
    """turret_damage para top: NO está en STATS_TO_NORMALIZE, se usa directo."""
    stats = {"kills": 3, "deaths": 1, "assists": 2, "turret_damage": 6000.0}
    pts = calculate_match_points(stats, "top", 30.0)
    weights = ROLE_WEIGHTS["top"]
    expected = (
        (3 / 30.0) * weights["kills"]
        + (1 / 30.0) * weights["deaths"]
        + (2 / 30.0) * weights["assists"]
        + 6000.0 * weights["turret_damage"]
    )
    assert pts == round(expected, 2)


def test_jungle_objective_steals_not_normalized():
    """objective_steals no está en STATS_TO_NORMALIZE — se usa directo."""
    stats = {"kills": 3, "deaths": 1, "assists": 5, "objective_steals": 2}
    pts = calculate_match_points(stats, "jungle", 33.4)
    weights = ROLE_WEIGHTS["jungle"]
    expected = (
        (3 / 33.4) * weights["kills"]
        + (1 / 33.4) * weights["deaths"]
        + (5 / 33.4) * weights["assists"]
        + 2 * weights["objective_steals"]
    )
    assert pts == round(expected, 2)


def test_support_objective_steals():
    """Support también tiene objective_steals, valor menor que jungle."""
    stats = {"kills": 0, "deaths": 1, "assists": 8, "objective_steals": 1, "vision_score": 50.0}
    pts = calculate_match_points(stats, "support", 33.4)
    weights = ROLE_WEIGHTS["support"]
    expected = (
        (0 / 33.4) * weights["kills"]
        + (1 / 33.4) * weights["deaths"]
        + (8 / 33.4) * weights["assists"]
        + 1 * weights["objective_steals"]
        + (50.0 / 33.4) * weights["vision_score"]
    )
    assert pts == round(expected, 2)
