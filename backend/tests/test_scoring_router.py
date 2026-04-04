"""Tests para GET /scoring/player/{player_id}/history — mockean Supabase sin red."""
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from auth.dependencies import get_current_user, get_supabase
from main import app

# ---------------------------------------------------------------------------
# Datos de prueba
# ---------------------------------------------------------------------------

USER_ID = str(uuid4())
PLAYER_ID = str(uuid4())
GAME_ID_1 = str(uuid4())
GAME_ID_2 = str(uuid4())
SERIES_ID_1 = str(uuid4())
SERIES_ID_2 = str(uuid4())
COMPETITION_ID = str(uuid4())
TEAM_HOME_ID = str(uuid4())
TEAM_AWAY_ID = str(uuid4())

FAKE_USER = {"id": USER_ID, "email": "test@test.com"}

PLAYER = {
    "id": PLAYER_ID,
    "name": "Caps",
    "team": "G2 Esports",
    "role": "mid",
    "image_url": None,
    "current_price": 12.5,
}

# Equipos mockeados (todos, para resolución de team_id por nombre)
ALL_TEAMS = [
    {"id": TEAM_HOME_ID, "name": "G2 Esports", "aliases": ["G2 Esports", "G2"]},
    {"id": TEAM_AWAY_ID, "name": "Fnatic", "aliases": ["Fnatic", "FNC"]},
]

# Equipos por ID (para obtener nombres en la respuesta)
TEAMS_BY_ID = [
    {"id": TEAM_HOME_ID, "name": "G2 Esports"},
    {"id": TEAM_AWAY_ID, "name": "Fnatic"},
]

# player_series_stats con nested series+competitions (historial, 1a query)
SERIES_STATS = [
    {
        "series_id": SERIES_ID_1,
        "series_points": 18.5,
        "avg_kills": 5.0,
        "avg_deaths": 2.0,
        "avg_assists": 3.0,
        "avg_cs_per_min": 8.5,
        "avg_dpm": 450.0,
        "avg_vision_score": 25.0,
        "series": {
            "id": SERIES_ID_1,
            "date": "2026-03-15",
            "competition_id": COMPETITION_ID,
            "winner_id": TEAM_HOME_ID,
            "team_home_id": TEAM_HOME_ID,
            "team_away_id": TEAM_AWAY_ID,
            "competitions": {"name": "LEC Spring 2026"},
        },
    },
    {
        "series_id": SERIES_ID_2,
        "series_points": 10.0,
        "avg_kills": 2.0,
        "avg_deaths": 4.0,
        "avg_assists": 7.0,
        "avg_cs_per_min": 7.2,
        "avg_dpm": 380.0,
        "avg_vision_score": 18.0,
        "series": {
            "id": SERIES_ID_2,
            "date": "2026-03-08",
            "competition_id": COMPETITION_ID,
            "winner_id": TEAM_HOME_ID,
            "team_home_id": TEAM_HOME_ID,
            "team_away_id": TEAM_AWAY_ID,
            "competitions": {"name": "LEC Spring 2026"},
        },
    },
]

ACTIVE_COMPETITION = [{"id": COMPETITION_ID}]

# player_series_stats para total_points (2a query, sin límite)
TOTAL_SERIES_STATS = [
    {"series_points": 18.5, "series": {"competition_id": COMPETITION_ID}},
    {"series_points": 10.0, "series": {"competition_id": COMPETITION_ID}},
]


# ---------------------------------------------------------------------------
# Helpers (mismo patrón que test_leagues.py)
# ---------------------------------------------------------------------------

def _chain(*return_values: object) -> MagicMock:
    """Query-builder mock que devuelve valores en secuencia en cada .execute()."""
    results = []
    for val in return_values:
        r = MagicMock()
        r.data = val
        results.append(r)

    call_count = {"n": 0}
    chain = MagicMock()

    def execute_side_effect():
        idx = call_count["n"]
        call_count["n"] += 1
        return results[idx] if idx < len(results) else results[-1]

    chain.execute.side_effect = execute_side_effect
    for method in ("select", "eq", "in_", "insert", "single", "order", "limit", "execute"):
        getattr(chain, method).return_value = chain
    chain.execute.side_effect = execute_side_effect  # restaurar después del loop
    return chain


