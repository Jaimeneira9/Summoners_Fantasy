from scoring.engine import (
    MULTIKILL_BONUS,
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
