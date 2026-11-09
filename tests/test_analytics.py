"""Resultados esperados calculados manualmente para jogos sintéticos."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from footballiq.analytics import analyze_recent_matches, report_json

FIXTURES = Path(__file__).parent / "fixtures" / "integration"


@pytest.fixture
def package() -> dict:
    """Carrega apenas dados fictícios, sem consultar serviços."""
    return json.loads((FIXTURES / "complete_five.json").read_text(encoding="utf-8"))


def policy(**changes) -> dict:
    """Política analítica explícita, sem pretensão de regulamento oficial."""
    return (
        dict(
            policy_id="synthetic-3-1-0",
            win=3,
            draw=1,
            loss=0,
            is_official=False,
            reference="Convenção fictícia",
            competition_id=None,
        )
        | changes
    )


def test_results_home_away_and_both_own_goals(package: dict) -> None:
    report = analyze_recent_matches(package)
    assert report.metrics["competitive"].values == {
        "wins": 2,
        "draws": 2,
        "losses": 1,
        "goals_for": 4,
        "goals_against": 4,
        "goal_difference": 0,
        "average_goals_for": 0.8,
        "average_goals_against": 0.8,
    }
    assert [match.reference.source_match_id for match in report.matches] == [
        "10",
        "9",
        "8",
        "7",
        "6",
    ]
    assert [(m.is_home, m.outcome) for m in report.matches] == [
        (True, "win"),
        (False, "win"),
        (True, "draw"),
        (False, "loss"),
        (True, "draw"),
    ]
    assert report.metrics["points"].values is None
    assert any("política" in warning for warning in report.warnings)


def test_points_require_valid_explicit_policy(package: dict) -> None:
    report = analyze_recent_matches(package, points_policy=policy())
    assert report.metrics["points"].values == {"points": 8}
    assert report.points_policy.is_official is False
    assert any("convenção" in warning for warning in report.warnings)
    for invalid in (
        policy(win=True),
        policy(win=-1),
        policy(win="3"),
        policy(reference=" "),
    ):
        with pytest.raises(ValidationError):
            analyze_recent_matches(package, points_policy=invalid)


def test_official_policy_is_bound_to_single_competition(package: dict) -> None:
    with pytest.raises(ValidationError):
        analyze_recent_matches(package, points_policy=policy(is_official=True))
    official = policy(is_official=True, competition_id="3")
    with pytest.raises(ValueError, match="single"):
        analyze_recent_matches(package, points_policy=official)
    package["selection"].update(competition_scope="single", competition_id="3")
    for match in package["matches"]:
        match["competition_id"] = "3"
    assert analyze_recent_matches(package, points_policy=official).metrics[
        "points"
    ].values == {"points": 8}


def test_complete_event_categories_and_zero_are_distinguished(package: dict) -> None:
    report = analyze_recent_matches(package)
    shots = report.metrics["shots"]
    assert shots.covered_matches == shots.selected_matches == 5
    assert shots.values["total_for"] == shots.values["on_target_for"] == 1
    assert shots.values["total_against"] == 0
    assert report.metrics["cards"].values["yellow_against"] == 1
    assert report.metrics["substitutions"].values["substitutions_for"] == 1
    # Quatro golos a favor não são convertidos em quatro remates.
    assert (
        shots.values["total_for"] != report.metrics["competitive"].values["goals_for"]
    )
    zero = copy.deepcopy(package)
    zero["matches"] = [zero["matches"][-1]]
    zero["selection"]["returned_count"] = 1
    result = analyze_recent_matches(zero)
    assert result.metrics["shots"].values["total_for"] == 0
    assert result.metrics["competitive"].values["draws"] == 1


def test_partial_window_keeps_subtotal_and_explicit_denominator(package: dict) -> None:
    match = package["matches"][0]
    match["score"]["status"] = "unverified"
    match["quality"]["shots"]["status"] = "unknown"
    report = analyze_recent_matches(package)
    competitive = report.metrics["competitive"]
    assert competitive.values is None
    assert competitive.covered_matches == 4
    assert competitive.selected_matches == 5
    assert competitive.covered_values["goals_for"] == 2
    assert competitive.covered_values["average_goals_for"] == 0.5
    assert competitive.missing[0].source_match_id == "10"
    assert report.metrics["shots"].values is None
    assert report.metrics["shots"].covered_values["total_for"] == 0
    assert len(report.matches) == 5  # O jogo incompleto não sai da janela.
    assert any("4/5" in warning for warning in report.warnings)


def test_partial_fixture_never_invents_score_or_event_totals() -> None:
    report = analyze_recent_matches(
        (FIXTURES / "partial_match.json").read_text(encoding="utf-8")
    )
    assert len(report.matches) == 1
    assert report.matches[0].outcome is None
    assert all(metric.values is None for metric in report.metrics.values())
    assert report.metrics["temporal_goals"].covered_values is None
    assert any("1 de 5" in warning for warning in report.warnings)


def test_temporal_distribution_uses_complete_goal_events(package: dict) -> None:
    values = analyze_recent_matches(package).metrics["temporal_goals"].values
    assert values["period_1_for"] == 3
    assert values["period_2_for"] == 1
    assert values["period_1_against"] == 3
    assert values["period_2_against"] == 1
    assert values["minute_45-59_for"] == 1
    assert values["minute_60-74_against"] == 1
    assert values["minute_90+_for"] == 0


def test_official_result_does_not_imply_complete_shots_or_goal_timeline(
    package: dict,
) -> None:
    package["matches"] = [package["matches"][-1]]
    package["selection"]["returned_count"] = 1
    match = package["matches"][0]
    match["score"]["provenance"].update(
        method="official_capture", reference_ids=["official_capture:synthetic-1"]
    )
    match["external_references"] = [
        {"resource": "official_capture", "id": "synthetic-1"}
    ]
    for name in ("score_events", "shots"):
        match["quality"][name]["status"] = "unknown"
    report = analyze_recent_matches(package)
    assert report.metrics["competitive"].values["draws"] == 1
    assert report.metrics["shots"].values is None
    assert report.metrics["temporal_goals"].values is None


def test_empty_window_has_no_totals_or_averages() -> None:
    report = analyze_recent_matches(
        (FIXTURES / "empty.json").read_text(encoding="utf-8")
    )
    assert report.matches == []
    for metric in report.metrics.values():
        assert metric.values is metric.covered_values is None
        assert metric.covered_matches == metric.selected_matches == 0
    assert any("0 de 5" in warning for warning in report.warnings)


def test_references_versions_and_repetition_are_stable(package: dict) -> None:
    original = copy.deepcopy(package)
    first = analyze_recent_matches(package)
    assert package == original
    assert report_json(first) == report_json(analyze_recent_matches(package))
    reference = first.matches[0].reference
    assert reference.source_instance_id == package["source_instance_id"]
    assert reference.source_system == "match_tracker"
    assert reference.data_version == "synthetic-match-10-v1"
    assert reference.event_ids == [
        e["source_event_id"] for e in package["matches"][0]["events"]
    ]
    assert first.snapshot_version == package["snapshot_version"]
    assert first.authorization_verified is False
    assert first.interpretation_status == "not_requested"
    package["source_instance_id"] = "another-fictional-instance"
    assert analyze_recent_matches(package).matches[0].reference != reference


def test_new_snapshot_and_event_version_change_report(package: dict) -> None:
    previous = report_json(analyze_recent_matches(package))
    package["matches"][0]["events"][0]["event_type"] = "SHOT_OFF_TARGET"
    package["matches"][0]["data_version"] = "synthetic-match-10-v2"
    package["snapshot_version"] = "synthetic-five-v2"
    current = analyze_recent_matches(package)
    assert report_json(current) != previous
    assert current.metrics["shots"].values["off_target_for"] == 1


def test_import_has_no_network_database_or_schema_side_effects() -> None:
    script = """
import importlib.abc
import socket
import sys
from unittest.mock import patch

class NoDatabaseImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'psycopg', 'sqlalchemy'} or fullname.startswith('footballiq.db'):
            raise AssertionError('Analytics must not import a database layer')

def forbidden(*args, **kwargs):
    raise AssertionError('Analytics must not open network connections')

sys.meta_path.insert(0, NoDatabaseImports())
with patch.object(socket.socket, 'connect', forbidden), patch.object(socket, 'create_connection', forbidden):
    from footballiq.analytics import analyze_recent_matches
    from footballiq.schemas.integration import ExportPackage
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
