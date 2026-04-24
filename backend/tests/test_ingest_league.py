"""
Tests de integración de scripts/ingest_league.py.

Verifica idempotencia, dry-run y preservación de datos existentes.
NO hace HTTP calls reales — mockea _fetch_markdown.
NO requiere Supabase real — usa mocks de supabase client.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# El script vive en scripts/, no en backend/.
# Agregamos el directorio raíz del proyecto al path para poder importarlo.
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import ingest_league  # noqa: E402


# ---------------------------------------------------------------------------
# Markdown fixture — misma data que test_gol_gg_parsers.py
# ---------------------------------------------------------------------------

TEAM_LIST_MARKDOWN = """
| Team | W | L | W% | GW | GL | GW% |
|------|---|---|----|----|----|-----|
| [G2 Esports](./team-stats/1234/page-team-stats/season-ALL/split-ALL/tournament-LEC-2026/) | 8 | 2 | 80% | 16 | 5 | 76% |
| [Fnatic](./team-stats/5678/page-team-stats/season-ALL/split-ALL/tournament-LEC-2026/) | 7 | 3 | 70% | 14 | 7 | 67% |
| [Team Vitality](./team-stats/9012/page-team-stats/season-ALL/split-ALL/tournament-LEC-2026/) | 6 | 4 | 60% | 12 | 9 | 57% |
"""

_FAKE_COMPETITION_ID = "comp-lec-2026"

# ---------------------------------------------------------------------------
# Helpers para construir el mock de Supabase
# ---------------------------------------------------------------------------


def _make_execute(data: list[dict]) -> MagicMock:
    result = MagicMock()
    result.data = data
    return result


def _build_supabase_mock(
    *,
    competition_exists: bool = False,
    write_calls: dict | None = None,
) -> tuple[MagicMock, dict]:
    """
    Construye un mock de Supabase client para ingest_league.

    Args:
        competition_exists: si True, simula que ya hay una competition con ese slug.
        write_calls: dict mutable para registrar llamadas de escritura
                     (tabla → lista de payloads). Permite verificar idempotencia.

    Returns:
        Tuple (supabase_mock, write_calls_dict).
    """
    if write_calls is None:
        write_calls = {}

    def _record_write(table: str, payload: Any) -> None:
        write_calls.setdefault(table, []).append(payload)

    # Estado mutable — el primer insert activa competition_exists para la misma sesión
    state = {"competition_exists": competition_exists}

    competition_row: dict = {}
    if competition_exists:
        competition_row.update({
            "id": _FAKE_COMPETITION_ID,
            "name": "LEC",
            "region": "Europe",
            "tier": 1,
            "gol_gg_slug": "LEC 2026 Spring Season",
        })

    def _table_side_effect(table_name: str) -> MagicMock:
        chain = MagicMock()

        if table_name == "competitions":
            # SELECT by slug
            def _competitions_select(fields):
                sel = MagicMock()

                def _eq(field, value):
                    eq_chain = MagicMock()
                    if state["competition_exists"]:
                        eq_chain.execute.return_value = _make_execute([competition_row])
                    else:
                        eq_chain.execute.return_value = _make_execute([])
                    return eq_chain

                sel.eq.side_effect = _eq
                return sel

            chain.select.side_effect = _competitions_select

            # UPDATE (cuando ya existe)
            def _competitions_update(payload):
                _record_write("competitions.update", payload)
                upd = MagicMock()
                upd.eq.return_value.execute.return_value = _make_execute([])
                return upd

            chain.update.side_effect = _competitions_update

            # INSERT (cuando no existe)
            def _competitions_insert(payload):
                _record_write("competitions.insert", payload)
                state["competition_exists"] = True
                competition_row.update({"id": _FAKE_COMPETITION_ID, **payload})
                ins = MagicMock()
                ins.execute.return_value = _make_execute([{"id": _FAKE_COMPETITION_ID}])
                return ins

            chain.insert.side_effect = _competitions_insert

        elif table_name == "teams":
            def _teams_upsert(payload, on_conflict=None):
                _record_write("teams.upsert", payload)
                ups = MagicMock()
                ups.execute.return_value = _make_execute([payload])
                return ups

            chain.upsert.side_effect = _teams_upsert

        elif table_name == "scoring_config":
            def _scoring_upsert(payload, on_conflict=None):
                _record_write("scoring_config.upsert", payload)
                ups = MagicMock()
                ups.execute.return_value = _make_execute([payload])
                return ups

            chain.upsert.side_effect = _scoring_upsert

        elif table_name == "players":
            # ingest_league NO debe tocar esta tabla — cualquier call queda registrado
            def _players_forbidden(*args, **kwargs):
                _record_write("players.FORBIDDEN", {"args": str(args), "kwargs": str(kwargs)})
                return MagicMock()

            chain.upsert.side_effect = _players_forbidden
            chain.update.side_effect = _players_forbidden
            chain.insert.side_effect = _players_forbidden

        return chain

    sb = MagicMock()
    sb.table.side_effect = _table_side_effect
    return sb, write_calls


# ---------------------------------------------------------------------------
# Test 1: idempotencia — dos runs seguidos no duplican datos
# ---------------------------------------------------------------------------


async def test_run_twice_idempotent():
    """
    Correr ingest_league.main() dos veces seguidas no aumenta el count de teams
    ni de registros en scoring_config.

    Run 1: competition no existe → INSERT.
    Run 2: competition ya existe → UPDATE (no INSERT adicional).
    Ambos runs deben upsertear los mismos 3 teams y la misma cantidad de scoring_config.
    """
    write_calls_run1: dict = {}
    write_calls_run2: dict = {}

    sb_run1, write_calls_run1 = _build_supabase_mock(
        competition_exists=False,
        write_calls=write_calls_run1,
    )
    # Run 2: la competition ya existe (como quedaría después del run 1)
    sb_run2, write_calls_run2 = _build_supabase_mock(
        competition_exists=True,
        write_calls=write_calls_run2,
    )

    # Run 1
    with (
        patch.object(sys, "argv", ["ingest_league.py", "--league", "LEC"]),
        patch("pipeline.gol_gg._fetch_markdown", new=AsyncMock(return_value=TEAM_LIST_MARKDOWN)),
        patch("ingest_league.create_client", return_value=sb_run1),
        patch.dict("os.environ", {"SUPABASE_URL": "http://fake.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "fake-key"}),
    ):
        exit1 = await ingest_league.main()

    # Run 2
    with (
        patch.object(sys, "argv", ["ingest_league.py", "--league", "LEC"]),
        patch("pipeline.gol_gg._fetch_markdown", new=AsyncMock(return_value=TEAM_LIST_MARKDOWN)),
        patch("ingest_league.create_client", return_value=sb_run2),
        patch.dict("os.environ", {"SUPABASE_URL": "http://fake.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "fake-key"}),
    ):
        exit2 = await ingest_league.main()

    assert exit1 == 0, f"Run 1 falló con exit code {exit1}"
    assert exit2 == 0, f"Run 2 falló con exit code {exit2}"

    # Run 1: inserta competition nueva
    assert len(write_calls_run1.get("competitions.insert", [])) == 1
    assert len(write_calls_run1.get("competitions.update", [])) == 0

    # Run 2: actualiza competition existente, NO vuelve a insertar
    assert len(write_calls_run2.get("competitions.insert", [])) == 0
    assert len(write_calls_run2.get("competitions.update", [])) == 1

    # Ambos runs upsertean los mismos 3 equipos
    teams_run1 = write_calls_run1.get("teams.upsert", [])
    teams_run2 = write_calls_run2.get("teams.upsert", [])
    assert len(teams_run1) == 3, f"Run 1 debería upsertear 3 teams, got {len(teams_run1)}"
    assert len(teams_run2) == 3, f"Run 2 debería upsertear 3 teams, got {len(teams_run2)}"

    names_run1 = {p["name"] for p in teams_run1}
    names_run2 = {p["name"] for p in teams_run2}
    assert names_run1 == names_run2, f"Los equipos difieren entre runs: {names_run1} vs {names_run2}"

    # Ambos runs seedean el mismo número de scoring_config rows
    sc_run1 = write_calls_run1.get("scoring_config.upsert", [])
    sc_run2 = write_calls_run2.get("scoring_config.upsert", [])
    assert len(sc_run1) > 0, "No se seeded ningún scoring_config en run 1"
    assert len(sc_run1) == len(sc_run2), (
        f"Scoring config count difiere: run1={len(sc_run1)}, run2={len(sc_run2)}"
    )


# ---------------------------------------------------------------------------
# Test 2: dry-run no toca la DB
# ---------------------------------------------------------------------------


async def test_dry_run_no_db_changes():
    """
    Con --dry-run, el supabase client no se crea y ningún método
    de escritura a la DB debe ser llamado.
    """
    mock_create_client = MagicMock()

    with (
        patch.object(sys, "argv", ["ingest_league.py", "--league", "LEC", "--dry-run"]),
        patch("pipeline.gol_gg._fetch_markdown", new=AsyncMock(return_value=TEAM_LIST_MARKDOWN)),
        patch("ingest_league.create_client", mock_create_client),
        patch.dict("os.environ", {"SUPABASE_URL": "http://fake.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "fake-key"}),
    ):
        exit_code = await ingest_league.main()

    assert exit_code == 0, f"dry-run falló con exit code {exit_code}"

    # create_client NO debe ser llamado en dry-run
    mock_create_client.assert_not_called()


# ---------------------------------------------------------------------------
# Test 3: current_price de un player existente no se resetea
# ---------------------------------------------------------------------------


async def test_existing_player_price_preserved():
    """
    ingest_league NO toca la tabla players — por lo tanto el current_price
    de un jugador existente con 15.0 jamás se modifica, independientemente
    de cuántas veces se corra el script.

    Este test verifica que la tabla 'players' nunca recibe llamadas de escritura.
    """
    # Simulamos un player existente con current_price=15.0 en la DB
    existing_player = {
        "id": "player-faker",
        "name": "Faker",
        "current_price": 15.0,
    }

    write_calls: dict = {}
    sb, write_calls = _build_supabase_mock(
        competition_exists=False,
        write_calls=write_calls,
    )

    with (
        patch.object(sys, "argv", ["ingest_league.py", "--league", "LEC"]),
        patch("pipeline.gol_gg._fetch_markdown", new=AsyncMock(return_value=TEAM_LIST_MARKDOWN)),
        patch("ingest_league.create_client", return_value=sb),
        patch.dict("os.environ", {"SUPABASE_URL": "http://fake.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "fake-key"}),
    ):
        exit_code = await ingest_league.main()

    assert exit_code == 0, f"El run falló con exit code {exit_code}"

    # La tabla 'players' no debe haber recibido ninguna operación de escritura
    assert "players.FORBIDDEN" not in write_calls, (
        f"ingest_league escribió en la tabla players: {write_calls.get('players.FORBIDDEN')}"
    )

    # El current_price del player no fue modificado (el script no lo toca)
    assert existing_player["current_price"] == 15.0, (
        "El current_price fue modificado — ingest_league no debería tocar players"
    )
