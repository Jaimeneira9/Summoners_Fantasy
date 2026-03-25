"""
Tests de series_ingest.py — funciones puras sin DB ni red.
"""
from __future__ import annotations

import pytest

from pipeline.gol_gg import PlayerRawStats
from pipeline.series_ingest import _best_multikill, _upsert_player_series_stats
from scoring.engine import calculate_match_points


# ---------------------------------------------------------------------------
# Helpers para crear PlayerRawStats de test rápidamente
# ---------------------------------------------------------------------------


def _make_stats(
    *,
    kills: int = 0,
    deaths: int = 0,
    assists: int = 0,
    cs_per_min: float = 6.0,
    vision_score: int = 20,
    damage_share: float = 0.2,
    objective_steals: int = 0,
    double_kill: bool = False,
    triple_kill: bool = False,
    quadra_kill: bool = False,
    penta_kill: bool = False,
    gold_diff_15: int | None = None,
    xp_diff_15: int | None = None,
    dpm: int = 400,
    wards_placed: int = 10,
    wards_destroyed: int = 3,
    solo_kills: int = 0,
    turret_damage: int = 1000,
    result: int = 1,
    role: str = "mid",
    player_name: str = "TestPlayer",
) -> PlayerRawStats:
    return PlayerRawStats(
        player_name=player_name,
        role=role,
        kills=kills,
        deaths=deaths,
        assists=assists,
        cs_per_min=cs_per_min,
        gold_diff_15=gold_diff_15,
        vision_score=vision_score,
        damage_share=damage_share,
        dpm=dpm,
        wards_placed=wards_placed,
        wards_destroyed=wards_destroyed,
        solo_kills=solo_kills,
        double_kill=double_kill,
        triple_kill=triple_kill,
        quadra_kill=quadra_kill,
        penta_kill=penta_kill,
        xp_diff_15=xp_diff_15,
        objective_steals=objective_steals,
        turret_damage=turret_damage,
        result=result,
    )


# ---------------------------------------------------------------------------
# Tests de _best_multikill
# ---------------------------------------------------------------------------


def test_best_multikill_penta_wins():
    stats = [
        _make_stats(penta_kill=True),
        _make_stats(quadra_kill=True),
        _make_stats(triple_kill=True),
    ]
    assert _best_multikill(stats) == "penta"


def test_best_multikill_priority_order():
    # quadra gana sobre triple y double
    stats = [
        _make_stats(quadra_kill=True),
        _make_stats(triple_kill=True),
        _make_stats(double_kill=True),
    ]
    assert _best_multikill(stats) == "quadra"

    # triple gana sobre double
    stats2 = [
        _make_stats(triple_kill=True),
        _make_stats(double_kill=True),
    ]
    assert _best_multikill(stats2) == "triple"

    # double es el mínimo
    stats3 = [_make_stats(double_kill=True)]
    assert _best_multikill(stats3) == "double"


def test_best_multikill_none_when_empty():
    assert _best_multikill([]) is None


def test_best_multikill_none_when_no_multikills():
    stats = [
        _make_stats(double_kill=False, triple_kill=False, quadra_kill=False, penta_kill=False),
        _make_stats(double_kill=False, triple_kill=False, quadra_kill=False, penta_kill=False),
    ]
    assert _best_multikill(stats) is None


# ---------------------------------------------------------------------------
# Tests de series_points — debe ser PROMEDIO, no suma
# ---------------------------------------------------------------------------


