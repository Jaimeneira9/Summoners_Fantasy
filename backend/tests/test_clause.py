"""Tests para activate_clause — POST /market/{league_id}/clause/{roster_player_id}/activate."""
from datetime import datetime, timedelta, timezone
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
BUYER_MEMBER_ID = str(uuid4())
OWNER_MEMBER_ID = str(uuid4())
PLAYER_ID = str(uuid4())
ROSTER_PLAYER_ID = str(uuid4())
BUYER_ROSTER_ID = str(uuid4())

FAKE_USER = {"id": USER_ID, "email": "test@test.com"}

BUYER_MEMBER = {"id": BUYER_MEMBER_ID, "remaining_budget": 100.0}

# clause_expires_at en el PASADO: protección expirada → se puede activar la cláusula
PAST_EXPIRES = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
# clause_expires_at en el FUTURO: protección activa → NO se puede activar la cláusula
FUTURE_EXPIRES = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

# Roster player con protección EXPIRADA (estado correcto para activar cláusula)
ROSTER_PLAYER = {
    "id": ROSTER_PLAYER_ID,
    "player_id": PLAYER_ID,
    "clause_expires_at": PAST_EXPIRES,
    "clause_amount": 15.0,
    "rosters": {
        "member_id": OWNER_MEMBER_ID,
        "league_members": {"league_id": LEAGUE_ID},
    },
}

# current_price > clause_amount: la nueva cláusula debe ser MAX(15.0, 18.0) = 18.0
PLAYER = {"current_price": 18.0, "role": "mid"}

BUYER_ROSTER = {"id": BUYER_ROSTER_ID}

# ---------------------------------------------------------------------------
# Helpers — mismo patrón que test_market.py
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
    for method in (
        "select", "eq", "in_", "insert", "single", "order", "limit",
        "update", "delete", "gt", "gte", "lt", "lte", "neq", "is_",
        "not_", "or_", "filter",
    ):
        getattr(chain, method).return_value = chain

    return chain


def _sb_multi(*table_chains: tuple) -> MagicMock:
    mapping = {name: chain for name, chain in table_chains}
    sb = MagicMock()
    sb.table.side_effect = lambda name: mapping.get(name, _chain([]))
    return sb


def _client(sb: MagicMock) -> TestClient:
    app.dependency_overrides[get_supabase] = lambda: sb
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def override_user():
    app.dependency_overrides[get_current_user] = _mock_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Helpers de construcción de sb para activate_clause
#
# Secuencia de llamadas en activate_clause:
#   tabla league_members  → 1 execute  (_get_member: buyer)
#   tabla roster_players  → 4 executes (rp lookup, owned check, occupied slots, delete, insert)
#   tabla players         → 1 execute  (current_price)
#   tabla rosters         → 1 execute  (_get_roster: buyer)
#   rpc deduct_budget     → 1 execute
#   rpc add_budget        → 1 execute
#   tabla sell_offers     → 1 execute  (cancel pending)
#   tabla transactions    → 1 execute  (insert)
# ---------------------------------------------------------------------------


def _make_sb_happy_path() -> MagicMock:
    """Mocks para el flujo feliz: comprador rival activa la cláusula con éxito.

    ROSTER_PLAYER tiene clause_expires_at en el PASADO (protección expirada),
    que es el único estado en que la activación debe proceder.
    """
    # league_members: solo el buyer (1 execute en _get_member)
    lm_chain = _chain([BUYER_MEMBER])

    # roster_players (en orden de ejecución):
    #   1. rp lookup (con join)         → [ROSTER_PLAYER]
    #   2. owned check (buyer ya tiene?)→ []   (no lo tiene)
    #   3. occupied slots               → []   (roster vacío, bench_1 libre)
    #   4. delete (old rp)              → []
    #   5. insert (new rp)              → [{}]
    rp_chain = _chain([ROSTER_PLAYER], [], [], [], [{}])

    # players: current_price lookup
    pl_chain = _chain([PLAYER])

    # rosters: _get_roster del comprador
    ro_chain = _chain([BUYER_ROSTER])

    # sell_offers: cancel pending
    so_chain = _chain([])

    # transactions: insert
    tx_chain = _chain([{}])

    sb = _sb_multi(
        ("league_members", lm_chain),
        ("roster_players", rp_chain),
        ("players", pl_chain),
        ("rosters", ro_chain),
        ("sell_offers", so_chain),
        ("transactions", tx_chain),
    )

    # rpc calls: deduct_budget → True (éxito), add_budget → None (no importa)
    deduct_result = MagicMock()
    deduct_result.data = True
    deduct_chain = MagicMock()
    deduct_chain.execute.return_value = deduct_result

    add_result = MagicMock()
    add_result.data = None
    add_chain = MagicMock()
    add_chain.execute.return_value = add_result

    def rpc_side_effect(fn_name: str, params: dict):
        if fn_name == "deduct_budget":
            return deduct_chain
        return add_chain

    sb.rpc.side_effect = rpc_side_effect
    return sb


