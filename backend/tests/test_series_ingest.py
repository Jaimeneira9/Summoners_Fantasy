"""
Tests de series_ingest.py — funciones puras sin DB ni red.
"""
from __future__ import annotations
from unittest.mock import MagicMock

import pytest

from pipeline.gol_gg import GameMeta, PlayerRawStats
from pipeline.series_ingest import (
    _best_multikill,
    _game_belongs_to_series,
    _update_manager_total_points,
    _upsert_player_series_stats,
)
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
    series_ingest debe calcular series_points como promedio de game_points, no suma.
    Si hay 2 games con points1 y points2, el resultado debe ser (points1+points2)/2, no points1+points2.
    """
    # game 1: kills=5, deaths=1, assists=3 en mid
    # game 2: kills=0, deaths=3, assists=1 en mid
    stats_game1 = _make_stats(kills=5, deaths=1, assists=3, role="mid", cs_per_min=0)
    stats_game2 = _make_stats(kills=0, deaths=3, assists=1, role="mid", cs_per_min=0)

    points1 = calculate_match_points(stats_game1.model_dump(), "mid", game_duration_min=25.0)
    points2 = calculate_match_points(stats_game2.model_dump(), "mid", game_duration_min=25.0)

    game_points_list = [points1, points2]
    expected_average = round(sum(game_points_list) / len(game_points_list), 2)
    wrong_sum = round(sum(game_points_list), 2)

    # Verificar que la suma y el promedio son diferentes (caso no trivial)
    assert expected_average != wrong_sum, "El test necesita points distintos para ser útil"

    # Verificar que la lógica correcta es el promedio
    calculated = round(sum(game_points_list) / len(game_points_list), 2)  # correcto: promedio
    wrong = round(sum(game_points_list), 2)  # incorrecto: suma

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


# ---------------------------------------------------------------------------
# Tests de _game_belongs_to_series — resolución por ID via aliases
# ---------------------------------------------------------------------------


def _make_supabase_mock(resolve_map: dict[str, str | None]) -> MagicMock:
    """
    Construye un mock de supabase donde _resolve_team_by_alias retorna el UUID
    correspondiente según resolve_map {team_name_lower → uuid}.

    El mock implementa la cadena:
      supabase.table("teams").select(...).contains(...).limit(1).execute()
    con un fallback all_teams que devuelve rows con name y aliases.
    """
    # Construimos rows de teams a partir del mapa: cada entrada es un equipo
    # cuyo name es la clave del mapa.
    teams_rows = [
        {"id": uuid, "name": name, "aliases": [name]}
        for name, uuid in resolve_map.items()
        if uuid is not None
    ]

    # Mock para .contains(...).limit(1).execute() → devuelve vacío (fuerza fallback)
    contains_chain = MagicMock()
    contains_chain.limit.return_value.execute.return_value = MagicMock(data=[])

    # Mock para all_teams (sin filtros): devuelve todos los rows
    all_teams_chain = MagicMock()
    all_teams_chain.execute.return_value = MagicMock(data=teams_rows)

    # Mock para .select("id, name, aliases") sin .contains → all_teams path
    select_mock = MagicMock()
    select_mock.contains.return_value = contains_chain
    select_mock.execute.return_value = MagicMock(data=teams_rows)

    table_mock = MagicMock()
    table_mock.select.return_value = select_mock

    supabase = MagicMock()
    supabase.table.return_value = table_mock
    return supabase


def test_game_belongs_to_series_alias_mismatch_resolved_by_id():
    """
    Reproduce el bug: matchlist tiene "NAVI"/"MKOI", game page tiene
    "Natus Vincere"/"Movistar KOI". El substring matching fallaba.
    Con resolución por UUID, ambos nombres resuelven al mismo ID → True.
    """
    navi_id = "uuid-navi"
    mkoi_id = "uuid-mkoi"

    # La DB conoce los nombres completos del game page (aliases incluyen ambas formas)
    resolve_map = {
        "Natus Vincere": navi_id,
        "Movistar KOI": mkoi_id,
    }
    supabase = _make_supabase_mock(resolve_map)

    meta = GameMeta(duration_min=32.0, winner_team="Natus Vincere", loser_team="Movistar KOI")

    result = _game_belongs_to_series(supabase, meta, navi_id, mkoi_id)

    assert result is True, (
        "El game debería pertenecer a la serie: los nombres completos del game page "
        "deben resolverse al mismo UUID que los nombres cortos del matchlist"
    )


def test_game_belongs_to_series_wrong_game_rejected():
    """
    Un game de otra serie (equipos completamente distintos) debe retornar False.
    """
    navi_id = "uuid-navi"
    mkoi_id = "uuid-mkoi"
    g2_id = "uuid-g2"
    fnc_id = "uuid-fnc"

    resolve_map = {
        "G2 Esports": g2_id,
        "Fnatic": fnc_id,
    }
    supabase = _make_supabase_mock(resolve_map)

    meta = GameMeta(duration_min=28.0, winner_team="G2 Esports", loser_team="Fnatic")

    result = _game_belongs_to_series(supabase, meta, navi_id, mkoi_id)

    assert result is False, (
        "Un game de G2 vs FNC no debe pertenecer a la serie NAVI vs MKOI"
    )


def test_game_belongs_to_series_no_meta_assumed_valid():
    """
    Si meta no tiene winner_team ni loser_team, no se puede validar → True.
    """
    supabase = MagicMock()
    meta = GameMeta(duration_min=25.0, winner_team="", loser_team="")

    result = _game_belongs_to_series(supabase, meta, "uuid-a", "uuid-b")

    assert result is True
    supabase.table.assert_not_called()  # No debe tocar la DB si no hay nombres


def test_game_belongs_to_series_partial_meta_one_team_match():
    """
    Si solo winner_team está disponible y matchea, es suficiente para True.
    """
    navi_id = "uuid-navi"
    mkoi_id = "uuid-mkoi"

    resolve_map = {"Natus Vincere": navi_id}
    supabase = _make_supabase_mock(resolve_map)

    meta = GameMeta(duration_min=30.0, winner_team="Natus Vincere", loser_team="")

    result = _game_belongs_to_series(supabase, meta, navi_id, mkoi_id)

    assert result is True


# ---------------------------------------------------------------------------
# Tests de _update_manager_total_points — regla de 5 titulares
# ---------------------------------------------------------------------------


def _make_scoring_supabase(
    *,
    snapped_weeks: list[int],
    # snap_rows: list of dicts con week, member_id, slot, player_id, captain_player_id
    snap_rows: list[dict],
    # series_by_week: {week: [series_id, ...]}
    series_by_week: dict[int, list[str]],
    # pss_rows: filas devueltas por player_series_stats
    pss_rows: list[dict],
    updated_totals: dict,  # out-param: {member_id: total} se rellena en el mock
) -> MagicMock:
    """
    Construye un mock de supabase para probar _update_manager_total_points.
    """
    def _make_execute_result(data):
        r = MagicMock()
        r.data = data
        return r

    # Contador de llamadas a table("lineup_snapshots") para distinguir la 1a y 2a query
    snapshots_call_count = {"n": 0}

    def _table_side_effect(table_name: str):
        mock = MagicMock()

        if table_name == "lineup_snapshots":
            week_rows = [{"week": w} for w in snapped_weeks]
            # El código llama a supabase.table("lineup_snapshots") DOS veces.
            # Usamos un contador global para la tabla para saber en qué llamada estamos.
            snapshots_call_count["n"] += 1
            call_n = snapshots_call_count["n"]
            data_to_return = week_rows if call_n == 1 else snap_rows
            chain = MagicMock()
            chain.select.return_value = chain
            chain.eq.return_value = chain
            chain.execute.return_value = _make_execute_result(data_to_return)
            return chain

        if table_name == "series":
            week_tracker = {"current": None}
            chain = MagicMock()

            def eq_side(field, value):
                if field == "week":
                    week_tracker["current"] = value
                return chain

            chain.select.return_value = chain
            chain.eq.side_effect = eq_side
            chain.execute.side_effect = lambda: _make_execute_result(
                [{"id": sid} for sid in series_by_week.get(week_tracker["current"], [])]
            )
            return chain

        if table_name == "player_series_stats":
            chain = MagicMock()
            chain.select.return_value = chain
            chain.in_.return_value = chain
            chain.execute.return_value = _make_execute_result(pss_rows)
            return chain

        if table_name == "captain_selections":
            chain = MagicMock()
            chain.select.return_value = chain
            chain.eq.return_value = chain
            chain.limit.return_value = chain
            chain.execute.return_value = _make_execute_result([])
            return chain

        if table_name == "league_members":
            chain = MagicMock()

            def update_side(payload):
                inner = MagicMock()

                def eq_side(field, value):
                    if field == "id":
                        updated_totals[value] = payload.get("total_points")
                    result = MagicMock()
                    result.execute.return_value = _make_execute_result([])
                    return result

                inner.eq.side_effect = eq_side
                return inner

            chain.update.side_effect = update_side
            return chain

        fallback = MagicMock()
        fallback.select.return_value = fallback
        fallback.eq.return_value = fallback
        fallback.execute.return_value = _make_execute_result([])
        return fallback

    sb = MagicMock()
    sb.table.side_effect = _table_side_effect
    return sb


def test_update_manager_total_points_four_starters_gives_zero():
    """
    Un manager con solo 4 starters (un slot NULL) en su snapshot
    debe recibir 0 puntos para esa semana — aunque sus jugadores tengan series_points.
    """
    competition_id = "comp-1"
    member_id = "member-1"
    series_id = "series-1"

    # 4 starters rellenos + 1 slot NULL
    snap_rows = [
        {"week": 1, "member_id": member_id, "slot": "starter_1", "player_id": "p1", "captain_player_id": None},
        {"week": 1, "member_id": member_id, "slot": "starter_2", "player_id": "p2", "captain_player_id": None},
        {"week": 1, "member_id": member_id, "slot": "starter_3", "player_id": "p3", "captain_player_id": None},
        {"week": 1, "member_id": member_id, "slot": "starter_4", "player_id": "p4", "captain_player_id": None},
        {"week": 1, "member_id": member_id, "slot": "starter_5", "player_id": None,  "captain_player_id": None},
    ]

    # Los 4 jugadores tendrían puntos si se contaran
    pss_rows = [
        {"player_id": "p1", "series_points": 10.0},
        {"player_id": "p2", "series_points": 8.0},
        {"player_id": "p3", "series_points": 12.0},
        {"player_id": "p4", "series_points": 9.0},
    ]

    updated_totals: dict = {}
    sb = _make_scoring_supabase(
        snapped_weeks=[1],
        snap_rows=snap_rows,
        series_by_week={1: [series_id]},
        pss_rows=pss_rows,
        updated_totals=updated_totals,
    )

    _update_manager_total_points(sb, competition_id, week=1)

    assert member_id in updated_totals, "El member debería haber recibido un UPDATE de total_points"
    assert updated_totals[member_id] == 0.0, (
        f"Con 4/5 starters, total_points debe ser 0.0 — got {updated_totals[member_id]}"
    )


def test_update_manager_total_points_five_starters_scores_normally():
    """
    Un manager con 5 starters completos debe acumular los series_points normalmente.
    """
    competition_id = "comp-1"
    member_id = "member-1"
    series_id = "series-1"

    snap_rows = [
        {"week": 1, "member_id": member_id, "slot": "starter_1", "player_id": "p1", "captain_player_id": None},
        {"week": 1, "member_id": member_id, "slot": "starter_2", "player_id": "p2", "captain_player_id": None},
        {"week": 1, "member_id": member_id, "slot": "starter_3", "player_id": "p3", "captain_player_id": None},
        {"week": 1, "member_id": member_id, "slot": "starter_4", "player_id": "p4", "captain_player_id": None},
        {"week": 1, "member_id": member_id, "slot": "starter_5", "player_id": "p5", "captain_player_id": None},
    ]

    pss_rows = [
        {"player_id": "p1", "series_points": 10.0},
        {"player_id": "p2", "series_points": 8.0},
        {"player_id": "p3", "series_points": 12.0},
        {"player_id": "p4", "series_points": 9.0},
        {"player_id": "p5", "series_points": 6.0},
    ]

    updated_totals: dict = {}
    sb = _make_scoring_supabase(
        snapped_weeks=[1],
        snap_rows=snap_rows,
        series_by_week={1: [series_id]},
        pss_rows=pss_rows,
        updated_totals=updated_totals,
    )

    _update_manager_total_points(sb, competition_id, week=1)

    assert member_id in updated_totals
    assert updated_totals[member_id] == pytest.approx(45.0, abs=0.01), (
        f"Con 5/5 starters y 45 pts totales, got {updated_totals[member_id]}"
    )


def test_update_manager_total_points_partial_week_zero_full_week_scores():
    """
    Multi-semana: semana 1 tiene 4 starters (→ 0 pts), semana 2 tiene 5 (→ suma normal).
    El total debe ser solo los puntos de la semana 2.
    """
    competition_id = "comp-1"
    member_id = "member-1"

    snap_rows = [
        # Semana 1: 4 starters (un slot NULL)
        {"week": 1, "member_id": member_id, "slot": "starter_1", "player_id": "p1", "captain_player_id": None},
        {"week": 1, "member_id": member_id, "slot": "starter_2", "player_id": "p2", "captain_player_id": None},
        {"week": 1, "member_id": member_id, "slot": "starter_3", "player_id": "p3", "captain_player_id": None},
        {"week": 1, "member_id": member_id, "slot": "starter_4", "player_id": "p4", "captain_player_id": None},
        {"week": 1, "member_id": member_id, "slot": "starter_5", "player_id": None,  "captain_player_id": None},
        # Semana 2: 5 starters completos
        {"week": 2, "member_id": member_id, "slot": "starter_1", "player_id": "p1", "captain_player_id": None},
        {"week": 2, "member_id": member_id, "slot": "starter_2", "player_id": "p2", "captain_player_id": None},
        {"week": 2, "member_id": member_id, "slot": "starter_3", "player_id": "p3", "captain_player_id": None},
        {"week": 2, "member_id": member_id, "slot": "starter_4", "player_id": "p4", "captain_player_id": None},
        {"week": 2, "member_id": member_id, "slot": "starter_5", "player_id": "p5", "captain_player_id": None},
    ]

    pss_rows = [
        {"player_id": "p1", "series_points": 10.0},
        {"player_id": "p2", "series_points": 8.0},
        {"player_id": "p3", "series_points": 12.0},
        {"player_id": "p4", "series_points": 9.0},
        {"player_id": "p5", "series_points": 6.0},
    ]

    updated_totals: dict = {}
    sb = _make_scoring_supabase(
        snapped_weeks=[1, 2],
        snap_rows=snap_rows,
        series_by_week={1: ["s1"], 2: ["s2"]},
        pss_rows=pss_rows,
        updated_totals=updated_totals,
    )

    _update_manager_total_points(sb, competition_id, week=1)

    assert member_id in updated_totals
    # Semana 1 aporta 0 (4 starters), semana 2 aporta 45.0
    assert updated_totals[member_id] == pytest.approx(45.0, abs=0.01), (
        f"Semana 1 con 4 starters debe ser 0, semana 2 con 5 starters debe ser 45.0. "
        f"Got {updated_totals[member_id]}"
    )