def _sb_multi(*table_chains: tuple) -> MagicMock:
    mapping = {name: chain for name, chain in table_chains}
    sb = MagicMock()
    sb.table.side_effect = lambda name: mapping.get(name, _chain([]))
    return sb


def _mock_user() -> dict:
    return FAKE_USER


def _client(sb: MagicMock) -> TestClient:
    app.dependency_overrides[get_supabase] = lambda: sb
    app.dependency_overrides[get_current_user] = _mock_user
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Fixture de cleanup
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def cleanup_overrides():
    yield
    app.dependency_overrides.pop(get_supabase, None)
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Fixture principal: respuesta exitosa
# ---------------------------------------------------------------------------

@pytest.fixture
def history_response():
    """Llama al endpoint con mocks completos y devuelve el JSON de respuesta."""
    # teams se consulta dos veces: 1) todos los equipos para resolver team_id
    # 2) equipos por ID para obtener nombres home/away
    teams_chain = _chain(ALL_TEAMS, TEAMS_BY_ID)
    # player_series_stats se consulta dos veces: 1) historial, 2) total_points
    pss_chain = _chain(SERIES_STATS, TOTAL_SERIES_STATS)

    sb = _sb_multi(
        ("players", _chain([PLAYER])),
        ("teams", teams_chain),
        ("player_series_stats", pss_chain),
        ("competitions", _chain(ACTIVE_COMPETITION)),
    )

    r = _client(sb).get(f"/scoring/player/{PLAYER_ID}/history")
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Tests: campos nuevos
# ---------------------------------------------------------------------------

def test_each_stat_has_competition_id(history_response):
    """Cada stat debe incluir competition_id como string no vacío."""
    stats = history_response["stats"]
    assert len(stats) > 0, "No hay stats en la respuesta"
    for stat in stats:
        assert "competition_id" in stat, f"Falta competition_id en stat: {stat}"
        assert isinstance(stat["competition_id"], str)
        assert stat["competition_id"] != "", "competition_id no puede ser string vacío"


def test_each_stat_has_competition_name(history_response):
    """Cada stat debe incluir competition_name como string no vacío."""
    stats = history_response["stats"]
    assert len(stats) > 0, "No hay stats en la respuesta"
    for stat in stats:
        assert "competition_name" in stat, f"Falta competition_name en stat: {stat}"
        assert isinstance(stat["competition_name"], str)
        assert stat["competition_name"] != "", "competition_name no puede ser string vacío"


def test_competition_id_is_valid_uuid(history_response):
    """competition_id debe ser un UUID válido."""
    from uuid import UUID
    stats = history_response["stats"]
    for stat in stats:
        try:
            UUID(stat["competition_id"])
        except (ValueError, AttributeError) as exc:
            pytest.fail(f"competition_id no es un UUID válido: {stat['competition_id']} — {exc}")


def test_competition_name_matches_mock(history_response):
    """competition_name debe coincidir con el nombre mockeado."""
    stats = history_response["stats"]
    for stat in stats:
        assert stat["competition_name"] == "LEC Spring 2026"


# ---------------------------------------------------------------------------
# Tests: campos anteriores siguen presentes
# ---------------------------------------------------------------------------

EXPECTED_FIELDS = [
    "kills", "deaths", "assists", "cs_per_min",
    "xp_diff_at_15", "fantasy_points", "dpm",
    "gold_diff_at_15", "matches",
]


def test_existing_fields_still_present(history_response):
    """Los campos anteriores deben seguir presentes en cada stat."""
    stats = history_response["stats"]
    assert len(stats) > 0
    for stat in stats:
        for field in EXPECTED_FIELDS:
            assert field in stat, f"Campo '{field}' desapareció de la respuesta"