# ---------------------------------------------------------------------------
# Happy path — rival activa la cláusula con éxito (protección expirada)
# ---------------------------------------------------------------------------


def test_activate_clause_ok() -> None:
    """Activación exitosa: protección expirada, presupuesto suficiente."""
    sb = _make_sb_happy_path()

    r = _client(sb).post(f"/market/{LEAGUE_ID}/clause/{ROSTER_PLAYER_ID}/activate")

    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["clause_amount"] == 15.0
    assert "new_clause_expires_at" in body

    # deduct_budget llamado con el importe correcto y el buyer_member_id correcto
    deduct_calls = [
        call for call in sb.rpc.call_args_list
        if call.args[0] == "deduct_budget"
    ]
    assert len(deduct_calls) == 1
    assert deduct_calls[0].args[1]["p_member_id"] == BUYER_MEMBER_ID
    assert deduct_calls[0].args[1]["p_amount"] == 15.0

    # add_budget llamado con el owner_member_id correcto
    add_calls = [
        call for call in sb.rpc.call_args_list
        if call.args[0] == "add_budget"
    ]
    assert len(add_calls) == 1
    assert add_calls[0].args[1]["p_member_id"] == OWNER_MEMBER_ID
    assert add_calls[0].args[1]["p_amount"] == 15.0

    # roster_players: el insert nuevo contiene clause_amount = MAX(price_paid=15.0, current_price=18.0) = 18.0
    rp_table = sb.table("roster_players")
    insert_calls = rp_table.insert.call_args_list
    assert insert_calls, "Se esperaba al menos un insert en roster_players"
    inserted_payload = insert_calls[-1].args[0]
    assert inserted_payload["clause_amount"] == 18.0, (
        f"clause_amount debe ser MAX(price_paid=15.0, current_price=18.0) = 18.0, "
        f"got {inserted_payload['clause_amount']}"
    )
    assert inserted_payload["price_paid"] == 15.0, (
        f"price_paid debe ser el clause_amount pagado (15.0), got {inserted_payload['price_paid']}"
    )
    assert inserted_payload["roster_id"] == BUYER_ROSTER_ID
    assert inserted_payload["player_id"] == PLAYER_ID

    # clause_expires_at debe ser ~14 días en el futuro (margen ±60 seg)
    expires_dt = datetime.fromisoformat(inserted_payload["clause_expires_at"])
    if expires_dt.tzinfo is None:
        expires_dt = expires_dt.replace(tzinfo=timezone.utc)
    expected = datetime.now(timezone.utc) + timedelta(days=14)
    assert abs((expires_dt - expected).total_seconds()) < 60


# ---------------------------------------------------------------------------
# Precio de cláusula no puede ser menor que price_paid
# ---------------------------------------------------------------------------


