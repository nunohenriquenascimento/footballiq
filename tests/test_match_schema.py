"""Testes para a validação declarativa de partidas com Pydantic."""

import pytest
from pydantic import ValidationError

from footballiq.schemas.match import FootballMatch


@pytest.mark.parametrize(
    ("payload", "match_key"),
    [
        (
            {
                "match_id": 0,
                "home_team": "Benfica",
                "away_team": "Porto",
                "home_goals": 2,
                "away_goals": 1,
                "status": "finished",
            },
            "match_id",
        ),
        (
            {
                "match_id": 101,
                "home_team": "   ",
                "away_team": "Porto",
                "home_goals": 2,
                "away_goals": 1,
                "status": "finished",
            },
            "home_team",
        ),
        (
            {
                "match_id": 101,
                "home_team": "Benfica",
                "away_team": "Benfica",
                "home_goals": 2,
                "away_goals": 1,
                "status": "finished",
            },
            "away_team",
        ),
        (
            {
                "match_id": 101,
                "home_team": "Benfica",
                "away_team": "Porto",
                "home_goals": -1,
                "away_goals": 1,
                "status": "finished",
            },
            "home_goals",
        ),
        (
            {
                "match_id": 101,
                "home_team": "Benfica",
                "away_team": "Porto",
                "home_goals": 2,
                "away_goals": 1,
                "status": "scheduled",
            },
            "status",
        ),
        (
            {
                "match_id": True,
                "home_team": "Benfica",
                "away_team": "Porto",
                "home_goals": 2,
                "away_goals": 1,
                "status": "finished",
            },
            "match_id",
        ),
    ],
)
def test_football_match_rejects_invalid_data(
    payload: dict[str, object], match_key: str
) -> None:
    """Valida que os campos obrigatórios e as regras de integridade são respeitadas."""
    with pytest.raises(ValidationError):
        FootballMatch.model_validate(payload)


def test_football_match_normalizes_team_names_and_strips_extra_fields() -> None:
    """Confirma que os nomes são normalizados e que campos extras são rejeitados."""
    payload = {
        "match_id": 101,
        "home_team": "  Benfica  ",
        "away_team": " Porto ",
        "home_goals": 2,
        "away_goals": 1,
        "status": "finished",
        "extra": "unexpected",
    }

    with pytest.raises(ValidationError):
        FootballMatch.model_validate(payload)

    valid = FootballMatch.model_validate(
        {
            "match_id": 101,
            "home_team": "  Benfica  ",
            "away_team": "Porto",
            "home_goals": 2,
            "away_goals": 1,
            "status": "finished",
        }
    )

    assert valid.home_team == "Benfica"
    assert valid.away_team == "Porto"
    assert valid.model_dump() == {
        "match_id": 101,
        "home_team": "Benfica",
        "away_team": "Porto",
        "home_goals": 2,
        "away_goals": 1,
        "status": "finished",
    }
