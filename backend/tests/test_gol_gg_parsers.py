"""
Tests de los parsers internos de gol_gg.py.

Usa fixtures reales de gol.gg — NO mocks, NO red, NO DB.
Los fixtures están en backend/tests/fixtures/golgg_*.md.
Para generarlos: correr el scraper localmente y copiar los archivos ahí.
"""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pytest

# Importar los parsers internos que vamos a testear
from pipeline.gol_gg import (
    GameMeta,
    _normalize_role,
    _parse_damage_share,
    _parse_fullstats_table,
    _parse_game_meta,
    _parse_matchlist,
    _parse_optional_int,
)

# ---------------------------------------------------------------------------
# Fixtures — cargan el markdown real de gol.gg
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _require_fixture(filename: str) -> str:
    path = FIXTURES_DIR / filename
    if not path.exists():
        pytest.skip(f"requires local scraper fixture: {path}")
    return path.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def golgg_matchlist_fixture() -> str:
    return _require_fixture("golgg_matchlist.md")


@pytest.fixture(scope="module")
def golgg_fullstats_fixture() -> str:
    return _require_fixture("golgg_fullstats.md")


@pytest.fixture(scope="module")
def golgg_page_game_fixture() -> str:
    return _require_fixture("golgg_page_game.md")


# ---------------------------------------------------------------------------
# Tests de _parse_optional_int
# ---------------------------------------------------------------------------


def test_parse_optional_int_normal():
    assert _parse_optional_int("15") == 15


def test_parse_optional_int_negative_escaped():
    assert _parse_optional_int("\\-1234") == -1234


def test_parse_optional_int_empty():
    assert _parse_optional_int("") is None


def test_parse_optional_int_none():
    assert _parse_optional_int(None) is None


def test_parse_optional_int_dash():
    assert _parse_optional_int("-") is None


def test_parse_optional_int_very_large():
    # No debe overflow — Python maneja ints arbitrarios
    assert _parse_optional_int("999999999") == 999999999


# ---------------------------------------------------------------------------
# Tests de _parse_damage_share
# ---------------------------------------------------------------------------


def test_parse_damage_share_normal():
    result = _parse_damage_share("27.3%")
    assert abs(result - 0.273) < 1e-5


def test_parse_damage_share_empty():
    assert _parse_damage_share("") == 0.0


def test_parse_damage_share_hundred():
    result = _parse_damage_share("100%")
    assert abs(result - 1.0) < 1e-5


# ---------------------------------------------------------------------------
# Tests de _normalize_role
# ---------------------------------------------------------------------------


def test_normalize_role_bot_to_adc():
    assert _normalize_role("bot") == "adc"


def test_normalize_role_jgl_to_jungle():
    assert _normalize_role("jgl") == "jungle"


def test_normalize_role_uppercase():
    assert _normalize_role("TOP") == "top"


def test_normalize_role_support_variants():
    assert _normalize_role("sup") == "support"


# ---------------------------------------------------------------------------
# Tests de _parse_matchlist (con fixture real)
# ---------------------------------------------------------------------------


def test_parse_matchlist_returns_entries(golgg_matchlist_fixture):
    entries = _parse_matchlist(golgg_matchlist_fixture)
    assert len(entries) > 0


def test_parse_matchlist_game_id_numeric(golgg_matchlist_fixture):
    entries = _parse_matchlist(golgg_matchlist_fixture)
    for entry in entries:
        assert entry.game_id.isdigit(), f"game_id no es numérico: {entry.game_id!r}"


def test_parse_matchlist_valid_dates(golgg_matchlist_fixture):
    entries = _parse_matchlist(golgg_matchlist_fixture)
    for entry in entries:
        assert isinstance(entry.date, date), f"date inválido: {entry.date!r}"


def test_parse_matchlist_week_positive(golgg_matchlist_fixture):
    entries = _parse_matchlist(golgg_matchlist_fixture)
    for entry in entries:
        assert entry.week > 0, f"week no positivo: {entry.week}"


def test_parse_matchlist_teams_non_empty(golgg_matchlist_fixture):
    entries = _parse_matchlist(golgg_matchlist_fixture)
    for entry in entries:
        assert entry.team_home != "", f"team_home vacío en game {entry.game_id}"
        assert entry.team_away != "", f"team_away vacío en game {entry.game_id}"


# ---------------------------------------------------------------------------
# Tests de _parse_fullstats_table (con fixture real)
# ---------------------------------------------------------------------------

