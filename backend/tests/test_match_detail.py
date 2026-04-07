"""
Tests for GET /series/{series_id}/match-detail endpoint.

Uses FastAPI dependency_overrides to mock Supabase + auth without hitting the network.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from auth.dependencies import get_current_user, get_supabase
from main import app

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

LEAGUE_ID = str(uuid4())
SERIES_ID = str(uuid4())
TEAM_HOME_ID = str(uuid4())
TEAM_AWAY_ID = str(uuid4())
COMPETITION_ID = str(uuid4())
GAME1_ID = str(uuid4())
GAME2_ID = str(uuid4())
PLAYER1_ID = str(uuid4())
PLAYER2_ID = str(uuid4())

SERIES_ROW_FINISHED = {
    "id": SERIES_ID,
    "date": "2026-04-10",
    "status": "finished",
    "team_home_id": TEAM_HOME_ID,
    "team_away_id": TEAM_AWAY_ID,
    "competition_id": COMPETITION_ID,
    "home_team": {"id": TEAM_HOME_ID, "name": "G2 Esports", "logo_url": None},
    "away_team": {"id": TEAM_AWAY_ID, "name": "Fnatic", "logo_url": None},
}

SERIES_ROW_SCHEDULED = {
    "id": SERIES_ID,
    "date": "2026-04-15",
    "status": "scheduled",
    "team_home_id": TEAM_HOME_ID,
    "team_away_id": TEAM_AWAY_ID,
    "competition_id": COMPETITION_ID,
    "home_team": {"id": TEAM_HOME_ID, "name": "G2 Esports", "logo_url": None},
    "away_team": {"id": TEAM_AWAY_ID, "name": "Fnatic", "logo_url": None},
}

GAMES_ROWS = [
    {
        "id": GAME1_ID,
        "game_number": 1,
        "duration_min": "32.50",
        "winner_id": TEAM_HOME_ID,
    },
    {
        "id": GAME2_ID,
        "game_number": 2,
        "duration_min": "28.00",
        "winner_id": TEAM_AWAY_ID,
    },
]

PLAYER_STATS_ROWS = [
    # Game 1 — Player1 wins
    {
        "game_id": GAME1_ID,
        "player_id": PLAYER1_ID,
        "kills": 5,
        "deaths": 2,
        "assists": 8,
        "game_points": 18.5,
        "gold_diff_15": 1200,
        "xp_diff_15": None,
        "result": 1,
        "players": {"name": "Caps", "role": "mid", "image_url": None, "team_id": TEAM_HOME_ID},
    },
    # Game 1 — Player2 loses
    {
        "game_id": GAME1_ID,
        "player_id": PLAYER2_ID,
        "kills": 2,
        "deaths": 5,
        "assists": 3,
        "game_points": 8.0,
        "gold_diff_15": -1200,
        "xp_diff_15": None,
        "result": 0,
        "players": {"name": "Humanoid", "role": "mid", "image_url": None, "team_id": TEAM_AWAY_ID},
    },
    # Game 2 — Player1 loses
    {
        "game_id": GAME2_ID,
        "player_id": PLAYER1_ID,
        "kills": 3,
        "deaths": 4,
        "assists": 6,
        "game_points": 12.0,
        "gold_diff_15": None,  # null gold diff in game 2
        "xp_diff_15": 500,
        "result": 0,
        "players": {"name": "Caps", "role": "mid", "image_url": None, "team_id": TEAM_HOME_ID},
    },
]


# ---------------------------------------------------------------------------
# Mock builder helpers
# ---------------------------------------------------------------------------


class _Seq:
    """Wraps a sequence of return values for tables queried multiple times."""
    def __init__(self, *items: Any):
        self._items = list(items)
        self._idx = 0

    def next(self) -> Any:
        if self._idx < len(self._items):
            val = self._items[self._idx]
            self._idx += 1
            return val
        return []


def _build_mock_sb(responses: dict[str, Any]) -> MagicMock:
    """
    Build a mock Supabase client.
    `responses` maps table name → data (list or dict).
    Wrap in _Seq(...) to return different data on successive calls to the same table.
    """
    sb = MagicMock()

    def table_side_effect(table_name: str) -> MagicMock:
        mock_table = MagicMock()
        mock_query = MagicMock()
        for method in ("select", "eq", "in_", "order", "single", "limit", "execute"):
            getattr(mock_query, method).return_value = mock_query

        result = MagicMock()
        raw = responses.get(table_name, [])
        if isinstance(raw, _Seq):
            result.data = raw.next()
        else:
            result.data = raw

        mock_query.execute.return_value = result
        mock_table.select.return_value = mock_query
        return mock_table

    sb.table.side_effect = table_side_effect
    return sb


def _fake_user() -> dict:
    return {"id": "user-1", "email": "test@test.com"}


def _override_deps(sb: MagicMock) -> TestClient:
    """Create TestClient with auth + supabase overrides."""
    app.dependency_overrides[get_supabase] = lambda: sb
    app.dependency_overrides[get_current_user] = lambda: _fake_user()
    return TestClient(app)


def _clear_overrides() -> None:
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests: played mode (finished series)
# ---------------------------------------------------------------------------


class TestMatchDetailPlayed:
    def setup_method(self):
        self.sb = _build_mock_sb({
            "league_members": [{"id": "member-1"}],
            "series": SERIES_ROW_FINISHED,
            "games": GAMES_ROWS,
            "player_game_stats": PLAYER_STATS_ROWS,
        })
        self.client = _override_deps(self.sb)

    def teardown_method(self):
        _clear_overrides()

    def test_finished_series_returns_played_mode(self):
        """Serie finished → mode='played', played != null, upcoming == null."""
        r = self.client.get(
            f"/series/{SERIES_ID}/match-detail",
            params={"league_id": LEAGUE_ID},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["mode"] == "played"
        assert body["played"] is not None
        assert body["upcoming"] is None

    def test_played_has_correct_game_count(self):
        """Played response has 2 games matching GAMES_ROWS."""
        r = self.client.get(
            f"/series/{SERIES_ID}/match-detail",
            params={"league_id": LEAGUE_ID},
        )
        played = r.json()["played"]
        assert len(played["games"]) == 2
        assert played["games"][0]["game_number"] == 1
        assert played["games"][1]["game_number"] == 2

    def test_series_stats_avg_kills_calculated_correctly(self):
        """Player1 has kills [5, 3] across 2 games → avg_kills = 4.0."""
        r = self.client.get(
            f"/series/{SERIES_ID}/match-detail",
            params={"league_id": LEAGUE_ID},
        )
        series_stats = r.json()["played"]["series_stats"]
        player1_stat = next(s for s in series_stats if s["player_id"] == PLAYER1_ID)
        assert player1_stat["avg_kills"] == 4.0
        assert player1_stat["games_played"] == 2

    def test_null_gold_diff_excluded_from_avg(self):
        """Player1: game1 gold_diff_15=1200, game2 gold_diff_15=None.
        avg_gold_diff_15 = avg of [1200] = 1200.0 (null excluded)."""
        r = self.client.get(
            f"/series/{SERIES_ID}/match-detail",
            params={"league_id": LEAGUE_ID},
        )
        series_stats = r.json()["played"]["series_stats"]
        player1_stat = next(s for s in series_stats if s["player_id"] == PLAYER1_ID)
        assert player1_stat["avg_gold_diff_15"] == 1200.0

    def test_all_null_gold_diff_yields_null_avg(self):
        """Player with all null gold_diff_15 → avg_gold_diff_15 = None."""
        rows_all_null = [
            {
                "game_id": GAME1_ID,
                "player_id": PLAYER1_ID,
                "kills": 3,
                "deaths": 2,
                "assists": 5,
                "game_points": 10.0,
                "gold_diff_15": None,
                "xp_diff_15": None,
                "result": 1,
                "players": {"name": "Caps", "role": "mid", "image_url": None, "team_id": TEAM_HOME_ID},
            }
        ]
        sb = _build_mock_sb({
            "league_members": [{"id": "member-1"}],
            "series": SERIES_ROW_FINISHED,
            "games": [GAMES_ROWS[0]],
            "player_game_stats": rows_all_null,
        })
        c = _override_deps(sb)
        r = c.get(
            f"/series/{SERIES_ID}/match-detail",
            params={"league_id": LEAGUE_ID},
        )
        series_stats = r.json()["played"]["series_stats"]
        assert series_stats[0]["avg_gold_diff_15"] is None

    def test_score_calculation(self):
        """Game 1 won by home, game 2 won by away → score_home=1, score_away=1."""
        r = self.client.get(
            f"/series/{SERIES_ID}/match-detail",
            params={"league_id": LEAGUE_ID},
        )
        played = r.json()["played"]
        assert played["score_home"] == 1
        assert played["score_away"] == 1


# ---------------------------------------------------------------------------
# Tests: upcoming mode (scheduled series)
# ---------------------------------------------------------------------------


PLAYER_ROWS_UPCOMING = [
    {"id": PLAYER1_ID, "name": "Caps", "role": "mid", "image_url": None, "team_id": TEAM_HOME_ID},
    {"id": PLAYER2_ID, "name": "Upset", "role": "adc", "image_url": None, "team_id": TEAM_AWAY_ID},
]

PSS_ROWS_UPCOMING = [
    {
        "player_id": PLAYER1_ID,
        "series_id": str(uuid4()),
        "games_played": 2,
        "series_points": 30.0,
        "avg_kills": 4.5,
        "avg_deaths": 2.0,
        "avg_assists": 6.0,
        "avg_gold_diff_15": 800.0,
    }
]


FINISHED_SERIES_ID = str(uuid4())


class TestMatchDetailUpcoming:
    def setup_method(self):
        # "series" table is queried twice:
        #   1st: fetch series by id (.single()) → SERIES_ROW_SCHEDULED
        #   2nd: fetch finished series in competition → [{"id": ...}]
        self.sb = _build_mock_sb({
            "league_members": [{"id": "member-1"}],
            "series": _Seq(SERIES_ROW_SCHEDULED, [{"id": FINISHED_SERIES_ID}]),
            "players": PLAYER_ROWS_UPCOMING,
            "player_series_stats": PSS_ROWS_UPCOMING,
        })
        self.client = _override_deps(self.sb)

    def teardown_method(self):
        _clear_overrides()

    def test_scheduled_series_returns_upcoming_mode(self):
        """Serie scheduled → mode='upcoming', upcoming != null, played == null."""
        r = self.client.get(
            f"/series/{SERIES_ID}/match-detail",
            params={"league_id": LEAGUE_ID},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["mode"] == "upcoming"
        assert body["upcoming"] is not None
        assert body["played"] is None

    def test_series_not_found_returns_404(self):
        """Series ID not found → 404."""
        sb = _build_mock_sb({
            "league_members": [{"id": "member-1"}],
            "series": None,  # not found
        })
        c = _override_deps(sb)
        r = c.get(
            f"/series/{str(uuid4())}/match-detail",
            params={"league_id": LEAGUE_ID},
        )
        assert r.status_code == 404

    def test_player_with_no_season_stats_included_with_defaults(self):
        """Players with no player_series_stats → appear with avg_kills=0, avg_points=None."""
        sb = _build_mock_sb({
            "league_members": [{"id": "member-1"}],
            "series": _Seq(SERIES_ROW_SCHEDULED, [{"id": FINISHED_SERIES_ID}]),
            "players": PLAYER_ROWS_UPCOMING,
            "player_series_stats": [],  # no stats for anyone
        })
        c = _override_deps(sb)
        r = c.get(
            f"/series/{SERIES_ID}/match-detail",
            params={"league_id": LEAGUE_ID},
        )
        assert r.status_code == 200
        upcoming = r.json()["upcoming"]
        avgs = upcoming["season_averages"]
        assert len(avgs) == 2
        for avg in avgs:
            assert avg["avg_kills"] == 0.0
            assert avg["avg_points"] is None