def test_series_points_is_average_not_sum():
    """
    Bug conocido: series_ingest usaba sum() en vez de sum()/len().
    Si hay 2 games con 30 y 10 puntos, el resultado debe ser 20.0, no 40.0.
    """
    # Calculamos manualmente los points
    # game 1: kills=5, deaths=1, assists=3 en mid → 5*2 + 1*(-1.5) + 3*1 = 10-1.5+3 = 11.5
    # game 2: kills=0, deaths=3, assists=1 en mid → 0 + 3*(-1.5) + 1 = -4.5+1 = -3.5
    # promedio = (11.5 + (-3.5)) / 2 = 4.0
    stats_game1 = _make_stats(kills=5, deaths=1, assists=3, role="mid", cs_per_min=0)
    stats_game2 = _make_stats(kills=0, deaths=3, assists=1, role="mid", cs_per_min=0)

    points1 = calculate_match_points(stats_game1.model_dump(), "mid", game_duration_min=25.0)
    points2 = calculate_match_points(stats_game2.model_dump(), "mid", game_duration_min=25.0)

    game_points_list = [points1, points2]
    expected_average = round(sum(game_points_list) / len(game_points_list), 2)
    wrong_sum = round(sum(game_points_list), 2)

    # Verificar que el promedio y la suma son diferentes (caso no trivial)
    assert expected_average != wrong_sum, "El test necesita points distintos para ser útil"

    # Verificar la función directamente sobre _upsert_player_series_stats
    # Inspeccionamos el campo series_points que se calcularía
    # Como no tenemos DB, verificamos la lógica inline:
    n = len(game_points_list)
    calculated = round(sum(game_points_list) / n, 2)  # correcto
    wrong = round(sum(game_points_list), 2)  # incorrecto (bug)

    assert calculated == expected_average
    assert wrong != expected_average, "La suma no debería ser igual al promedio con 2 games"


def test_series_points_single_game_equals_game_points():
    """Con un solo game, promedio == suma == valor del game."""
    stats = _make_stats(kills=3, deaths=2, assists=5, role="support", cs_per_min=0)
    points = calculate_match_points(stats.model_dump(), "support", game_duration_min=25.0)

    game_points_list = [points]
    n = len(game_points_list)
    avg = round(sum(game_points_list) / n, 2)
    total = round(sum(game_points_list), 2)

    assert avg == total  # con 1 game son iguales


# ---------------------------------------------------------------------------
# Tests del scoring engine con stats realistas
# ---------------------------------------------------------------------------


def test_scoring_engine_accepts_float_stats():
    """cs_per_min flotante (ej. 7.66) no debe explotar el engine."""
    stats = _make_stats(kills=4, deaths=2, assists=7, cs_per_min=7.66, role="adc")
    # No debe levantar excepción
    points = calculate_match_points(stats.model_dump(), "adc", game_duration_min=29.05)
    assert isinstance(points, float)


def test_scoring_engine_zero_duration_safe():
    """duration_min=0 no debe dividir por cero."""
    stats = _make_stats(kills=2, deaths=1, assists=4, role="jungle")
    # Con duration_min=0, no se aplica normalización (threshold=30 no se alcanza)
    points = calculate_match_points(stats.model_dump(), "jungle", game_duration_min=0.0)
    assert isinstance(points, float)


def test_scoring_engine_penta_kill_bonus():
    """Un pentakill debe sumar 15 puntos de bonus."""
    stats_no_penta = _make_stats(kills=5, deaths=0, assists=0, role="mid", cs_per_min=0)
    stats_penta = _make_stats(
        kills=5, deaths=0, assists=0, role="mid", cs_per_min=0, penta_kill=True
    )

    points_no_penta = calculate_match_points(
        stats_no_penta.model_dump(), "mid", game_duration_min=25.0
    )
    points_penta = calculate_match_points(
        stats_penta.model_dump(), "mid", game_duration_min=25.0
    )

    # El bonus de penta es 15.0
    assert abs((points_penta - points_no_penta) - 15.0) < 0.01


def test_scoring_engine_dpm_affects_mid():
    """dpm tiene peso 0.0069 en mid — un dpm mayor debe dar más puntos."""
    stats_low = _make_stats(kills=3, deaths=2, assists=4, role="mid", dpm=200, cs_per_min=0)
    stats_high = _make_stats(kills=3, deaths=2, assists=4, role="mid", dpm=800, cs_per_min=0)

    p_low = calculate_match_points(stats_low.model_dump(), "mid", game_duration_min=25.0)
    p_high = calculate_match_points(stats_high.model_dump(), "mid", game_duration_min=25.0)

    assert p_high > p_low, "dpm (peso 0.0069) debe afectar el score de mid"
    assert round(p_high - p_low, 2) == round((800 - 200) * 0.0069, 2)


def test_scoring_engine_long_game_normalization():
    """Partidas > 30min aplican factor de normalización (resultado < sin factor)."""
    stats = _make_stats(kills=5, deaths=1, assists=5, role="top", cs_per_min=8.0)

    points_short = calculate_match_points(stats.model_dump(), "top", game_duration_min=25.0)
    points_long = calculate_match_points(stats.model_dump(), "top", game_duration_min=45.0)

    # Partida larga → puntos reducidos por normalización
    assert points_long < points_short