VALID_ROLES = {"top", "jungle", "mid", "adc", "support"}


def test_parse_fullstats_returns_10_players(golgg_fullstats_fixture):
    raw_players = _parse_fullstats_table(golgg_fullstats_fixture)
    assert len(raw_players) == 10, f"Esperaba 10 jugadores, obtuve {len(raw_players)}"


def test_parse_fullstats_player_names(golgg_fullstats_fixture):
    raw_players = _parse_fullstats_table(golgg_fullstats_fixture)
    for i, p in enumerate(raw_players):
        name = p.get("player_name", "")
        assert name != "", f"player_name vacío en índice {i}"


def test_parse_fullstats_roles_valid(golgg_fullstats_fixture):
    from pipeline.gol_gg import _normalize_role

    raw_players = _parse_fullstats_table(golgg_fullstats_fixture)
    for i, p in enumerate(raw_players):
        raw_role = p.get("role", "")
        normalized = _normalize_role(raw_role)
        assert normalized in VALID_ROLES, (
            f"Rol inválido '{raw_role}' → '{normalized}' en índice {i}"
        )


def test_parse_fullstats_kills_non_negative(golgg_fullstats_fixture):
    from pipeline.gol_gg import _parse_int

    raw_players = _parse_fullstats_table(golgg_fullstats_fixture)
    for i, p in enumerate(raw_players):
        kills = _parse_int(p.get("kills"))
        assert kills >= 0, f"kills negativo ({kills}) en índice {i}"


def test_parse_fullstats_damage_share_decimal(golgg_fullstats_fixture):
    from pipeline.gol_gg import _parse_damage_share

    raw_players = _parse_fullstats_table(golgg_fullstats_fixture)
    for i, p in enumerate(raw_players):
        ds = _parse_damage_share(p.get("damage_share"))
        assert 0.0 <= ds <= 1.0, f"damage_share fuera de rango ({ds}) en índice {i}"


def test_parse_fullstats_cs_per_min_positive(golgg_fullstats_fixture):
    from pipeline.gol_gg import _parse_float

    raw_players = _parse_fullstats_table(golgg_fullstats_fixture)
    for i, p in enumerate(raw_players):
        csm = _parse_float(p.get("cs_per_min"))
        assert csm >= 0, f"cs_per_min negativo ({csm}) en índice {i}"


# ---------------------------------------------------------------------------
# Tests de _parse_game_meta (con fixture real — DESPUÉS del fix)
# ---------------------------------------------------------------------------


def test_parse_game_meta_duration_positive(golgg_page_game_fixture):
    meta = _parse_game_meta(golgg_page_game_fixture)
    assert meta.duration_min > 0, f"duration_min no positivo: {meta.duration_min}"


def test_parse_game_meta_winner_non_empty(golgg_page_game_fixture):
    meta = _parse_game_meta(golgg_page_game_fixture)
    assert meta.winner_team != "", "winner_team está vacío"


def test_parse_game_meta_duration_reasonable(golgg_page_game_fixture):
    meta = _parse_game_meta(golgg_page_game_fixture)
    # Una partida de LoL razonable: entre 15 y 60 minutos
    assert 15.0 <= meta.duration_min <= 60.0, (
        f"duration_min fuera de rango razonable: {meta.duration_min}"
    )


# ---------------------------------------------------------------------------
# Tests de seguridad — inputs maliciosos
# ---------------------------------------------------------------------------


def test_parse_matchlist_empty_string():
    entries = _parse_matchlist("")
    assert entries == []


def test_parse_matchlist_garbage_input():
    entries = _parse_matchlist("asdf\n\n!!!")
    assert entries == []


def test_parse_fullstats_empty_string():
    raw = _parse_fullstats_table("")
    assert raw == []


def test_parse_game_meta_empty_string():
    meta = _parse_game_meta("")
    assert meta.duration_min == 0.0
    assert meta.winner_team == ""


def test_parse_fullstats_special_chars_in_name():
    """Un nombre con comilla o unicode no debe explotar el parser."""
    # Construimos un markdown mínimo con nombre especial en la fila Player
    markdown = (
        "| Player | O'Brien | Ñoño | Ünïcödé | X | Y | A | B | C | D | E |\n"
        "| ------ | ------- | ---- | ------- | - | - | - | - | - | - | - |\n"
        "| Role   | top     | mid  | jungle  | adc | support | top | mid | jungle | adc | support |\n"
    )
    # No debe levantar excepción
    raw = _parse_fullstats_table(markdown)
    assert isinstance(raw, list)
