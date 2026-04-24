"""Tests para POST /roster/{league_id}/pick — mockean Supabase y get_current_user, sin red."""
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
LEAGUE_ID = str(uuid4())
COMPETITION_ID = str(uuid4())
MEMBER_ID = str(uuid4())
ROSTER_ID = str(uuid4())
PLAYER_A_ID = str(uuid4())
PLAYER_B_ID = str(uuid4())
ROSTER_PLAYER_A_ID = str(uuid4())

LEAGUE_BUDGET_PICK = {
    "id": LEAGUE_ID,
    "game_mode": "budget_pick",
    "competition_id": COMPETITION_ID,
}

LEAGUE_DRAFT_MARKET = {
    "id": LEAGUE_ID,
    "game_mode": "draft_market",
    "competition_id": COMPETITION_ID,
}

MEMBER = {"id": MEMBER_ID, "remaining_budget": 80.0, "total_points": 0.0}

PLAYER_TOP = {
    "id": PLAYER_B_ID,
    "name": "Odoamne",
    "team": "BDS",
    "role": "top",
    "current_price": 15.0,
}

PLAYER_JUNGLE = {
    "id": PLAYER_B_ID,
    "name": "Inspired",
    "team": "BDS",
    "role": "jungle",
    "current_price": 15.0,
}

OCCUPANT_A = {
    "id": ROSTER_PLAYER_A_ID,
    "player_id": PLAYER_A_ID,
    "price_paid": 20.0,
}

ROSTER = {"id": ROSTER_ID}

SERIES_IN_PROGRESS = [{"id": str(uuid4())}]

