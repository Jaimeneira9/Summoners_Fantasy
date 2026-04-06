"""
Tests de market/price_updater.py — usa mocks de supabase, sin DB ni red.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from market.price_updater import (
    CAP_DOWN,
    CAP_UP,
    PRICE_FLOOR,
    ROLLING_WINDOW,
    SENSITIVITY,
    _calculate_league_avg_efficiency,
    update_player_prices_post_series,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _SupabaseMock:
    """
    Wrapper del mock de supabase que expone las tablas capturadas para
    inspección en tests.
    """

    def __init__(self, supabase: MagicMock, tables: dict[str, MagicMock]) -> None:
        self._supabase = supabase
        self._tables = tables

    def __getattr__(self, name: str):
        return getattr(self._supabase, name)

    def table(self, name: str) -> MagicMock:
        return self._supabase.table(name)

    def get_table(self, name: str) -> MagicMock:
        return self._tables[name]


def _build_player_chain(player_data: dict) -> MagicMock:
    """Construye la cadena mock para players.select().eq().single().execute()."""
    player_exec = MagicMock()
    player_exec.data = player_data

    player_single = MagicMock()
    player_single.execute.return_value = player_exec

    player_eq = MagicMock()
    player_eq.single.return_value = player_single

    player_select = MagicMock()
    player_select.eq.return_value = player_eq

    return player_select


def _build_stats_chain(game_points: list[float]) -> MagicMock:
    """Construye la cadena mock para player_game_stats.select().eq().order().limit().execute()."""
    stats_exec = MagicMock()
    stats_exec.data = [{"game_points": pts} for pts in game_points]

    stats_limit = MagicMock()
    stats_limit.execute.return_value = stats_exec

    stats_order = MagicMock()
    stats_order.limit.return_value = stats_limit

    stats_eq = MagicMock()
    stats_eq.order.return_value = stats_order

    stats_select = MagicMock()
    stats_select.eq.return_value = stats_eq

    return stats_select


def _build_update_chain() -> tuple[MagicMock, MagicMock]:
    """Construye la cadena mock para .update().eq().execute(). Devuelve (table_mock, update_chain)."""
    update_exec = MagicMock()
    update_exec.data = None

    update_eq = MagicMock()
    update_eq.execute.return_value = update_exec

    update_chain = MagicMock()
    update_chain.eq.return_value = update_eq

    return update_chain


def _make_supabase_multi(
    players: list[dict],
    *,
    roster_data: list[dict] | None = None,
) -> _SupabaseMock:
    """
    Construye un mock de supabase para múltiples jugadores.

    Cada elemento de `players` debe tener:
        id: str
        current_price: float
        game_points: list[float]
        price_history: list (opcional, default [])

    El routing de player lookups y stats lookups por player_id se hace
    mediante side_effects en la cadena de llamadas.
    """
    # Indexar jugadores por id para routing
    players_by_id = {p["id"]: p for p in players}

    # --- players table ---
    players_table = MagicMock()
    stats_table = MagicMock()
    candidates_table = MagicMock()
    roster_table = MagicMock()

    # select() en players table: el código llama .select().eq(id, player_id).single().execute()
    # Necesitamos que cada llamada a .eq() devuelva el jugador correcto.
    # Implementamos con side_effect en .eq() que inspeccionan el player_id.
    def players_select_eq_side_effect(col, val):
        player = players_by_id.get(val)
        exec_mock = MagicMock()
        exec_mock.data = (
            {
                "current_price": player["current_price"],
                "price_history": player.get("price_history", []),
            }
            if player
            else None
        )
        single_mock = MagicMock()
        single_mock.execute.return_value = exec_mock
        eq_mock = MagicMock()
        eq_mock.single.return_value = single_mock
        return eq_mock

    players_select = MagicMock()
    players_select.eq.side_effect = players_select_eq_side_effect
    players_table.select.return_value = players_select

    # update() en players table
    players_update_chain = _build_update_chain()
    players_table.update.return_value = players_update_chain

    # --- player_game_stats table ---
    def stats_select_eq_side_effect(col, val):
        player = players_by_id.get(val)
        game_points = player.get("game_points", []) if player else []
        exec_mock = MagicMock()
        exec_mock.data = [{"game_points": pts} for pts in game_points]
        limit_mock = MagicMock()
        limit_mock.execute.return_value = exec_mock
        order_mock = MagicMock()
        order_mock.limit.return_value = limit_mock
        eq_mock = MagicMock()
        eq_mock.order.return_value = order_mock
        return eq_mock

    stats_select = MagicMock()
    stats_select.eq.side_effect = stats_select_eq_side_effect
    stats_table.select.return_value = stats_select

    # --- market_candidates table ---
    candidates_update_chain = _build_update_chain()
    candidates_table.update.return_value = candidates_update_chain

    # --- roster_players table ---
    rp_exec = MagicMock()
    rp_exec.data = roster_data or []
    rp_eq = MagicMock()
    rp_eq.execute.return_value = rp_exec
    rp_select = MagicMock()
    rp_select.eq.return_value = rp_eq
    roster_table.select.return_value = rp_select

    roster_update_chain = _build_update_chain()
    roster_table.update.return_value = roster_update_chain

    captured = {
        "players": players_table,
        "player_game_stats": stats_table,
        "market_candidates": candidates_table,
        "roster_players": roster_table,
    }

    supabase = MagicMock()

    def table_side_effect(name: str) -> MagicMock:
        return captured.get(name, MagicMock())

    supabase.table.side_effect = table_side_effect
    return _SupabaseMock(supabase, captured)


def _make_supabase(
    *,
    current_price: float = 20.0,
    price_history: list | None = None,
    game_points: list[float] | None = None,
    league_peer_price: float = 20.0,
    league_peer_points: list[float] | None = None,
) -> _SupabaseMock:
    """
    Helper de conveniencia para tests de un solo jugador.

    Para que league_avg tenga sentido, se puede configurar un peer con
    league_peer_price / league_peer_points. Si no se especifica, el peer
    tendrá la misma eficiencia que el jugador principal (→ delta=0).
    """
    if league_peer_points is None:
        # Mismo ratio pts/precio que el jugador principal → delta=0 en el principal
        main_pts = (game_points or [20.0])
        main_avg = sum(main_pts) / len(main_pts) if main_pts else 20.0
        main_eff = main_avg / current_price
        league_peer_points = [main_eff * league_peer_price]

    return _make_supabase_multi([
        {
            "id": "player-1",
            "current_price": current_price,
            "price_history": price_history or [],
            "game_points": game_points or [],
        },
        {
            "id": "peer-player",
            "current_price": league_peer_price,
            "price_history": [],
            "game_points": league_peer_points,
        },
    ])


# ---------------------------------------------------------------------------
# Tests — fórmula de eficiencia relativa (adaptados de la suite anterior)
# ---------------------------------------------------------------------------


def test_price_increases_when_above_league_avg():
    """Jugador más eficiente que la media de liga → precio sube."""
    # P1: eff=3.0 pts/M, P2: eff=1.0 pts/M → league_avg=2.0 → P1 sube
    supabase = _make_supabase_multi([
        {"id": "p1", "current_price": 10.0, "game_points": [30.0, 30.0, 30.0], "price_history": []},
        {"id": "p2", "current_price": 20.0, "game_points": [20.0, 20.0, 20.0], "price_history": []},
    ])
    update_player_prices_post_series(supabase, ["p1", "p2"])

    players_table = supabase.get_table("players")
    # Múltiples calls a update() — el primero es p1 (eff alta)
    update_calls = players_table.update.call_args_list
    p1_payload = update_calls[0][0][0]
    assert p1_payload["current_price"] > 10.0
    assert p1_payload["last_price_change_pct"] > 0


def test_price_decreases_when_below_league_avg():
    """Jugador menos eficiente que la media de liga → precio baja."""
    # P1: eff=3.0 pts/M, P2: eff=1.0 pts/M → league_avg=2.0 → P2 baja
    supabase = _make_supabase_multi([
        {"id": "p1", "current_price": 10.0, "game_points": [30.0, 30.0, 30.0], "price_history": []},
        {"id": "p2", "current_price": 20.0, "game_points": [20.0, 20.0, 20.0], "price_history": []},
    ])
    update_player_prices_post_series(supabase, ["p1", "p2"])

    players_table = supabase.get_table("players")
    update_calls = players_table.update.call_args_list
    p2_payload = update_calls[1][0][0]
    assert p2_payload["current_price"] < 20.0
    assert p2_payload["last_price_change_pct"] < 0


def test_price_floor_at_8():
    """Precio mínimo absoluto es 8.0 incluso con caída extrema."""
    # P1 a 9.0, P2 con eff muy alta → P1 cae pero no puede bajar de 8.0
    # P1: eff=0.1/9=0.011, P2: eff=100/10=10 → league_avg≈5.0 → P1 cae mucho
    supabase = _make_supabase_multi([
        {"id": "p1", "current_price": 9.0, "game_points": [0.1, 0.1, 0.1], "price_history": []},
        {"id": "p2", "current_price": 10.0, "game_points": [100.0, 100.0, 100.0], "price_history": []},
    ])
    update_player_prices_post_series(supabase, ["p1", "p2"])

    players_table = supabase.get_table("players")
    update_calls = players_table.update.call_args_list
    p1_payload = update_calls[0][0][0]
    assert p1_payload["current_price"] >= PRICE_FLOOR


def test_no_update_when_no_stats():
    """Sin stats en player_game_stats → ningún UPDATE llamado para ese jugador."""
    supabase = _make_supabase_multi([
        {"id": "p1", "current_price": 20.0, "game_points": [], "price_history": []},
        # Solo 1 jugador, sin stats → league_avg = 0 → return early
    ])
    update_player_prices_post_series(supabase, ["p1"])

    players_table = supabase.get_table("players")
    players_table.update.assert_not_called()

    candidates_table = supabase.get_table("market_candidates")
    candidates_table.update.assert_not_called()


def test_history_bounded_to_90():
    """price_history no crece más allá de 90 entradas."""
    existing_history = [{"date": f"2025-01-{i:02d}", "price": 10.0, "delta_pct": 0.01} for i in range(1, 91)]
    supabase = _make_supabase_multi([
        {"id": "p1", "current_price": 10.0, "game_points": [30.0, 30.0, 30.0], "price_history": existing_history},
        {"id": "p2", "current_price": 20.0, "game_points": [20.0, 20.0, 20.0], "price_history": []},
    ])
    update_player_prices_post_series(supabase, ["p1", "p2"])

    players_table = supabase.get_table("players")
    update_calls = players_table.update.call_args_list
    p1_payload = update_calls[0][0][0]
    assert len(p1_payload["price_history"]) == 90


def test_candidates_ask_price_synced():
    """Después del update de precio, market_candidates.update es llamado con el nuevo precio."""
    supabase = _make_supabase_multi([
        {"id": "p1", "current_price": 10.0, "game_points": [30.0, 30.0, 30.0], "price_history": []},
        {"id": "p2", "current_price": 20.0, "game_points": [20.0, 20.0, 20.0], "price_history": []},
    ])
    update_player_prices_post_series(supabase, ["p1", "p2"])

    candidates_table = supabase.get_table("market_candidates")
    assert candidates_table.update.call_count >= 1
    candidates_payload = candidates_table.update.call_args_list[0][0][0]
    assert "ask_price" in candidates_payload
    assert candidates_payload["ask_price"] > 10.0  # p1 subió


def test_delta_capped_at_cap_up():
    """delta_pct no puede superar CAP_UP aunque la eficiencia sea extrema."""
    # P1 eff muy alta vs P2 eff muy baja
    supabase = _make_supabase_multi([
        {"id": "p1", "current_price": 8.0, "game_points": [9999.0, 9999.0, 9999.0], "price_history": []},
        {"id": "p2", "current_price": 8.0, "game_points": [0.1, 0.1, 0.1], "price_history": []},
    ])
    update_player_prices_post_series(supabase, ["p1", "p2"])

    players_table = supabase.get_table("players")
    p1_payload = players_table.update.call_args_list[0][0][0]
    assert p1_payload["last_price_change_pct"] <= CAP_UP


def test_delta_capped_at_cap_down():
    """delta_pct no puede bajar de CAP_DOWN aunque la eficiencia sea casi cero."""
    supabase = _make_supabase_multi([
        {"id": "p1", "current_price": 8.0, "game_points": [0.1, 0.1, 0.1], "price_history": []},
        {"id": "p2", "current_price": 8.0, "game_points": [9999.0, 9999.0, 9999.0], "price_history": []},
    ])
    update_player_prices_post_series(supabase, ["p1", "p2"])

    players_table = supabase.get_table("players")
    p1_payload = players_table.update.call_args_list[0][0][0]
    assert p1_payload["last_price_change_pct"] >= CAP_DOWN


def test_update_player_prices_isolates_failures():
    """Un fallo en un jugador no impide que el resto se procese."""
    call_count = 0

    def table_side_effect_failing(name: str) -> MagicMock:
        nonlocal call_count
        call_count += 1
        raise RuntimeError("DB exploded")

    supabase = MagicMock()
    supabase.table.side_effect = table_side_effect_failing

    # No debe propagar la excepción
    update_player_prices_post_series(supabase, ["bad-player"])
    # El mock fue llamado (intentó procesar) y no explotó hacia afuera
    assert call_count >= 1


# ---------------------------------------------------------------------------
# Tests nuevos — T-01 a T-14 del spec
# ---------------------------------------------------------------------------


def test_T01_efficient_player_price_increases():
    """T-01: Jugador más eficiente que la media → precio sube."""
    # P1: current_price=10.0, recent_avg=30.0 → eff=3.0 pts/M
    # P2: current_price=20.0, recent_avg=20.0 → eff=1.0 pts/M
    # league_avg = (3.0 + 1.0) / 2 = 2.0
    # P1: eff_ratio = (3.0 - 2.0) / 2.0 = 0.5 → delta = min(0.5 * 0.375, 0.20) = 0.1875
    # new_price = round(10.0 * 1.1875, 2) = 11.88 (rounded to 2 decimals)
    supabase = _make_supabase_multi([
        {"id": "p1", "current_price": 10.0, "game_points": [30.0, 30.0, 30.0], "price_history": []},
        {"id": "p2", "current_price": 20.0, "game_points": [20.0, 20.0, 20.0], "price_history": []},
    ])
    update_player_prices_post_series(supabase, ["p1", "p2"])

    players_table = supabase.get_table("players")
    p1_payload = players_table.update.call_args_list[0][0][0]
    assert abs(p1_payload["current_price"] - 11.88) < 0.001
    assert abs(p1_payload["last_price_change_pct"] - 0.1875) < 0.0001


def test_T02_inefficient_player_price_decreases():
    """T-02: Jugador menos eficiente que la media → precio baja."""
    # Mismo lote que T-01
    # P2: eff_ratio = (1.0 - 2.0) / 2.0 = -0.5 → delta = max(-0.5 * 0.375, -0.20) = -0.1875
    # expected new_price = 20.0 * 0.8125 = 16.25
    supabase = _make_supabase_multi([
        {"id": "p1", "current_price": 10.0, "game_points": [30.0, 30.0, 30.0], "price_history": []},
        {"id": "p2", "current_price": 20.0, "game_points": [20.0, 20.0, 20.0], "price_history": []},
    ])
    update_player_prices_post_series(supabase, ["p1", "p2"])

    players_table = supabase.get_table("players")
    p2_payload = players_table.update.call_args_list[1][0][0]
    assert abs(p2_payload["current_price"] - 16.25) < 0.001
    assert abs(p2_payload["last_price_change_pct"] - (-0.1875)) < 0.0001


def test_T03_equal_efficiency_no_price_change():
    """T-03: Jugador con eficiencia igual a la media → precio sin cambio."""
    # 2 jugadores con misma eff=2.0 → eff_ratio=0 → delta=0
    supabase = _make_supabase_multi([
        {"id": "p1", "current_price": 10.0, "game_points": [20.0, 20.0, 20.0], "price_history": []},
        {"id": "p2", "current_price": 20.0, "game_points": [40.0, 40.0, 40.0], "price_history": []},
    ])
    update_player_prices_post_series(supabase, ["p1", "p2"])

    players_table = supabase.get_table("players")
    for call in players_table.update.call_args_list:
        payload = call[0][0]
        assert payload["last_price_change_pct"] == 0.0
        # new_price debe ser igual al current_price original (dentro del redondeo)
        assert payload["current_price"] in (10.0, 20.0)


def test_T04_single_player_no_price_change():
    """T-04: Liga con un solo jugador → precio sin cambio."""
    # Lote de 1 → league_avg == player_eff → eff_ratio=0 → delta=0
    supabase = _make_supabase_multi([
        {"id": "p1", "current_price": 15.0, "game_points": [30.0, 30.0, 30.0], "price_history": []},
    ])
    update_player_prices_post_series(supabase, ["p1"])

    players_table = supabase.get_table("players")
    p1_payload = players_table.update.call_args_list[0][0][0]
    assert p1_payload["last_price_change_pct"] == 0.0
    assert p1_payload["current_price"] == 15.0


def test_T05_delta_capped_at_new_cap_up():
    """T-05: Eficiencia extremamente positiva → capped a CAP_UP=0.20."""
    supabase = _make_supabase_multi([
        {"id": "p1", "current_price": 8.0, "game_points": [9999.0, 9999.0, 9999.0], "price_history": []},
        {"id": "p2", "current_price": 8.0, "game_points": [0.1, 0.1, 0.1], "price_history": []},
    ])
    update_player_prices_post_series(supabase, ["p1", "p2"])

    players_table = supabase.get_table("players")
    p1_payload = players_table.update.call_args_list[0][0][0]
    assert p1_payload["last_price_change_pct"] == CAP_UP


def test_T06_delta_capped_at_new_cap_down():
    """T-06: Eficiencia extremamente negativa → capped a CAP_DOWN=-0.20."""
    supabase = _make_supabase_multi([
        {"id": "p1", "current_price": 8.0, "game_points": [0.1, 0.1, 0.1], "price_history": []},
        {"id": "p2", "current_price": 8.0, "game_points": [9999.0, 9999.0, 9999.0], "price_history": []},
    ])
    update_player_prices_post_series(supabase, ["p1", "p2"])

    players_table = supabase.get_table("players")
    p1_payload = players_table.update.call_args_list[0][0][0]
    assert p1_payload["last_price_change_pct"] == CAP_DOWN


def test_T07_price_floor_8_applied():
    """T-07: Caída extrema → new_price no puede quedar por debajo de 8.0."""
    # current_price=9.0, delta=-0.20 → 9.0 * 0.80 = 7.2 → floor a 8.0
    supabase = _make_supabase_multi([
        {"id": "p1", "current_price": 9.0, "game_points": [0.1, 0.1, 0.1], "price_history": []},
        {"id": "p2", "current_price": 9.0, "game_points": [9999.0, 9999.0, 9999.0], "price_history": []},
    ])
    update_player_prices_post_series(supabase, ["p1", "p2"])

    players_table = supabase.get_table("players")
    p1_payload = players_table.update.call_args_list[0][0][0]
    assert p1_payload["current_price"] == PRICE_FLOOR


def test_T08_no_stats_no_update():
    """T-08: Jugador sin stats → skip sin UPDATE en DB."""
    # Solo p1 sin stats — league_avg = 0 → return early
    supabase = _make_supabase_multi([
        {"id": "p1", "current_price": 15.0, "game_points": [], "price_history": []},
    ])
    update_player_prices_post_series(supabase, ["p1"])

    players_table = supabase.get_table("players")
    players_table.update.assert_not_called()

    candidates_table = supabase.get_table("market_candidates")
    candidates_table.update.assert_not_called()


def test_T09_partial_stats_used():
    """T-09: Jugador con 1 partida (menos que ROLLING_WINDOW=3) → usa el dato disponible."""
    # P1 solo tiene 1 partida, pero debe ser procesado normalmente
    supabase = _make_supabase_multi([
        {"id": "p1", "current_price": 10.0, "game_points": [25.0], "price_history": []},
        {"id": "p2", "current_price": 20.0, "game_points": [20.0, 20.0, 20.0], "price_history": []},
    ])
    update_player_prices_post_series(supabase, ["p1", "p2"])

    # P1: recent_avg=25.0, current_price=10.0 → eff=2.5
    # P2: recent_avg=20.0, current_price=20.0 → eff=1.0
    # league_avg = (2.5 + 1.0) / 2 = 1.75 → P1 sube
    players_table = supabase.get_table("players")
    assert players_table.update.call_count >= 1
    p1_payload = players_table.update.call_args_list[0][0][0]
    assert p1_payload["current_price"] > 10.0


def test_T10_all_same_efficiency_no_change():
    """T-10: Todos los jugadores con la misma eficiencia → todos delta=0."""
    # 3 jugadores con eff=2.0 cada uno
    supabase = _make_supabase_multi([
        {"id": "p1", "current_price": 10.0, "game_points": [20.0, 20.0, 20.0], "price_history": []},
        {"id": "p2", "current_price": 15.0, "game_points": [30.0, 30.0, 30.0], "price_history": []},
        {"id": "p3", "current_price": 20.0, "game_points": [40.0, 40.0, 40.0], "price_history": []},
    ])
    update_player_prices_post_series(supabase, ["p1", "p2", "p3"])

    players_table = supabase.get_table("players")
    for call in players_table.update.call_args_list:
        payload = call[0][0]
        assert payload["last_price_change_pct"] == 0.0


def test_T11_rolling_window_is_3():
    """T-11: ROLLING_WINDOW=3 — la query usa limit(3)."""
    assert ROLLING_WINDOW == 3

    supabase = _make_supabase_multi([
        {"id": "p1", "current_price": 10.0, "game_points": [20.0], "price_history": []},
    ])

    # Capturar los mocks internos para inspeccionar el limit
    captured_limits = []

    original_side_effect = supabase._supabase.table.side_effect

    def instrumented_table(name):
        t = original_side_effect(name)
        if name == "player_game_stats":
            # Guardar referencia al select para capturar el limit llamado
            original_select = t.select

            def instrumented_select(*args, **kwargs):
                sel = original_select(*args, **kwargs)
                original_eq = sel.eq

                def instrumented_eq(col, val):
                    eq = original_eq(col, val)
                    original_order = eq.order

                    def instrumented_order(*a, **kw):
                        ord_mock = original_order(*a, **kw)
                        original_limit = ord_mock.limit

                        def instrumented_limit(n):
                            captured_limits.append(n)
                            return original_limit(n)

                        ord_mock.limit = instrumented_limit
                        return ord_mock

                    eq.order = instrumented_order
                    return eq

                sel.eq = instrumented_eq
                return sel

            t.select = instrumented_select
        return t

    supabase._supabase.table.side_effect = instrumented_table

    update_player_prices_post_series(supabase, ["p1"])

    assert all(lim == 3 for lim in captured_limits), f"Expected limit(3), got {captured_limits}"


def test_T12_market_candidates_synced():
    """T-12: market_candidates.ask_price sincronizado con el nuevo precio."""
    # P1 sube de 10.0 → debería llamar market_candidates.update con nuevo precio
    supabase = _make_supabase_multi([
        {"id": "p1", "current_price": 10.0, "game_points": [30.0, 30.0, 30.0], "price_history": []},
        {"id": "p2", "current_price": 20.0, "game_points": [20.0, 20.0, 20.0], "price_history": []},
    ])
    update_player_prices_post_series(supabase, ["p1", "p2"])

    candidates_table = supabase.get_table("market_candidates")
    assert candidates_table.update.call_count == 2

    # P1: new_price = round(10.0 * 1.1875, 2) = 11.88
    p1_candidates_payload = candidates_table.update.call_args_list[0][0][0]
    assert "ask_price" in p1_candidates_payload
    assert abs(p1_candidates_payload["ask_price"] - 11.88) < 0.001


def test_T13_idempotency_skip_on_same_date():
    """T-13: Segunda llamada con mismo series_date → NO actualiza datos."""
    today = "2026-04-06"
    existing_history = [{"date": today, "price": 10.0, "delta_pct": 0.05}]

    supabase = _make_supabase_multi([
        {"id": "p1", "current_price": 10.0, "game_points": [30.0, 30.0, 30.0], "price_history": existing_history},
        {"id": "p2", "current_price": 20.0, "game_points": [20.0, 20.0, 20.0], "price_history": existing_history},
    ])

    # Parchear datetime.now para devolver la misma fecha que ya está en history
    from datetime import date, timezone as tz
    mock_date = MagicMock()
    mock_date.isoformat.return_value = today

    with patch("market.price_updater.datetime") as mock_dt:
        mock_dt.now.return_value.date.return_value = mock_date
        update_player_prices_post_series(supabase, ["p1", "p2"])

    players_table = supabase.get_table("players")
    players_table.update.assert_not_called()

    candidates_table = supabase.get_table("market_candidates")
    candidates_table.update.assert_not_called()


def test_T14_idempotency_processes_new_date():
    """T-14: Primera llamada con fecha nueva → SÍ actualiza datos."""
    old_date = "2026-03-30"
    new_date = "2026-04-06"
    existing_history = [{"date": old_date, "price": 10.0, "delta_pct": 0.05}]

    supabase = _make_supabase_multi([
        {"id": "p1", "current_price": 10.0, "game_points": [30.0, 30.0, 30.0], "price_history": existing_history},
        {"id": "p2", "current_price": 20.0, "game_points": [20.0, 20.0, 20.0], "price_history": existing_history},
    ])

    mock_date = MagicMock()
    mock_date.isoformat.return_value = new_date

    with patch("market.price_updater.datetime") as mock_dt:
        mock_dt.now.return_value.date.return_value = mock_date
        update_player_prices_post_series(supabase, ["p1", "p2"])

    players_table = supabase.get_table("players")
    # Ambos jugadores deben haber sido actualizados
    assert players_table.update.call_count == 2

    candidates_table = supabase.get_table("market_candidates")
    assert candidates_table.update.call_count == 2


# ---------------------------------------------------------------------------
# Tests unitarios de helpers
# ---------------------------------------------------------------------------


def test_calculate_league_avg_empty():
    """_calculate_league_avg_efficiency([]) → 0.0."""
    assert _calculate_league_avg_efficiency([]) == 0.0


def test_calculate_league_avg_single():
    """_calculate_league_avg_efficiency([X]) → X."""
    assert _calculate_league_avg_efficiency([2.0]) == 2.0


def test_calculate_league_avg_multiple():
    """_calculate_league_avg_efficiency([3.0, 1.0]) → 2.0."""
    assert _calculate_league_avg_efficiency([3.0, 1.0]) == 2.0


def test_calculate_league_avg_all_same():
    """_calculate_league_avg_efficiency([2.0, 2.0, 2.0]) → 2.0."""
    assert _calculate_league_avg_efficiency([2.0, 2.0, 2.0]) == 2.0


# ---------------------------------------------------------------------------
# Tests de constantes
# ---------------------------------------------------------------------------


def test_constants_values():
    """Verificar que las constantes definitivas tienen los valores correctos."""
    assert ROLLING_WINDOW == 3
    assert SENSITIVITY == 0.375
    assert CAP_UP == 0.20
    assert CAP_DOWN == -0.20
    assert PRICE_FLOOR == 8.0
