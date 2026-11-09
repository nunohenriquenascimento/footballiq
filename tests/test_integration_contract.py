"""Regressões do contrato v1 com dados exclusivamente fictícios e sem rede."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from footballiq.analytics import validate_package

FIXTURES = Path(__file__).parent / "fixtures" / "integration"


@pytest.fixture
def package() -> dict:
    """Devolve um pacote independente por teste para evitar mutações partilhadas."""
    return json.loads((FIXTURES / "complete_five.json").read_text(encoding="utf-8"))


def change(payload: dict, path: tuple, value: object) -> None:
    """Altera um campo aninhado para exercitar uma contradição concreta."""
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value


@pytest.mark.parametrize(
    "filename", ["complete_five.json", "partial_match.json", "empty.json"]
)
def test_synthetic_fixtures_validate_as_json_and_python(filename: str) -> None:
    text = (FIXTURES / filename).read_text(encoding="utf-8")
    assert validate_package(text) == validate_package(json.loads(text))


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema_version",), "1.1"),
        (("schema_version",), 1.0),
        (("source_system",), "footballiq"),
        (("source_instance_id",), " "),
        (("snapshot_version",), ""),
        (("selection", "returned_count"), True),
        (("selection", "returned_count"), 4),
        (("selection", "limit"), 6),
        (("selection", "limit"), 5.0),
        (("selection", "team_id"), "99"),
        (("selection", "competition_id"), "1"),
        (("selection", "competition_scope"), "single"),
        (("matches", 0, "season_id"), "8"),
        (("matches", 0, "team_id"), "55"),
        (("matches", 0, "status"), "FIRST_HALF"),
        (("matches", 0, "away_team", "team_id"), "42"),
        (("matches", 0, "home_team", "name"), "  "),
        (("matches", 0, "score", "home_goals"), True),
        (("matches", 0, "score", "home_goals"), "2"),
        (("matches", 0, "score", "home_goals"), -1),
        (("matches", 0, "score", "home_goals"), None),
        (("matches", 0, "score", "home_goals"), 3),
        (("matches", 0, "score", "provenance", "method"), "unknown"),
        (("matches", 0, "score", "provenance", "verified_at"), None),
        (("matches", 0, "score", "provenance", "reference_ids"), []),
        (("matches", 0, "score", "provenance", "reference_ids"), ["event:9999"]),
        (("matches", 0, "quality", "score_events", "status"), "partial"),
        (("matches", 0, "quality", "shots", "evidence"), None),
        (("matches", 0, "quality", "shots", "evidence"), " "),
        (("matches", 0, "quality", "cards", "status"), "estimated"),
        (("matches", 0, "source_reference", "id"), "9"),
        (
            ("matches", 0, "source_reference", "path"),
            "https://example.invalid/matches/10",
        ),
        (("matches", 0, "source_reference", "path"), "//example.invalid/10"),
        (("matches", 0, "source_reference", "path"), "/../10"),
        (("matches", 0, "source_reference", "path"), "/%2e%2e/10"),
        (("matches", 0, "events", 0, "source_match_id"), "9"),
        (("matches", 0, "events", 0, "team_id"), "99"),
        (("matches", 0, "events", 0, "event_type"), "XG"),
        (("matches", 0, "events", 0, "period"), True),
        (("matches", 0, "events", 0, "period"), 3),
        (("matches", 0, "events", 0, "elapsed_seconds"), False),
        (("matches", 0, "events", 0, "minute"), 99),
        (("matches", 0, "timezone"), "Unknown/Nowhere"),
        (("exported_at",), "2026-11-09T10:00:00"),
        (("exported_at",), 1794218400),
        (("selection", "as_of"), "2026-11-01T10:00:00Z"),
        (("matches", 0, "updated_at"), "2026-12-01T10:00:00Z"),
    ],
)
def test_rejects_contradictory_fields(
    package: dict, path: tuple, value: object
) -> None:
    change(package, path, value)
    with pytest.raises(ValidationError):
        validate_package(package)


@pytest.mark.parametrize(
    "invalid_id", ["0", "01", "-1", "1.0", "1\n", " 1", "١", 1, True]
)
def test_ids_are_positive_canonical_strings(package: dict, invalid_id: object) -> None:
    package["matches"][0]["events"][0]["source_event_id"] = invalid_id
    with pytest.raises(ValidationError):
        validate_package(package)


@pytest.mark.parametrize(
    "path",
    [
        (),
        ("authorized_scope",),
        ("selection",),
        ("matches", 0),
        ("matches", 0, "events", 0),
        ("matches", 0, "quality", "shots"),
    ],
)
def test_extra_fields_are_rejected_recursively(package: dict, path: tuple) -> None:
    target = package
    for key in path:
        target = target[key]
    target["unexpected"] = "value"
    with pytest.raises(ValidationError):
        validate_package(package)


def test_numeric_tie_break_and_event_order_are_validated(package: dict) -> None:
    assert [m.source_match_id for m in validate_package(package).matches][:2] == [
        "10",
        "9",
    ]
    package["matches"][0], package["matches"][1] = (
        package["matches"][1],
        package["matches"][0],
    )
    with pytest.raises(ValidationError, match="ordem"):
        validate_package(package)
    package["matches"].reverse()
    with pytest.raises(ValidationError, match="ordem"):
        validate_package(package)


def test_event_order_is_not_silently_repaired(package: dict) -> None:
    package["matches"][0]["events"].reverse()
    with pytest.raises(ValidationError, match="Eventos fora"):
        validate_package(package)


@pytest.mark.parametrize("kind", ["match", "event", "cross_match_event", "sixth_match"])
def test_duplicates_and_sixth_match_are_rejected(package: dict, kind: str) -> None:
    if kind == "match":
        package["matches"][1] = copy.deepcopy(package["matches"][0])
    elif kind == "event":
        package["matches"][0]["events"].insert(
            0, copy.deepcopy(package["matches"][0]["events"][0])
        )
    elif kind == "cross_match_event":
        package["matches"][1]["events"][0]["source_event_id"] = package["matches"][0][
            "events"
        ][0]["source_event_id"]
    else:
        package["matches"].append(copy.deepcopy(package["matches"][-1]))
    with pytest.raises(ValidationError):
        validate_package(package)


def test_offset_timestamps_normalize_to_same_instant(package: dict) -> None:
    package["matches"][0]["kickoff_at"] = "2026-11-08T16:00:00+01:00"
    assert (
        validate_package(package).matches[0].kickoff_at.isoformat()
        == "2026-11-08T15:00:00+00:00"
    )


def test_single_competition_must_match_every_game(package: dict) -> None:
    package["selection"].update(competition_scope="single", competition_id="3")
    for match in package["matches"]:
        match["competition_id"] = "3"
    validate_package(package)
    package["matches"][2]["competition_id"] = None
    with pytest.raises(ValidationError, match="competição"):
        validate_package(package)


def player(player_id: str = "21") -> dict:
    """Cria uma inscrição fictícia da equipa/época usadas nas fixtures."""
    return dict(
        source_player_id=player_id, team_id="42", season_id="7", name="Jogador Fictício"
    )


def test_player_links_and_known_squad_are_checked(package: dict) -> None:
    match = package["matches"][0]
    goal = next(e for e in match["events"] if e["event_type"] == "GOAL")
    goal["player"] = player()
    match["squad"] = [dict(source_squad_id="70", player=player(), is_starter=True)]
    match["quality"]["squad"].update(status="complete", evidence="Fixture")
    validate_package(package)
    goal["player"]["season_id"] = "8"
    with pytest.raises(ValidationError, match="época"):
        validate_package(package)
    goal["player"] = player("22")
    with pytest.raises(ValidationError, match="convocatória"):
        validate_package(package)


def test_squad_boolean_and_duplicates_are_strict(package: dict) -> None:
    match = package["matches"][0]
    match["quality"]["squad"].update(status="complete", evidence="Fixture")
    match["squad"] = [dict(source_squad_id="70", player=player(), is_starter=1)]
    with pytest.raises(ValidationError):
        validate_package(package)
    match["squad"][0]["is_starter"] = True
    match["squad"].append(copy.deepcopy(match["squad"][0]))
    with pytest.raises(ValidationError, match="duplicado"):
        validate_package(package)


def test_related_player_roles_and_team_are_checked(package: dict) -> None:
    event = package["matches"][0]["events"][0]  # Remate: não admite assistência.
    event["related_player"] = player()
    with pytest.raises(ValidationError, match="related_player"):
        validate_package(package)
    event["related_player"] = None
    event["player"] = player()
    event["player"]["team_id"] = "55"
    with pytest.raises(ValidationError, match="equipa"):
        validate_package(package)


def test_complete_attribution_requires_scorer_and_substitution_players(
    package: dict,
) -> None:
    package["matches"][0]["quality"]["player_attribution"].update(
        status="complete", evidence="Fixture"
    )
    with pytest.raises(ValidationError, match="Autoria completa|Substituição completa"):
        validate_package(package)


def test_validated_instances_are_revalidated_after_mutation(package: dict) -> None:
    parsed = validate_package(package)
    parsed.matches[0].team_id = "999"
    with pytest.raises(ValidationError):
        validate_package(parsed)


@pytest.mark.parametrize("key", ["updated_at", "competition_id", "squad"])
def test_nullable_fields_are_still_required(package: dict, key: str) -> None:
    del package["matches"][0][key]
    with pytest.raises(ValidationError):
        validate_package(package)


def test_unavailable_category_cannot_contain_observed_events(package: dict) -> None:
    package["matches"][0]["quality"]["shots"]["status"] = "unavailable"
    with pytest.raises(ValidationError, match="unavailable"):
        validate_package(package)


def test_official_verification_requires_capture_reference_and_reconciliation(
    package: dict,
) -> None:
    match = package["matches"][0]
    match["score"]["provenance"].update(
        method="official_capture", reference_ids=["official_capture:demo"]
    )
    with pytest.raises(ValidationError, match="Captura oficial"):
        validate_package(package)
    match["external_references"] = [{"resource": "official_capture", "id": "demo"}]
    validate_package(package)
    match["score"]["home_goals"] = 99
    with pytest.raises(ValidationError, match="reconcilia"):
        validate_package(package)


def test_same_registration_cannot_contradict_squad_identity(package: dict) -> None:
    match = package["matches"][0]
    goal = next(e for e in match["events"] if e["event_type"] == "GOAL")
    goal["player"] = player()
    match["squad"] = [dict(source_squad_id="70", player=player(), is_starter=True)]
    match["quality"]["squad"].update(status="complete", evidence="Fixture")
    goal["player"]["name"] = "Outra identidade no mesmo snapshot"
    with pytest.raises(ValidationError, match="contraditórias"):
        validate_package(package)


def test_unavailable_score_cannot_have_values(package: dict) -> None:
    package["matches"][0]["score"]["status"] = "unavailable"
    with pytest.raises(ValidationError, match="unavailable"):
        validate_package(package)
