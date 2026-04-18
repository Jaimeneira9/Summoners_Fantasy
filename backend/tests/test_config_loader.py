"""
Tests de scoring/config_loader.py — sin DB ni red.

Patrón de mock: se construye la cadena de llamadas Supabase
  supabase.table(...).select(...).eq(...).eq(...).limit(1).execute()
  supabase.table(...).select(...).eq(...).not_.is_(...).limit(1).execute()
usando MagicMock con side_effect para distinguir por tabla/llamada.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from scoring.config_loader import (
    clear_weights_cache,
    get_multikill_bonuses,
    get_scoring_weights,
)
from scoring.engine import MULTIKILL_BONUS, ROLE_WEIGHTS


# ---------------------------------------------------------------------------
# Helpers de mock
# ---------------------------------------------------------------------------


def _make_supabase_weights(data: list[dict]) -> MagicMock:
    """
    Mock para get_scoring_weights:
      supabase.table("scoring_config").select("weights")
              .eq("competition_id", ...).eq("role", ...).limit(1).execute()
    """
    execute_result = MagicMock()
    execute_result.data = data

    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.ilike.return_value = chain
    chain.limit.return_value = chain
    chain.execute.return_value = execute_result

    sb = MagicMock()
    sb.table.return_value = chain
    return sb


def _make_supabase_multikill(data: list[dict]) -> MagicMock:
    """
    Mock para get_multikill_bonuses:
      supabase.table("scoring_config").select("multikill_bonuses")
              .eq("competition_id", ...).not_.is_("multikill_bonuses", "null")
              .limit(1).execute()
    """
    execute_result = MagicMock()
    execute_result.data = data

    not_chain = MagicMock()
    not_chain.is_.return_value = MagicMock(
        limit=MagicMock(
            return_value=MagicMock(execute=MagicMock(return_value=execute_result))
        )
    )

    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.ilike.return_value = chain
    chain.not_ = not_chain
    chain.limit.return_value = chain
    chain.execute.return_value = execute_result

    sb = MagicMock()
    sb.table.return_value = chain
    return sb


def _make_supabase_raising(exc: Exception) -> MagicMock:
    """Mock que lanza una excepción al llamar a execute()."""
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.ilike.return_value = chain
    chain.not_ = MagicMock()
    chain.not_.is_.return_value = chain
    chain.limit.return_value = chain
    chain.execute.side_effect = exc

    sb = MagicMock()
    sb.table.return_value = chain
    return sb


# ---------------------------------------------------------------------------
# setUp / tearDown — limpia cache entre tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_cache():
    """Limpia el cache antes y después de cada test para aislarlos."""
    clear_weights_cache()
    yield
    clear_weights_cache()


# ---------------------------------------------------------------------------
# T1.5-a  fallback cuando no hay fila en DB
# ---------------------------------------------------------------------------


def test_get_scoring_weights_fallback_when_no_db_row():
    """Sin fila en DB, debe devolver ROLE_WEIGHTS[role]."""
    sb = _make_supabase_weights(data=[])
    result = get_scoring_weights(sb, "comp-lec", "mid")
    assert result == ROLE_WEIGHTS["mid"]


# ---------------------------------------------------------------------------
# T1.5-b  retorna DB weights cuando hay fila
# ---------------------------------------------------------------------------


def test_get_scoring_weights_returns_db_weights():
    """Con fila en DB, debe devolver los weights de la DB."""
    custom = {"kills": 99.0, "deaths": -10.0, "cs_per_min": 1.5}
    sb = _make_supabase_weights(data=[{"weights": custom}])
    result = get_scoring_weights(sb, "comp-lck", "adc")
    assert result == custom


# ---------------------------------------------------------------------------
# T1.5-c  cachea en segunda llamada — DB consultada exactamente una vez
# ---------------------------------------------------------------------------


def test_get_scoring_weights_caches_on_second_call():
    """La segunda llamada con mismos args NO debe volver a consultar la DB."""
    custom = {"kills": 50.0}
    sb = _make_supabase_weights(data=[{"weights": custom}])

    result1 = get_scoring_weights(sb, "comp-lec", "top")
    result2 = get_scoring_weights(sb, "comp-lec", "top")

    assert result1 == result2 == custom
    # execute() debe haberse llamado exactamente una vez
    assert sb.table.return_value.execute.call_count == 1


# ---------------------------------------------------------------------------
# T1.5-d  excepción de DB → logger.warning + retorna fallback (no crashea)
# ---------------------------------------------------------------------------


def test_get_scoring_weights_db_exception_logs_warning_and_falls_back():
    """Si la DB lanza una excepción, se llama logger.warning y se devuelve el fallback."""
    sb = _make_supabase_raising(RuntimeError("DB connection refused"))

    with patch("scoring.config_loader.logger") as mock_logger:
        result = get_scoring_weights(sb, "comp-x", "support")

    mock_logger.warning.assert_called_once()
    warning_args = mock_logger.warning.call_args[0]
    # El mensaje debe mencionar competition_id y role
    assert "comp-x" in warning_args or any("comp-x" in str(a) for a in warning_args)
    assert result == ROLE_WEIGHTS["support"]


# ---------------------------------------------------------------------------
# T1.5-e  clear_weights_cache() resetea el cache → siguiente llamada va a DB
# ---------------------------------------------------------------------------


def test_clear_weights_cache_forces_db_requery():
    """Después de clear_weights_cache(), la próxima llamada debe consultar la DB de nuevo."""
    custom = {"kills": 77.0}
    sb = _make_supabase_weights(data=[{"weights": custom}])

    # Primera llamada — consulta DB
    get_scoring_weights(sb, "comp-lec", "jungle")
    assert sb.table.return_value.execute.call_count == 1

    # Limpiamos cache
    clear_weights_cache()

    # Segunda llamada — debe volver a consultar DB
    get_scoring_weights(sb, "comp-lec", "jungle")
    assert sb.table.return_value.execute.call_count == 2


# ---------------------------------------------------------------------------
# T1.5-f  get_multikill_bonuses — retorna DB o fallback MULTIKILL_BONUS
# ---------------------------------------------------------------------------


def test_get_multikill_bonuses_returns_db_value():
    """Con fila en DB que tiene multikill_bonuses, debe devolver esos bonuses."""
    custom_bonuses = {"double_kill": 3.0, "triple_kill": 7.0, "penta_kill": 20.0}
    sb = _make_supabase_multikill(data=[{"multikill_bonuses": custom_bonuses}])
    result = get_multikill_bonuses(sb, "comp-lec")
    assert result == custom_bonuses


def test_get_multikill_bonuses_fallback_when_no_db_row():
    """Sin fila en DB, debe devolver MULTIKILL_BONUS hardcodeado."""
    sb = _make_supabase_multikill(data=[])
    result = get_multikill_bonuses(sb, "comp-unknown")
    assert result == MULTIKILL_BONUS
