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
    "vision_score", "fantasy_points", "dpm",
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