def test_kills_deaths_assists_are_numeric(history_response):
    # Ahora son promedios por serie (floats), no enteros por juego
    stats = history_response["stats"]
    for stat in stats:
        assert isinstance(stat["kills"], (int, float))
        assert isinstance(stat["deaths"], (int, float))
        assert isinstance(stat["assists"], (int, float))


def test_fantasy_points_is_numeric(history_response):
    stats = history_response["stats"]
    for stat in stats:
        assert isinstance(stat["fantasy_points"], (int, float))


def test_matches_has_required_subfields(history_response):
    """El campo matches (cuando no es null) debe tener scheduled_at, team_1, team_2."""
    stats = history_response["stats"]
    for stat in stats:
        if stat["matches"] is not None:
            assert "scheduled_at" in stat["matches"]
            assert "team_1" in stat["matches"]
            assert "team_2" in stat["matches"]


def test_response_has_player_and_total_points(history_response):
    """La respuesta raíz debe tener player y total_points."""
    assert "player" in history_response
    assert "total_points" in history_response
    assert isinstance(history_response["total_points"], (int, float))


# ---------------------------------------------------------------------------
# Tests: edge cases
# ---------------------------------------------------------------------------

def test_player_not_found_returns_404():
    """Si el jugador no existe, debe devolver 404."""
    sb = _sb_multi(
        ("players", _chain([])),
        ("teams", _chain([], [])),
        ("player_series_stats", _chain([], [])),
        ("competitions", _chain([])),
    )
    r = _client(sb).get(f"/scoring/player/{uuid4()}/history")
    assert r.status_code == 404


def test_invalid_uuid_returns_422():
    """UUID inválido debe devolver 422."""
    sb = _sb_multi(("players", _chain([])))
    r = _client(sb).get("/scoring/player/no-es-uuid/history")
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Fixture con player_game_stats que expone duration_min desde games
# (necesaria para stat_breakdown y tests de normalización)
# ---------------------------------------------------------------------------

# Datos de player_game_stats con join a games(series_id, duration_min)
# Simula dos juegos de la misma serie con duración ~33 min cada uno
PLAYER_GAME_STATS = [
    {
        "gold_diff_15": 250.0,
        "xp_diff_15": 180.0,
        "games": {"series_id": SERIES_ID_1, "duration_min": 33.0},
    },
    {
        "gold_diff_15": 300.0,
        "xp_diff_15": 220.0,
        "games": {"series_id": SERIES_ID_1, "duration_min": 34.0},
    },
    {
        "gold_diff_15": -100.0,
        "xp_diff_15": -50.0,
        "games": {"series_id": SERIES_ID_2, "duration_min": 28.0},
    },
]


@pytest.fixture
def history_response_with_duration():
    """
    Fixture que incluye player_game_stats con duration_min.
    Necesaria para probar que stat_breakdown usa duración real desde games.duration_min.
    """
    teams_chain = _chain(ALL_TEAMS, TEAMS_BY_ID)
    pss_chain = _chain(SERIES_STATS, TOTAL_SERIES_STATS)
    pgs_chain = _chain(PLAYER_GAME_STATS)

    sb = _sb_multi(
        ("players", _chain([PLAYER])),
        ("teams", teams_chain),
        ("player_series_stats", pss_chain),
        ("player_game_stats", pgs_chain),
        ("competitions", _chain(ACTIVE_COMPETITION)),
    )

    r = _client(sb).get(f"/scoring/player/{PLAYER_ID}/history")
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Tests: stat_breakdown
# ---------------------------------------------------------------------------

def test_stat_breakdown_present_in_each_stat(history_response_with_duration):
    """stat_breakdown debe estar presente en cada stat cuando el jugador tiene rol."""
    stats = history_response_with_duration["stats"]
    assert len(stats) > 0
    for stat in stats:
        assert "stat_breakdown" in stat, f"Falta stat_breakdown en stat: {stat}"