def test_activate_clause_new_clause_amount_ge_price_paid() -> None:
    """clause_amount >= price_paid siempre: cuando current_price < price_paid se usa price_paid."""
    # Jugador que bajó de precio: current_price < clause_amount (price_paid)
    cheap_player = {"current_price": 10.0, "role": "mid"}

    lm_chain = _chain([BUYER_MEMBER])
    rp_chain = _chain([ROSTER_PLAYER], [], [], [], [{}])
    pl_chain = _chain([cheap_player])
    ro_chain = _chain([BUYER_ROSTER])
    so_chain = _chain([])
    tx_chain = _chain([{}])

    sb = _sb_multi(
        ("league_members", lm_chain),
        ("roster_players", rp_chain),
        ("players", pl_chain),
        ("rosters", ro_chain),
        ("sell_offers", so_chain),
        ("transactions", tx_chain),
    )

    deduct_result = MagicMock()
    deduct_result.data = True
    deduct_chain = MagicMock()
    deduct_chain.execute.return_value = deduct_result

    add_result = MagicMock()
    add_result.data = None
    add_chain = MagicMock()
    add_chain.execute.return_value = add_result

    def rpc_side_effect(fn_name: str, params: dict):
        if fn_name == "deduct_budget":
            return deduct_chain
        return add_chain

    sb.rpc.side_effect = rpc_side_effect

    r = _client(sb).post(f"/market/{LEAGUE_ID}/clause/{ROSTER_PLAYER_ID}/activate")

    assert r.status_code == 200
    rp_table = sb.table("roster_players")
    insert_calls = rp_table.insert.call_args_list
    inserted_payload = insert_calls[-1].args[0]

    # clause_amount = MAX(price_paid=15.0, current_price=10.0) = 15.0
    assert inserted_payload["clause_amount"] == 15.0, (
        f"clause_amount debe ser MAX(price_paid=15.0, current_price=10.0) = 15.0, "
        f"got {inserted_payload['clause_amount']}"
    )
    assert inserted_payload["clause_amount"] >= inserted_payload["price_paid"], (
        "clause_amount nunca puede ser menor que price_paid"
    )


# ---------------------------------------------------------------------------
# Own clause guard — manager intenta activar la cláusula de su propio jugador
# ---------------------------------------------------------------------------


def test_activate_clause_own_player_returns_409() -> None:
    # El roster_player pertenece al mismo BUYER_MEMBER_ID
    own_rp = {
        **ROSTER_PLAYER,
        "rosters": {
            "member_id": BUYER_MEMBER_ID,  # mismo que el comprador
            "league_members": {"league_id": LEAGUE_ID},
        },
    }

    lm_chain = _chain([BUYER_MEMBER])
    rp_chain = _chain([own_rp])

    sb = _sb_multi(
        ("league_members", lm_chain),
        ("roster_players", rp_chain),
    )

    r = _client(sb).post(f"/market/{LEAGUE_ID}/clause/{ROSTER_PLAYER_ID}/activate")

    assert r.status_code == 409
    assert "tuyo" in r.json()["detail"].lower() or "propio" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Protection guard — clause_expires_at en el FUTURO → protección activa → 403
# ---------------------------------------------------------------------------


def test_activate_clause_during_protection_returns_403() -> None:
    """Intentar activar la cláusula mientras el jugador está en período de protección → 403."""
    protected_rp = {
        **ROSTER_PLAYER,
        "clause_expires_at": FUTURE_EXPIRES,  # protección activa
    }

    lm_chain = _chain([BUYER_MEMBER])
    rp_chain = _chain([protected_rp])

    sb = _sb_multi(
        ("league_members", lm_chain),
        ("roster_players", rp_chain),
    )

    r = _client(sb).post(f"/market/{LEAGUE_ID}/clause/{ROSTER_PLAYER_ID}/activate")

    assert r.status_code == 403
    assert "protección" in r.json()["detail"].lower() or "proteccion" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Insufficient budget — deduct_budget RPC devuelve False
# ---------------------------------------------------------------------------


def test_activate_clause_insufficient_budget_returns_402() -> None:
    lm_chain = _chain([BUYER_MEMBER])
    rp_chain = _chain([ROSTER_PLAYER], [], [])
    pl_chain = _chain([PLAYER])
    ro_chain = _chain([BUYER_ROSTER])

    sb = _sb_multi(
        ("league_members", lm_chain),
        ("roster_players", rp_chain),
        ("players", pl_chain),
        ("rosters", ro_chain),
    )

    # deduct_budget → False (presupuesto insuficiente)
    deduct_result = MagicMock()
    deduct_result.data = False
    deduct_chain = MagicMock()
    deduct_chain.execute.return_value = deduct_result
    sb.rpc.return_value = deduct_chain

    r = _client(sb).post(f"/market/{LEAGUE_ID}/clause/{ROSTER_PLAYER_ID}/activate")

    assert r.status_code == 402
    assert "presupuesto" in r.json()["detail"].lower() or "insuficiente" in r.json()["detail"].lower()
