from scoring.engine import (
    GAME_LENGTH_NORMALIZATION_THRESHOLD_MIN,
    MULTIKILL_BONUS,
    calculate_match_points,
)


def test_mid_basic_stats():
    stats = {"kills": 5, "deaths": 2, "assists": 3, "cs_per_min": 8.5}
    pts = calculate_match_points(stats, "mid", 25.0)
    expected = 5 * 2.0 + 2 * (-1.5) + 3 * 1.0 + 8.5 * 0.5
    assert pts == round(expected, 2)


def test_adc_basic_stats():
    stats = {"kills": 8, "deaths": 1, "assists": 2, "cs_per_min": 10.0, "damage_share": 0.35}
    pts = calculate_match_points(stats, "adc", 25.0)
    expected = 8 * 2.0 + 1 * (-1.5) + 2 * 0.75 + 10.0 * 0.6 + 0.35 * 10.0
    assert pts == round(expected, 2)


def test_support_vision_and_assists():
    stats = {"kills": 1, "deaths": 2, "assists": 10, "vision_score": 50}
    pts = calculate_match_points(stats, "support", 25.0)
    expected = 1 * 1.5 + 2 * (-1.0) + 10 * 2.0 + 50 * 0.1
    assert pts == round(expected, 2)


def test_jungle_objective_steal():
    stats = {"kills": 3, "deaths": 1, "assists": 5, "objective_steals": 2}
    pts = calculate_match_points(stats, "jungle", 25.0)
    expected = 3 * 2.0 + 1 * (-1.5) + 5 * 1.5 + 2 * 5.0
    assert pts == round(expected, 2)


def test_penta_kill_bonus():
    stats = {"kills": 5, "deaths": 0, "penta_kill": True}
    pts = calculate_match_points(stats, "adc", 25.0)
    # kills: 5*2.0=10, penta bonus: 15
    assert pts == round(10.0 + MULTIKILL_BONUS["penta_kill"], 2)


def test_double_kill_bonus():
    stats = {"kills": 2, "deaths": 0, "double_kill": True}
    pts = calculate_match_points(stats, "mid", 25.0)
    assert pts == round(2 * 2.0 + MULTIKILL_BONUS["double_kill"], 2)


def test_normalization_applies_above_threshold():
    stats = {"kills": 5, "deaths": 2, "assists": 3, "cs_per_min": 8.5}
    pts_short = calculate_match_points(stats, "mid", GAME_LENGTH_NORMALIZATION_THRESHOLD_MIN - 1)
    pts_long = calculate_match_points(stats, "mid", GAME_LENGTH_NORMALIZATION_THRESHOLD_MIN + 10)
    assert pts_long < pts_short


def test_normalization_not_applied_below_threshold():
    stats = {"kills": 5, "deaths": 2, "assists": 3, "cs_per_min": 8.5}
    # Exactly at threshold — no normalization
    pts = calculate_match_points(stats, "mid", float(GAME_LENGTH_NORMALIZATION_THRESHOLD_MIN))
    expected = 5 * 2.0 + 2 * (-1.5) + 3 * 1.0 + 8.5 * 0.5
    assert pts == round(expected, 2)


def test_unknown_stats_ignored():
    stats = {"kills": 3, "unknown_stat": 999}
    pts = calculate_match_points(stats, "top", 25.0)
    assert pts == round(3 * 2.0, 2)


def test_empty_stats_returns_zero():
    pts = calculate_match_points({}, "mid", 25.0)
    assert pts == 0.0