def test_stat_breakdown_is_dict_or_none(history_response_with_duration):
    """stat_breakdown debe ser dict (con rol conocido) o None."""
    stats = history_response_with_duration["stats"]
    for stat in stats:
        breakdown = stat["stat_breakdown"]
        assert breakdown is None or isinstance(breakdown, dict), (
            f"stat_breakdown debe ser dict o None, got: {type(breakdown)}"
        )


def test_stat_breakdown_has_expected_keys_for_mid(history_response_with_duration):
    """Para rol mid, stat_breakdown debe tener kills, deaths, assists, cs_per_min, dpm."""
    stats = history_response_with_duration["stats"]
    for stat in stats:
        breakdown = stat["stat_breakdown"]
        if breakdown is not None:
            for expected_key in ("kills", "deaths", "assists", "cs_per_min", "dpm"):
                assert expected_key in breakdown, (
                    f"Falta '{expected_key}' en stat_breakdown: {breakdown}"
                )


def test_stat_breakdown_values_are_numeric(history_response_with_duration):
    """Todos los valores de stat_breakdown deben ser numéricos."""
    stats = history_response_with_duration["stats"]
    for stat in stats:
        breakdown = stat["stat_breakdown"]
        if breakdown is not None:
            for key, val in breakdown.items():
                assert isinstance(val, (int, float)), (
                    f"stat_breakdown['{key}'] = {val!r} no es numérico"
                )


def test_stat_breakdown_kills_in_realistic_range(history_response_with_duration):
    """
    Regresión del bug de normalización:
    stat_breakdown['kills'] para stats típicas (kills≈5, duration≈33min) debe ser ~12 pts,
    NO ~420 pts (que es lo que producía el bug de stats brutas × pesos/min).
    """
    stats = history_response_with_duration["stats"]
    for stat in stats:
        breakdown = stat["stat_breakdown"]
        if breakdown is not None and "kills" in breakdown:
            kills_pts = breakdown["kills"]
            assert kills_pts < 50.0, (
                f"stat_breakdown['kills'] = {kills_pts} es demasiado alto. "
                "Si supera 50 pts, el endpoint está usando stats brutas × pesos calibrados/min "
                "(el bug que se fixeó en 2026-03-25)."
            )


def test_stat_breakdown_total_in_realistic_range(history_response_with_duration):
    """
    La suma de stat_breakdown no debe superar ~60 pts para stats típicas de mid.
    Valores >100 indican que se están usando stats brutas (el bug).
    """
    stats = history_response_with_duration["stats"]
    for stat in stats:
        breakdown = stat["stat_breakdown"]
        if breakdown is not None:
            total = sum(v for v in breakdown.values() if v > 0)
            assert total < 100.0, (
                f"Suma de componentes positivos de stat_breakdown = {total}. "
                "Supera el límite de 100 pts — posible regresión del bug de normalización."
            )


def test_stat_breakdown_deaths_contributes_negatively(history_response_with_duration):
    """deaths debe contribuir negativamente al stat_breakdown (peso negativo)."""
    stats = history_response_with_duration["stats"]
    for stat in stats:
        breakdown = stat["stat_breakdown"]
        # Solo chequeamos series con muertes > 0
        if breakdown is not None and "deaths" in breakdown:
            deaths_raw = stat.get("deaths", 0)
            if deaths_raw > 0:
                assert breakdown["deaths"] < 0, (
                    f"stat_breakdown['deaths'] = {breakdown['deaths']} debe ser negativo "
                    f"cuando hay {deaths_raw} muertes (peso negativo en todos los roles)"
                )


# ---------------------------------------------------------------------------
# Tests: duration leída desde games.duration_min (no de columna inexistente)
# ---------------------------------------------------------------------------

