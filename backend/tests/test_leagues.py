"""Tests para /leagues — mockean Supabase y get_current_user, sin red."""
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
MEMBER_ID = str(uuid4())
COMPETITION_ID = str(uuid4())

LEAGUE = {
    "id": LEAGUE_ID,
    "name": "Mi Liga",
    "invite_code": "abc12345",
    "owner_id": USER_ID,
    "competition_id": COMPETITION_ID,
    "competitions": {"name": "LEC Spring 2026"},
    "budget": 100.0,
    "max_members": 10,
    "is_active": True,
}

MEMBER = {
    "id": MEMBER_ID,
    "user_id": USER_ID,
    "display_name": "Jaime",
    "remaining_budget": 100.0,
    "total_points": 0.0,
}

FAKE_USER = {"id": USER_ID, "email": "test@test.com"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_user() -> dict:
    return FAKE_USER


def _chain(*return_values: object) -> MagicMock:
    """
    Crea un query-builder mock que devuelve `return_values` en orden
    cada vez que se llama a .execute().
    """
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
    for method in ("select", "eq", "neq", "in_", "insert", "update", "delete", "single", "order", "limit", "ilike", "like"):
        getattr(chain, method).return_value = chain

    return chain


def _sb(*return_values: object) -> MagicMock:
    sb = MagicMock()
    sb.table.return_value = _chain(*return_values)
    return sb


def _sb_multi(*table_chains: tuple) -> MagicMock:
    """
    Permite definir respuestas distintas por tabla:
      _sb_multi(("league_members", chain1), ("fantasy_leagues", chain2))
    """
    mapping = {name: chain for name, chain in table_chains}
    sb = MagicMock()
    sb.table.side_effect = lambda name: mapping.get(name, _chain([]))
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
    c = TestClient(app, raise_server_exceptions=False)
    return c


# ---------------------------------------------------------------------------
# GET /leagues/
# ---------------------------------------------------------------------------

def test_list_leagues_returns_list() -> None:
    memberships = [{"league_id": LEAGUE_ID, "id": MEMBER_ID, "remaining_budget": 100.0, "total_points": 0.0, "display_name": None}]
    leagues = [LEAGUE]
    lm_chain = _chain(memberships)
    fl_chain = _chain(leagues)
    sb = _sb_multi(("league_members", lm_chain), ("fantasy_leagues", fl_chain))

    r = _client(sb).get("/leagues/")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert r.json()[0]["name"] == "Mi Liga"


def test_list_leagues_no_memberships_returns_empty() -> None:
    lm_chain = _chain([])
    sb = _sb_multi(("league_members", lm_chain))

    r = _client(sb).get("/leagues/")
    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# POST /leagues/
# ---------------------------------------------------------------------------

def test_create_league_returns_201() -> None:
    comp_chain = _chain([{"id": COMPETITION_ID, "name": "LEC Spring 2026"}])  # competitions lookup
    lm_chain = _chain(None)   # insert member
    fl_chain = _chain([LEAGUE])  # insert league
    sb = _sb_multi(
        ("competitions", comp_chain),
        ("fantasy_leagues", fl_chain),
        ("league_members", lm_chain),
    )

    r = _client(sb).post("/leagues/", json={"name": "Nueva Liga"})
    assert r.status_code == 201
    assert r.json()["name"] == "Mi Liga"


def test_create_league_name_too_short() -> None:
    sb = _sb([LEAGUE])
    r = _client(sb).post("/leagues/", json={"name": "ab"})
    assert r.status_code == 422


def test_create_league_max_members_out_of_range() -> None:
    sb = _sb([LEAGUE])
    r = _client(sb).post("/leagues/", json={"name": "Liga X", "max_members": 1})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /leagues/{league_id}
# ---------------------------------------------------------------------------

def test_get_league_ok() -> None:
    member_check = _chain([{"id": MEMBER_ID, "remaining_budget": 100.0, "total_points": 0.0, "display_name": None}])
    league_detail = _chain(LEAGUE)               # single()
    sb = _sb_multi(
        ("league_members", member_check),
        ("fantasy_leagues", league_detail),
    )

    r = _client(sb).get(f"/leagues/{LEAGUE_ID}")
    assert r.status_code == 200
    assert r.json()["id"] == LEAGUE_ID


def test_get_league_not_member_returns_403() -> None:
    member_check = _chain([])   # usuario no es miembro
    sb = _sb_multi(("league_members", member_check))

    r = _client(sb).get(f"/leagues/{LEAGUE_ID}")
    assert r.status_code == 403


def test_get_league_invalid_uuid() -> None:
    sb = _sb([])
    r = _client(sb).get("/leagues/no-es-uuid")
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# POST /leagues/{league_id}/join
# ---------------------------------------------------------------------------

def test_join_league_ok() -> None:
    fl_chain = _chain(LEAGUE)
    lm_chain = _chain(
        [],        # existing member check → no es miembro
        [],        # count members → liga no llena
        [MEMBER],  # insert → nuevo miembro
    )
    sb = _sb_multi(
        ("fantasy_leagues", fl_chain),
        ("league_members", lm_chain),
    )

    r = _client(sb).post(
        f"/leagues/{LEAGUE_ID}/join",
        json={"invite_code": "abc12345"},
    )
    assert r.status_code == 201


def test_join_league_wrong_invite_code() -> None:
    fl_chain = _chain(LEAGUE)
    sb = _sb_multi(("fantasy_leagues", fl_chain))

    r = _client(sb).post(
        f"/leagues/{LEAGUE_ID}/join",
        json={"invite_code": "WRONG"},
    )
    assert r.status_code == 403


def test_join_league_already_member() -> None:
    fl_chain = _chain(LEAGUE)
    lm_chain = _chain([{"id": MEMBER_ID}])  # ya existe
    sb = _sb_multi(
        ("fantasy_leagues", fl_chain),
        ("league_members", lm_chain),
    )

    r = _client(sb).post(
        f"/leagues/{LEAGUE_ID}/join",
        json={"invite_code": "abc12345"},
    )
    assert r.status_code == 409


def test_join_league_full() -> None:
    full_league = {**LEAGUE, "max_members": 1}
    fl_chain = _chain(full_league)
    lm_chain = _chain(
        [],                    # not member yet
        [{"id": str(uuid4())}],  # count = 1 → llena
    )
    sb = _sb_multi(
        ("fantasy_leagues", fl_chain),
        ("league_members", lm_chain),
    )

    r = _client(sb).post(
        f"/leagues/{LEAGUE_ID}/join",
        json={"invite_code": "abc12345"},
    )
    assert r.status_code == 400


def test_join_league_inactive() -> None:
    inactive = {**LEAGUE, "is_active": False}
    fl_chain = _chain(inactive)
    sb = _sb_multi(("fantasy_leagues", fl_chain))

    r = _client(sb).post(
        f"/leagues/{LEAGUE_ID}/join",
        json={"invite_code": "abc12345"},
    )
    assert r.status_code == 400
