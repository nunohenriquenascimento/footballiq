import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from app.validation.validate_match_details import (
    _player_indexes,
    _validate_events,
    validate_match_details,
    validation_exit_code,
)


DATA_PATH = (
    Path(__file__).resolve().parents[1]
    / "data/processed/match_details_sub16_fdm_2025_2026.json"
)


def _player() -> dict:
    return {
        "player_id": 1,
        "shirt_number": 1,
        "name": "Jogador Teste",
        "is_goalkeeper": False,
    }


def _match_with_events(events: list[dict]) -> dict:
    return {
        "match_id": 1,
        "lineups": {
            "home": {
                "starters": [_player()],
                "substitutes": [],
            },
            "away": {"starters": [], "substitutes": []},
        },
        "events": events,
    }


def _event(
    event_type: str,
    phase: str | None,
    minute: int | None,
    *,
    display_minute: str | None = None,
    detail: str | None = None,
) -> dict:
    return {
        "type": event_type,
        "phase": phase,
        "minute": minute,
        "added_time": None,
        "display_minute": display_minute,
        "source_section": phase,
        "team_side": "home",
        "player_id": 1,
        "player_name": "Jogador Teste",
        "detail": detail,
    }


class ValidateMatchDetailsTests(unittest.TestCase):
    def _event_issues(self, events: list[dict]) -> list[dict]:
        match = _match_with_events(events)
        issues: list[dict] = []
        _validate_events(
            match,
            match["match_id"],
            _player_indexes(match),
            issues,
        )
        return issues

    def test_accepts_zero_minute_card_at_half_time(self) -> None:
        issues = self._event_issues(
            [_event("yellow_card", "half_time", 0, display_minute="0'")]
        )
        self.assertFalse(
            any(issue["check"] == "chronology" for issue in issues)
        )

    def test_accepts_zero_minute_card_post_match(self) -> None:
        issues = self._event_issues(
            [_event("red_card", "post_match", 0, display_minute="0'")]
        )
        self.assertFalse(
            any(issue["check"] == "chronology" for issue in issues)
        )

    def test_accepts_penalty_without_minute(self) -> None:
        issues = self._event_issues(
            [_event("goal", None, None, detail="penalty")]
        )
        self.assertFalse(
            any(issue["check"] == "chronology" for issue in issues)
        )

        matches = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        match = copy.deepcopy(
            next(item for item in matches if item["match_id"] == 2453130)
        )
        with patch(
            "app.validation.validate_match_details.EXPECTED_MATCHES",
            1,
        ):
            validation = validate_match_details([match])
        self.assertFalse(
            any(
                issue["check"] == "score"
                for issue in validation["issues"]
            )
        )

    def test_accepts_events_in_phase_order(self) -> None:
        events = [
            _event("goal", "first_half", 20),
            _event("yellow_card", "half_time", 0),
            _event("goal", "second_half", 60),
            _event("red_card", "post_match", 0),
        ]
        issues = self._event_issues(events)
        self.assertFalse(
            any(issue["check"] == "chronology" for issue in issues)
        )

    def test_cross_team_substitution_is_source_inconsistency(
        self,
    ) -> None:
        matches = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        match = copy.deepcopy(
            next(item for item in matches if item["match_id"] == 2453114)
        )
        with patch(
            "app.validation.validate_match_details.EXPECTED_MATCHES",
            1,
        ):
            validation = validate_match_details([match])
        substitutions = [
            issue
            for issue in validation["source_inconsistency"]
            if issue["check"] == "substitution"
        ]
        self.assertEqual(len(substitutions), 1)
        self.assertTrue(substitutions[0]["source_value_preserved"])

    def test_exit_zero_for_source_inconsistency_only(self) -> None:
        matches = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        match = copy.deepcopy(
            next(item for item in matches if item["match_id"] == 2453114)
        )
        with patch(
            "app.validation.validate_match_details.EXPECTED_MATCHES",
            1,
        ):
            validation = validate_match_details([match])
        self.assertEqual(validation["statistics"]["technical_errors"], 0)
        self.assertGreater(
            validation["statistics"]["source_inconsistency"],
            0,
        )
        self.assertEqual(validation_exit_code(validation), 0)

    def test_exit_one_for_structural_error(self) -> None:
        with patch(
            "app.validation.validate_match_details.EXPECTED_MATCHES",
            1,
        ):
            validation = validate_match_details(["não é um objeto"])
        self.assertEqual(validation["statistics"]["structural_error"], 1)
        self.assertEqual(validation_exit_code(validation), 1)


if __name__ == "__main__":
    unittest.main()