def test_duration_from_games_duration_min():
    """
    Verifica que el endpoint lee duration_min desde el join games(duration_min)
    en player_game_stats, en lugar de una columna que no existe.
    La duración real debe afectar los valores de stat_breakdown.
    """
    # Juego corto (~20 min) → kills/min más alto → más pts en stat_breakdown
    pgs_short = [
        {
            "gold_diff_15": 200.0,
            "xp_diff_15": 100.0,
            "games": {"series_id": SERIES_ID_1, "duration_min": 20.0},
        }
    ]
    # Juego largo (~45 min) → kills/min más bajo → menos pts en stat_breakdown
    pgs_long = [
        {
            "gold_diff_15": 200.0,
            "xp_diff_15": 100.0,
            "games": {"series_id": SERIES_ID_1, "duration_min": 45.0},
        }
    ]

    def _build_client(pgs_data):
        teams_chain = _chain(ALL_TEAMS, TEAMS_BY_ID)
        pss_chain = _chain(SERIES_STATS, TOTAL_SERIES_STATS)
        pgs_chain = _chain(pgs_data)
        sb = _sb_multi(
            ("players", _chain([PLAYER])),
            ("teams", teams_chain),
            ("player_series_stats", pss_chain),
            ("player_game_stats", pgs_chain),
            ("competitions", _chain(ACTIVE_COMPETITION)),
        )
        return _client(sb)

    r_short = _build_client(pgs_short).get(f"/scoring/player/{PLAYER_ID}/history")
    r_long = _build_client(pgs_long).get(f"/scoring/player/{PLAYER_ID}/history")

    assert r_short.status_code == 200, r_short.text
    assert r_long.status_code == 200, r_long.text

    stats_short = r_short.json()["stats"]
    stats_long = r_long.json()["stats"]

    # Buscar la serie que tiene el game mockeado (SERIES_ID_1)
    def _find_series(stats_list, series_id):
        return next((s for s in stats_list if s["series_id"] == series_id), None)

    stat_short = _find_series(stats_short, SERIES_ID_1)
    stat_long = _find_series(stats_long, SERIES_ID_1)

    assert stat_short is not None, "No se encontró la serie en respuesta con juego corto"
    assert stat_long is not None, "No se encontró la serie en respuesta con juego largo"

    bd_short = stat_short.get("stat_breakdown") or {}
    bd_long = stat_long.get("stat_breakdown") or {}

    # Con duración corta, kills/min es mayor → más pts de kills
    if "kills" in bd_short and "kills" in bd_long:
        assert bd_short["kills"] > bd_long["kills"], (
            f"Con duración 20 min las kills deben generar más pts que con 45 min. "
            f"short={bd_short['kills']}, long={bd_long['kills']}. "
            "Si son iguales, el endpoint no está leyendo duration_min desde games."
        )


def test_no_player_game_stats_uses_default_duration():
    """
    Si player_game_stats no devuelve datos para una serie, stat_breakdown
    debe usar la duración por defecto (33.4 min) y no romper.
    """
    teams_chain = _chain(ALL_TEAMS, TEAMS_BY_ID)
    pss_chain = _chain(SERIES_STATS, TOTAL_SERIES_STATS)
    pgs_chain = _chain([])  # sin datos de duración

    sb = _sb_multi(
        ("players", _chain([PLAYER])),
        ("teams", teams_chain),
        ("player_series_stats", pss_chain),
        ("player_game_stats", pgs_chain),
        ("competitions", _chain(ACTIVE_COMPETITION)),
    )

    r = _client(sb).get(f"/scoring/player/{PLAYER_ID}/history")
    assert r.status_code == 200, r.text

    stats = r.json()["stats"]
    assert len(stats) > 0

    for stat in stats:
        breakdown = stat.get("stat_breakdown")
        if breakdown is not None:
            # Con duración default (33.4), kills debe estar en rango razonable
            if "kills" in breakdown:
                assert breakdown["kills"] < 50.0, (
                    f"Con duración default 33.4 min, kills pts = {breakdown['kills']} "
                    "supera el límite esperado de 50 pts."
                )
