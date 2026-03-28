"""
Tests de market/price_updater.py — usa mocks de supabase, sin DB ni red.
"""
from __future__ import annotations

from unittest.mock import MagicMock, call

from market.price_updater import (
    CAP_DOWN,
    CAP_UP,
    PRICE_FLOOR,
    ROLLING_WINDOW,
    SENSITIVITY,
    _update_single_player_price,
    update_player_prices_post_series,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _SupabaseMock:
    """
    Wrapper del mock de supabase que expone las tablas capturadas para
    inspección en tests. Necesario porque table_side_effect crea un mock
    nuevo en cada llamada — si el test vuelve a llamar supabase.table("players")
    después de la función, obtiene un objeto distinto al que usó el código real.
    """

    def __init__(self, supabase: MagicMock, tables: dict[str, MagicMock]) -> None:
        self._supabase = supabase
        self._tables = tables

    def __getattr__(self, name: str):
        return getattr(self._supabase, name)

    def table(self, name: str) -> MagicMock:
        """Delega al mock real para que el código de producción lo use."""
        return self._supabase.table(name)

    def get_table(self, name: str) -> MagicMock:
        """Devuelve el mock capturado la primera vez que se llamó table(name)."""
        return self._tables[name]


def _make_supabase(
    *,
    current_price: float = 20.0,
    avg_points_baseline: float | None = 30.0,
    price_history: list | None = None,
    game_points: list[float] | None = None,
) -> _SupabaseMock:
    """
    Construye un mock de supabase con los datos configurados.

    - players.select().eq().single().execute() → player data
    - player_game_stats.select().eq().order().limit().execute() → stats data
    - players.update().eq().execute() → None (no importa el retorno)
    - market_candidates.update().eq().execute() → None

    Retorna un _SupabaseMock que expone get_table(name) para inspeccionar
    los mocks reales usados por el código de producción.
    """
    supabase = MagicMock()

    player_data = {
        "current_price": current_price,
        "avg_points_baseline": avg_points_baseline,
        "price_history": price_history or [],
    }

    stats_data = [{"game_points": pts} for pts in (game_points or [])]

    # Cadena para players: .table().select().eq().single().execute()
    player_exec = MagicMock()
    player_exec.data = player_data

    player_single = MagicMock()
    player_single.execute.return_value = player_exec

    player_eq = MagicMock()
    player_eq.single.return_value = player_single

    player_select = MagicMock()
    player_select.eq.return_value = player_eq

    # Cadena para player_game_stats: .table().select().eq().order().limit().execute()
    stats_exec = MagicMock()
    stats_exec.data = stats_data

    stats_limit = MagicMock()
    stats_limit.execute.return_value = stats_exec

    stats_order = MagicMock()
    stats_order.limit.return_value = stats_limit

    stats_eq = MagicMock()
    stats_eq.order.return_value = stats_order

    stats_select = MagicMock()
    stats_select.eq.return_value = stats_eq

    # Cadena para players.update y market_candidates.update
    update_eq = MagicMock()
    update_eq.execute.return_value = MagicMock()

    update_chain = MagicMock()
    update_chain.eq.return_value = update_eq

    # Mocks de tabla fijos — se crean una sola vez y se reúsan en cada llamada
    players_table = MagicMock()
    players_table.select.return_value = player_select
    players_table.update.return_value = update_chain

    stats_table = MagicMock()
    stats_table.select.return_value = stats_select

    candidates_table = MagicMock()
    candidates_table.update.return_value = update_chain

    captured: dict[str, MagicMock] = {
        "players": players_table,
        "player_game_stats": stats_table,
        "market_candidates": candidates_table,
    }

    def table_side_effect(name: str) -> MagicMock:
        return captured.get(name, MagicMock())

    supabase.table.side_effect = table_side_effect
    return _SupabaseMock(supabase, captured)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_price_increases_when_above_baseline():
    """recent_avg > baseline → precio sube."""
    supabase = _make_supabase(
        current_price=20.0,
        avg_points_baseline=30.0,
        game_points=[50.0, 50.0, 50.0],  # recent_avg=50 > baseline=30
    )
    _update_single_player_price(supabase, "player-1")

    players_table = supabase.get_table("players")
    update_call_args = players_table.update.call_args
    payload = update_call_args[0][0]
    assert payload["current_price"] > 20.0
    assert payload["last_price_change_pct"] > 0


def test_price_decreases_when_below_baseline():
    """recent_avg < baseline → precio baja."""
    supabase = _make_supabase(
        current_price=20.0,
        avg_points_baseline=30.0,
        game_points=[10.0, 10.0, 10.0],  # recent_avg=10 < baseline=30
    )
    _update_single_player_price(supabase, "player-1")

    players_table = supabase.get_table("players")
    update_call_args = players_table.update.call_args
    payload = update_call_args[0][0]
    assert payload["current_price"] < 20.0
    assert payload["last_price_change_pct"] < 0


def test_price_floor_at_1():
    """Precio mínimo absoluto es 1.0 incluso con caída extrema."""
    supabase = _make_supabase(
        current_price=1.0,
        avg_points_baseline=999.0,
        game_points=[0.1, 0.1, 0.1],
    )
    _update_single_player_price(supabase, "player-1")

    players_table = supabase.get_table("players")
    update_call_args = players_table.update.call_args
    payload = update_call_args[0][0]
    assert payload["current_price"] >= PRICE_FLOOR


def test_no_update_when_no_stats():
    """Sin stats en player_game_stats → ningún UPDATE llamado."""
    supabase = _make_supabase(
        current_price=20.0,
        avg_points_baseline=30.0,
        game_points=[],  # sin datos
    )
    _update_single_player_price(supabase, "player-1")

    players_table = supabase.get_table("players")
    players_table.update.assert_not_called()

    candidates_table = supabase.get_table("market_candidates")
    candidates_table.update.assert_not_called()


def test_null_baseline_sets_baseline_no_price_change():
    """baseline=None → establece baseline, no mueve precio."""
    supabase = _make_supabase(
        current_price=20.0,
        avg_points_baseline=None,  # sin baseline
        game_points=[30.0, 30.0, 30.0],
    )
    _update_single_player_price(supabase, "player-1")

    players_table = supabase.get_table("players")
    update_call_args = players_table.update.call_args
    payload = update_call_args[0][0]

    # Solo debe actualizar avg_points_baseline, NO current_price
    assert "avg_points_baseline" in payload
    assert "current_price" not in payload

    candidates_table = supabase.get_table("market_candidates")
    candidates_table.update.assert_not_called()


def test_history_bounded_to_90():
    """price_history no crece más allá de 90 entradas."""
    existing_history = [{"date": "2025-01-01", "price": 10.0, "delta_pct": 0.01}] * 90
    supabase = _make_supabase(
        current_price=20.0,
        avg_points_baseline=30.0,
        price_history=existing_history,
        game_points=[50.0],
    )
    _update_single_player_price(supabase, "player-1")

    players_table = supabase.get_table("players")
    update_call_args = players_table.update.call_args
    payload = update_call_args[0][0]
    assert len(payload["price_history"]) == 90


def test_candidates_ask_price_synced():
    """Después del update de precio, market_candidates.update es llamado con el nuevo precio."""
    supabase = _make_supabase(
        current_price=20.0,
        avg_points_baseline=30.0,
        game_points=[50.0],
    )
    _update_single_player_price(supabase, "player-1")

    candidates_table = supabase.get_table("market_candidates")
    candidates_table.update.assert_called_once()
    candidates_payload = candidates_table.update.call_args[0][0]
    assert "ask_price" in candidates_payload
    assert candidates_payload["ask_price"] > 20.0  # precio subió


def test_delta_capped_at_cap_up():
    """delta_pct no puede superar CAP_UP aunque la performance sea extrema."""
    supabase = _make_supabase(
        current_price=20.0,
        avg_points_baseline=1.0,
        game_points=[9999.0],  # rendimiento absurdamente alto
    )
    _update_single_player_price(supabase, "player-1")

    players_table = supabase.table("players")
    payload = players_table.update.call_args[0][0]
    assert payload["last_price_change_pct"] <= CAP_UP


def test_delta_capped_at_cap_down():
    """delta_pct no puede bajar de CAP_DOWN aunque la performance sea cero."""
    supabase = _make_supabase(
        current_price=20.0,
        avg_points_baseline=9999.0,
        game_points=[0.1],  # rendimiento casi nulo
    )
    _update_single_player_price(supabase, "player-1")

    players_table = supabase.table("players")
    payload = players_table.update.call_args[0][0]
    assert payload["last_price_change_pct"] >= CAP_DOWN


def test_update_player_prices_isolates_failures():
    """Un fallo en un jugador no impide que el resto se procese."""
    good_supabase = _make_supabase(
        current_price=20.0,
        avg_points_baseline=30.0,
        game_points=[50.0],
    )

    # Forzar fallo en el primer jugador haciendo que table() lance excepción
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