FAKE_USER = {"id": USER_ID, "email": "test@test.com"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_user() -> dict:
    return FAKE_USER


def _chain(*return_values: object) -> MagicMock:
    """
    Query-builder mock que devuelve `return_values` en orden por cada .execute().
    Soporta todos los métodos del query-builder de Supabase usados en el backend.
    """
    results = []
    for val in return_values:
        r = MagicMock()
        r.data = val
        r.count = len(val) if isinstance(val, list) else 0
        results.append(r)

    call_count = {"n": 0}
    chain = MagicMock()

    def execute_side_effect():
        idx = call_count["n"]
        call_count["n"] += 1
        return results[idx] if idx < len(results) else results[-1]

    chain.execute.side_effect = execute_side_effect
    for method in ("select", "eq", "in_", "insert", "single", "order", "limit",
                   "update", "delete", "gt", "gte", "lt", "lte", "neq", "is_",
                   "not_", "or_", "filter", "upsert"):
        getattr(chain, method).return_value = chain

    return chain


def _rpc_chain(data: object) -> MagicMock:
    """Mock para supabase.rpc(...) — devuelve un mock con .data fijo."""
    result = MagicMock()
    result.data = data
    rpc_mock = MagicMock()
    rpc_mock.execute.return_value = result
    return rpc_mock


def _sb_multi(*table_chains: tuple, rpc_data: object = True) -> MagicMock:
    mapping = {name: chain for name, chain in table_chains}
    sb = MagicMock()
    sb.table.side_effect = lambda name: mapping.get(name, _chain([]))
    sb.rpc.return_value = _rpc_chain(rpc_data)
    return sb


# ---------------------------------------------------------------------------
# Fixtures base
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def override_user():
    app.dependency_overrides[get_current_user] = _mock_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _client(sb: MagicMock) -> TestClient:
    app.dependency_overrides[get_supabase] = lambda: sb
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# POST /roster/{league_id}/pick
# ---------------------------------------------------------------------------

def test_pick_empty_slot_ok() -> None:
    """Fichar jugador en slot vacío: HTTP 200, released_player_id=None, budget correcto."""
    # fantasy_leagues: game_mode=budget_pick
    fl_chain = _chain(LEAGUE_BUDGET_PICK)
    # league_members: membresía ok
    lm_chain = _chain([MEMBER])
    # series: no hay in_progress
    sr_chain = _chain([])
    # players: jugador activo, role=top
    pl_chain = _chain([PLAYER_TOP])
    # rosters: roster existente
    ro_chain = _chain([ROSTER])
    # roster_players: 1) dup check → vacío; 2) occupant check → vacío
    rp_chain = _chain([], [])

    sb = _sb_multi(
        ("fantasy_leagues", fl_chain),
        ("league_members", lm_chain),
        ("series", sr_chain),
        ("players", pl_chain),
        ("rosters", ro_chain),
        ("roster_players", rp_chain),
        rpc_data=True,
    )

    r = _client(sb).post(
        f"/roster/{LEAGUE_ID}/pick",
        json={"player_id": PLAYER_B_ID, "slot": "starter_1"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["released_player_id"] is None
    assert body["remaining_budget"] == pytest.approx(65.0)  # 80 - 15


def test_pick_swap_occupied_slot_ok() -> None:
    """Reemplazar jugador en slot ocupado: libera A (price_paid=20) y ficha B (25)."""
    member_30 = {**MEMBER, "remaining_budget": 30.0}
    player_b_25 = {**PLAYER_TOP, "current_price": 25.0}

    fl_chain = _chain(LEAGUE_BUDGET_PICK)
    lm_chain = _chain([member_30])
    # series: no in_progress; luego current_week query (step 10)
    sr_chain = _chain([], [{"week": 5}])
    pl_chain = _chain([player_b_25])
    ro_chain = _chain([ROSTER])
    # roster_players: 1) dup → vacío; 2) occupant → OCCUPANT_A;
    #   3) captain_selections query; 4) delete occupant; 5) insert nuevo
    rp_chain = _chain([], [OCCUPANT_A])
    # captain_selections: capitán no coincide con el jugador saliente
    cs_chain = _chain([])

    sb = _sb_multi(
        ("fantasy_leagues", fl_chain),
        ("league_members", lm_chain),
        ("series", sr_chain),
        ("players", pl_chain),
        ("rosters", ro_chain),
        ("roster_players", rp_chain),
        ("captain_selections", cs_chain),
        rpc_data=True,
    )

    r = _client(sb).post(
        f"/roster/{LEAGUE_ID}/pick",
        json={"player_id": PLAYER_B_ID, "slot": "starter_1"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["released_player_id"] == PLAYER_A_ID
    # budget = 30 + 20 - 25 = 25
    assert body["remaining_budget"] == pytest.approx(25.0)


def test_pick_insufficient_budget() -> None:
    """swap_budget devuelve False → HTTP 402."""
    fl_chain = _chain(LEAGUE_BUDGET_PICK)
    lm_chain = _chain([MEMBER])
    sr_chain = _chain([])
    pl_chain = _chain([PLAYER_TOP])
    ro_chain = _chain([ROSTER])
    rp_chain = _chain([], [])

    sb = _sb_multi(
        ("fantasy_leagues", fl_chain),
        ("league_members", lm_chain),
        ("series", sr_chain),
        ("players", pl_chain),
        ("rosters", ro_chain),
        ("roster_players", rp_chain),
        rpc_data=False,  # swap_budget falla
    )

    r = _client(sb).post(
        f"/roster/{LEAGUE_ID}/pick",
        json={"player_id": PLAYER_B_ID, "slot": "starter_1"},
    )
    assert r.status_code == 402


def test_pick_jornada_bloqueada() -> None:
    """Hay series in_progress → HTTP 409."""
    fl_chain = _chain(LEAGUE_BUDGET_PICK)
    lm_chain = _chain([MEMBER])
    sr_chain = _chain(SERIES_IN_PROGRESS)  # jornada en curso

    sb = _sb_multi(
        ("fantasy_leagues", fl_chain),
        ("league_members", lm_chain),
        ("series", sr_chain),
    )

    r = _client(sb).post(
        f"/roster/{LEAGUE_ID}/pick",
        json={"player_id": PLAYER_B_ID, "slot": "starter_1"},
    )
    assert r.status_code == 409


def test_pick_wrong_game_mode() -> None:
    """Liga con game_mode=draft_market → HTTP 400."""
    fl_chain = _chain(LEAGUE_DRAFT_MARKET)

    sb = _sb_multi(("fantasy_leagues", fl_chain))

    r = _client(sb).post(
        f"/roster/{LEAGUE_ID}/pick",
        json={"player_id": PLAYER_B_ID, "slot": "starter_1"},
    )
    assert r.status_code == 400


def test_pick_inactive_player() -> None:
    """Jugador no encontrado o inactivo (query devuelve lista vacía) → HTTP 404."""
    fl_chain = _chain(LEAGUE_BUDGET_PICK)
    lm_chain = _chain([MEMBER])
    sr_chain = _chain([])
    pl_chain = _chain([])  # jugador no encontrado

    sb = _sb_multi(
        ("fantasy_leagues", fl_chain),
        ("league_members", lm_chain),
        ("series", sr_chain),
        ("players", pl_chain),
    )

    r = _client(sb).post(
        f"/roster/{LEAGUE_ID}/pick",
        json={"player_id": PLAYER_B_ID, "slot": "starter_1"},
    )
    assert r.status_code == 404


def test_pick_duplicate_player() -> None:
    """Jugador ya está en el roster (dup check devuelve resultado) → HTTP 409."""
    fl_chain = _chain(LEAGUE_BUDGET_PICK)
    lm_chain = _chain([MEMBER])
    sr_chain = _chain([])
    pl_chain = _chain([PLAYER_TOP])
    ro_chain = _chain([ROSTER])
    # dup check devuelve al menos 1 resultado → duplicado
    rp_chain = _chain([{"id": str(uuid4())}])

    sb = _sb_multi(
        ("fantasy_leagues", fl_chain),
        ("league_members", lm_chain),
        ("series", sr_chain),
        ("players", pl_chain),
        ("rosters", ro_chain),
        ("roster_players", rp_chain),
    )

    r = _client(sb).post(
        f"/roster/{LEAGUE_ID}/pick",
        json={"player_id": PLAYER_B_ID, "slot": "starter_1"},
    )
    assert r.status_code == 409


def test_pick_wrong_slot_role() -> None:
    """Jugador jungle en slot starter_1 (top) → HTTP 422."""
    fl_chain = _chain(LEAGUE_BUDGET_PICK)
    lm_chain = _chain([MEMBER])
    sr_chain = _chain([])
    pl_chain = _chain([PLAYER_JUNGLE])  # role=jungle, pero slot=starter_1 (top)

    sb = _sb_multi(
        ("fantasy_leagues", fl_chain),
        ("league_members", lm_chain),
        ("series", sr_chain),
        ("players", pl_chain),
    )

    r = _client(sb).post(
        f"/roster/{LEAGUE_ID}/pick",
        json={"player_id": PLAYER_B_ID, "slot": "starter_1"},
    )
    assert r.status_code == 422


def test_pick_clears_captain() -> None:
    """Jugador saliente era capitán: verifica que captain_selections.update fue llamado con captain_player_id=None."""
    member_50 = {**MEMBER, "remaining_budget": 50.0}
    player_b_20 = {**PLAYER_TOP, "current_price": 20.0}
    captain_week = 6  # current_week=5, captain_week=6

    fl_chain = _chain(LEAGUE_BUDGET_PICK)
    lm_chain = _chain([member_50])
    # series: 1) in_progress → vacío; 2) current_week → semana 5
    sr_chain = _chain([], [{"week": 5}])
    pl_chain = _chain([player_b_20])
    ro_chain = _chain([ROSTER])
    # roster_players: 1) dup → vacío; 2) occupant → OCCUPANT_A (player_id=PLAYER_A_ID)
    rp_chain = _chain([], [OCCUPANT_A])
    # captain_selections: jugador saliente ES el capitán de captain_week
    cs_chain = _chain([{"captain_player_id": PLAYER_A_ID}], None)

    sb = _sb_multi(
        ("fantasy_leagues", fl_chain),
        ("league_members", lm_chain),
        ("series", sr_chain),
        ("players", pl_chain),
        ("rosters", ro_chain),
        ("roster_players", rp_chain),
        ("captain_selections", cs_chain),
        rpc_data=True,
    )

    r = _client(sb).post(
        f"/roster/{LEAGUE_ID}/pick",
        json={"player_id": PLAYER_B_ID, "slot": "starter_1"},
    )
    assert r.status_code == 200

    # Verificar que captain_selections.update fue llamado con captain_player_id=None
    cs_mock = sb.table("captain_selections")
    cs_mock.update.assert_called_once_with({"captain_player_id": None})


# ---------------------------------------------------------------------------
# GET /roster/{league_id}/available-players
# ---------------------------------------------------------------------------

PLAYER_MID_1 = {
    "id": str(uuid4()),
    "name": "Caps",
    "team": "G2",
    "role": "mid",
    "image_url": None,
    "current_price": 20.0,
    "last_price_change_pct": 0.0,
}

PLAYER_MID_2 = {
    "id": str(uuid4()),
    "name": "Humanoid",
    "team": "FNC",
    "role": "mid",
    "image_url": None,
    "current_price": 18.0,
    "last_price_change_pct": 0.0,
}

PLAYER_TOP_2 = {
    "id": str(uuid4()),
    "name": "BrokenBlade",
    "team": "G2",
    "role": "top",
    "image_url": None,
    "current_price": 16.0,
    "last_price_change_pct": 0.0,
}

COMPETITION = {"name": "LEC Spring 2025"}


def test_available_players_all() -> None:
    """Liga budget_pick, roster vacío → HTTP 200, 3 jugadores, in_my_roster=False en todos."""
    fl_chain = _chain(LEAGUE_BUDGET_PICK)
    lm_chain = _chain([MEMBER])
    comp_chain = _chain(COMPETITION)
    pl_chain = _chain([PLAYER_MID_1, PLAYER_MID_2, PLAYER_TOP_2])
    ro_chain = _chain([])  # sin roster → my_player_ids vacío

    sb = _sb_multi(
        ("fantasy_leagues", fl_chain),
        ("league_members", lm_chain),
        ("competitions", comp_chain),
        ("players", pl_chain),
        ("rosters", ro_chain),
    )

    r = _client(sb).get(f"/roster/{LEAGUE_ID}/available-players")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 3
    assert all(p["in_my_roster"] is False for p in body)


def test_available_players_filter_role() -> None:
    """Parámetro ?role=mid → HTTP 200, 2 jugadores, todos role=mid."""
    fl_chain = _chain(LEAGUE_BUDGET_PICK)
    lm_chain = _chain([MEMBER])
    comp_chain = _chain(COMPETITION)
    pl_chain = _chain([PLAYER_MID_1, PLAYER_MID_2])  # el mock devuelve solo mids
    ro_chain = _chain([])

    sb = _sb_multi(
        ("fantasy_leagues", fl_chain),
        ("league_members", lm_chain),
        ("competitions", comp_chain),
        ("players", pl_chain),
        ("rosters", ro_chain),
    )

    r = _client(sb).get(f"/roster/{LEAGUE_ID}/available-players?role=mid")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    assert all(p["role"] == "mid" for p in body)


def test_available_players_in_my_roster() -> None:
    """Jugador X en el roster del user → in_my_roster=True; jugador Y → False."""
    player_x_id = str(uuid4())
    player_y_id = str(uuid4())

    player_x = {**PLAYER_MID_1, "id": player_x_id}
    player_y = {**PLAYER_MID_2, "id": player_y_id}

    fl_chain = _chain(LEAGUE_BUDGET_PICK)
    lm_chain = _chain([MEMBER])
    comp_chain = _chain(COMPETITION)
    pl_chain = _chain([player_x, player_y])
    ro_chain = _chain([ROSTER])
    # roster_players: el user tiene al jugador X
    rp_chain = _chain([{"player_id": player_x_id}])

    sb = _sb_multi(
        ("fantasy_leagues", fl_chain),
        ("league_members", lm_chain),
        ("competitions", comp_chain),
        ("players", pl_chain),
        ("rosters", ro_chain),
        ("roster_players", rp_chain),
    )

    r = _client(sb).get(f"/roster/{LEAGUE_ID}/available-players")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2

    by_id = {p["id"]: p for p in body}
    assert by_id[player_x_id]["in_my_roster"] is True
    assert by_id[player_y_id]["in_my_roster"] is False


def test_available_players_not_member() -> None:
    """User no es miembro de la liga → HTTP 403."""
    fl_chain = _chain(LEAGUE_BUDGET_PICK)
    lm_chain = _chain([])  # _get_member lanza 403 cuando data está vacío

    sb = _sb_multi(
        ("fantasy_leagues", fl_chain),
        ("league_members", lm_chain),
    )

    r = _client(sb).get(f"/roster/{LEAGUE_ID}/available-players")
    assert r.status_code == 403
