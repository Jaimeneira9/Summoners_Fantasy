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

# Respuesta de player_game_stats para ordenar por fecha (1a query)
GAMES_FOR_PLAYER = [
    {
        "game_id": GAME_ID_1,
        "games": {"id": GAME_ID_1, "series": {"date": "2026-03-15"}},
    },
    {
        "game_id": GAME_ID_2,
        "games": {"id": GAME_ID_2, "series": {"date": "2026-03-08"}},
    },
]

# Respuesta de player_game_stats con stats reales (2a query, ya filtrada)
RAW_STATS = [
    {
        "game_id": GAME_ID_1,
        "kills": 5,
        "deaths": 2,
        "assists": 3,
        "cs_per_min": 8.5,
        "vision_score": 25,
        "game_points": 18.5,
        "damage_share": 0.32,
        "gold_diff_15": 450,
    },
    {
        "game_id": GAME_ID_2,
        "kills": 2,
        "deaths": 4,
        "assists": 7,
        "cs_per_min": 7.2,
        "vision_score": 18,
        "game_points": 10.0,
        "damage_share": 0.28,
        "gold_diff_15": -300,
    },
]

# Respuesta de games con series y competitions nested
GAMES_DATA = [
    {
        "id": GAME_ID_1,
        "team_home_id": TEAM_HOME_ID,
        "team_away_id": TEAM_AWAY_ID,
        "duration_min": 28.5,
        "series": {
            "date": "2026-03-15",
            "competition_id": COMPETITION_ID,
            "competitions": {"name": "LEC Spring 2026"},
        },
    },
    {
        "id": GAME_ID_2,
        "team_home_id": TEAM_AWAY_ID,
        "team_away_id": TEAM_HOME_ID,
        "duration_min": 32.0,
        "series": {
            "date": "2026-03-08",
            "competition_id": COMPETITION_ID,
            "competitions": {"name": "LEC Spring 2026"},
        },
    },
]

TEAMS_DATA = [
    {"id": TEAM_HOME_ID, "name": "G2 Esports"},
    {"id": TEAM_AWAY_ID, "name": "FNC"},
]

ACTIVE_COMPETITION = [{"id": COMPETITION_ID}]

# Para el total_points: player_game_stats con game_points + nested competition_id
TOTAL_STATS = [
    {
        "game_points": 18.5,
        "games": {"series": {"competition_id": COMPETITION_ID}},
    },
    {
        "game_points": 10.0,
        "games": {"series": {"competition_id": COMPETITION_ID}},
    },
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
    pgs_chain = _chain(GAMES_FOR_PLAYER, RAW_STATS, TOTAL_STATS)
    games_chain = _chain(GAMES_DATA)
    teams_chain = _chain(TEAMS_DATA)
    comp_chain = _chain(ACTIVE_COMPETITION)

    sb = _sb_multi(
        ("players", _chain([PLAYER])),
        ("player_game_stats", pgs_chain),
        ("games", games_chain),
        ("teams", teams_chain),
        ("competitions", comp_chain),
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


def test_kills_deaths_assists_are_integers(history_response):
    stats = history_response["stats"]
    for stat in stats:
        assert isinstance(stat["kills"], int)
        assert isinstance(stat["deaths"], int)
        assert isinstance(stat["assists"], int)


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
    pgs_chain = _chain([], [], [])
    sb = _sb_multi(
        ("players", _chain([])),
        ("player_game_stats", pgs_chain),
        ("games", _chain([])),
        ("teams", _chain([])),
        ("competitions", _chain([])),
    )
    r = _client(sb).get(f"/scoring/player/{uuid4()}/history")
    assert r.status_code == 404


def test_invalid_uuid_returns_422():
    """UUID inválido debe devolver 422."""
    sb = _sb_multi(("players", _chain([])))
    r = _client(sb).get("/scoring/player/no-es-uuid/history")
    assert r.status_code == 422
