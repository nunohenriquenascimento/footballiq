"""Tendências sintéticas, sem PostgreSQL, Ollama ou ligações de rede."""

import json
import socket
from datetime import timedelta, timezone
from html import escape
from pathlib import Path
from unittest.mock import Mock

import pytest

from footballiq.analyst_dashboard import render_dashboard
from footballiq.analyst_demo import load_demo_report, render_demo_dashboard
from footballiq.analyst_interpretation import interpret_report, prepare_facts
from footballiq.analytics import analyze_recent_matches
from footballiq.trends import calculate_trends


@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Falha imediatamente se o núcleo tentar abrir uma ligação real."""
    monkeypatch.setattr(
        socket.socket, "connect", Mock(side_effect=AssertionError("Rede"))
    )


def test_complete_window_preserves_engine_and_versions() -> None:
    report = load_demo_report()
    before = report.model_dump_json()
    trends = calculate_trends(report)
    assert [g.match_id for g in trends.games] == ["6", "7", "8", "9", "10"]
    assert [g.outcome for g in trends.games] == ["draw", "loss", "draw", "win", "win"]
    assert [(g.goals_for, g.goals_against) for g in trends.games] == [
        (0, 0),
        (0, 2),
        (1, 1),
        (1, 0),
        (2, 1),
    ]
    assert [g.goal_difference for g in trends.games] == [0, -2, 0, 1, 1]
    values = trends.window.values
    assert values is not None
    for key in (
        "wins",
        "draws",
        "losses",
        "average_goals_for",
        "average_goals_against",
    ):
        assert values[key] == report.metrics["competitive"].values[key]
    assert values["clean_sheets"] == 2
    assert values["failed_to_score"] == 2
    assert values["goal_difference_range"] == 3
    assert values["goal_difference_population_variance"] == pytest.approx(1.2)
    assert values["equal_adjacent_outcomes"] == 1
    assert values["adjacent_pairs"] == 4
    assert trends.snapshot_version == report.snapshot_version
    assert trends.team_id == report.selection.team_id
    assert trends.season_id == report.selection.season_id
    for game in trends.games:
        original = next(
            m for m in report.matches if m.reference.source_match_id == game.match_id
        )
        assert game.data_version == original.reference.data_version
    assert report.model_dump_json() == before
    assert calculate_trends(report).to_dict() == trends.to_dict()


def test_venue_samples_respect_team_perspective() -> None:
    report = load_demo_report()
    trends = calculate_trends(report)
    for sample, home in ((trends.home, True), (trends.away, False)):
        expected = {
            m.reference.source_match_id for m in report.matches if m.is_home == home
        }
        assert set(sample.selected_ids) == expected
        assert set(sample.used_ids) == expected
        assert sample.values is not None
    assert trends.venue_reason is None
    assert len(trends.home.selected_ids) + len(trends.away.selected_ids) == 5


def test_temporal_groups_use_means_and_explicit_sizes() -> None:
    trends = calculate_trends(load_demo_report())
    assert trends.older.used_ids == ("6", "7")
    assert trends.newer.used_ids == ("8", "9", "10")
    assert trends.temporal_reason is None
    assert trends.temporal_change == pytest.approx(
        {"average_goals_for": 4 / 3, "average_goals_against": -1 / 3}
    )


@pytest.mark.parametrize("scenario,count", [("partial_match", 1), ("empty", 0)])
def test_missing_results_and_empty_are_not_zero(scenario: str, count: int) -> None:
    trends = calculate_trends(load_demo_report(scenario))
    assert len(trends.games) == count
    assert trends.window.values is None
    assert trends.window.covered_values is None
    assert trends.window.used_ids == ()
    assert trends.window.variability_reason == "insufficient_sample_min_2"
    assert trends.temporal_change is None
    assert trends.temporal_reason == "insufficient_sample_min_4"


def test_one_verified_zero_score_is_valid_but_not_variability() -> None:
    report = load_demo_report()
    report.matches = [report.matches[-1]]
    trends = calculate_trends(report)
    assert trends.window.values["clean_sheets"] == 1
    assert trends.window.values["failed_to_score"] == 1
    assert "goal_difference_population_variance" not in trends.window.values
    assert trends.window.stability_reason == "no_verified_adjacent_pairs"
    assert trends.venue_reason == "insufficient_sample_min_2_per_venue"


@pytest.mark.parametrize("status", ["unverified", "conflict", "unavailable"])
def test_unverified_even_with_numeric_scores_is_excluded(status: str) -> None:
    report = load_demo_report()
    report.matches[2].score_status = status
    trends = calculate_trends(report)
    assert trends.window.values is None
    assert len(trends.window.used_ids) == 4
    assert "8" not in trends.window.used_ids
    assert trends.window.reason == "unverified_results"
    game = trends.games[2]
    assert (
        game.goals_for
        is game.goals_against
        is game.goal_difference
        is game.outcome
        is None
    )
    assert trends.temporal_change is None
    assert trends.temporal_reason == "unverified_results"
    assert trends.window.covered_values["adjacent_pairs"] == 2


def test_stability_never_bridges_unknown_results() -> None:
    report = load_demo_report()
    for match in report.matches:
        if match.reference.source_match_id in {"7", "9"}:
            match.score_status = "unverified"
    trends = calculate_trends(report)
    assert trends.window.used_ids == ("6", "8", "10")
    assert "adjacent_pairs" not in trends.window.covered_values
    assert trends.window.stability_reason == "no_verified_adjacent_pairs"


def test_numeric_tie_break_and_timezone_normalized_order() -> None:
    report = load_demo_report()
    for match in report.matches:
        match.kickoff_at = report.matches[0].kickoff_at
    report.matches = list(reversed(report.matches))
    trends = calculate_trends(report)
    assert [g.match_id for g in trends.games] == ["6", "7", "8", "9", "10"]
    assert trends.temporal_change is None
    assert trends.temporal_reason == "tied_temporal_boundary"


def test_four_verified_games_are_sufficient() -> None:
    report = load_demo_report()
    report.matches = report.matches[1:]
    trends = calculate_trends(report)
    assert len(trends.older.used_ids) == len(trends.newer.used_ids) == 2
    assert trends.temporal_change is not None


@pytest.mark.parametrize("duplicate", [True, False])
def test_invalid_window_is_rejected(duplicate: bool) -> None:
    report = load_demo_report()
    if duplicate:
        report.matches[0] = report.matches[1]
    else:
        report.matches.append(report.matches[0])
    with pytest.raises(ValueError):
        calculate_trends(report)


def test_catalog_contains_only_local_trend_facts_with_exact_evidence() -> None:
    report = load_demo_report()
    prepared = prepare_facts(report)
    context = json.loads(prepared.context)
    trends = [f for f in prepared.facts if f.fact_id.startswith("trend:")]
    assert {f.fact_id for f in trends} == {
        "trend:window",
        "trend:home",
        "trend:away",
        "trend:sequence",
        "trend:temporal",
    }
    assert context["trends"]["formula_version"] == "footballiq.trends.v1"
    for fact in trends:
        assert "Cobertura" in fact.text or "cobertura" in fact.text
        assert report.snapshot_version in fact.text
        for ref in fact.references:
            match = next(
                m
                for m in report.matches
                if ref == f"match:{m.reference.source_match_id}"
            )
            assert match.reference.data_version in fact.text
    selected = next(f for f in trends if f.fact_id == "trend:window")
    client = Mock()
    client.chat.return_value = json.dumps(
        {
            "summary": "selection",
            "observations": [
                {"fact_id": selected.fact_id, "references": selected.references}
            ],
        }
    )
    accepted = interpret_report(report, client)
    assert accepted.interpretation_status == "available"
    assert accepted.observations == (selected,)
    assert escape(selected.text, quote=True) in render_dashboard(report, accepted)


@pytest.mark.parametrize(
    "fact_id,refs",
    [
        ("trend:invented", ["match:6"]),
        ("trend:window", ["match:999"]),
        ("trend:window", ["match:6"]),
    ],
)
def test_invalid_trend_selection_falls_back_without_mutation(
    fact_id: str, refs: list[str]
) -> None:
    report = load_demo_report()
    before = report.model_dump_json()
    client = Mock()
    client.chat.return_value = json.dumps(
        {
            "summary": "selection",
            "observations": [{"fact_id": fact_id, "references": refs}],
        }
    )
    result = interpret_report(report, client)
    assert result.interpretation_status == "unavailable"
    assert report.model_dump_json() == before
    assert "Tendências competitivas" in render_dashboard(report, result)


@pytest.mark.parametrize("scenario", ["complete_five", "partial_match", "empty"])
def test_dashboard_remains_offline_with_trends_and_existing_sections(
    scenario: str,
) -> None:
    html = render_demo_dashboard(scenario)
    for title in (
        "Tendências competitivas",
        "DADOS FICTÍCIOS",
        "Referências auditáveis",
        "Estatísticas com contexto",
        "AI Analyst",
    ):
        assert title in html
    assert "mais antigo primeiro" in html
    assert "<script" not in html
    if scenario != "complete_five":
        assert "Indisponível" in html


def test_trend_html_escapes_versions_and_unavailable_state() -> None:
    report = load_demo_report()
    report.matches[0].reference.data_version = '<script>alert("x")</script>'
    html = render_dashboard(report)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    report.matches[0].score_status = "unverified"
    html = render_dashboard(report)
    assert "Subtotal apenas" in html
    assert "Cobertura 4/5" in html


def test_equal_instants_in_different_timezones_block_temporal_split() -> None:
    report = load_demo_report()
    instant = report.matches[2].kickoff_at
    report.matches[3].kickoff_at = instant.astimezone(timezone(timedelta(hours=2)))
    trends = calculate_trends(report)
    assert trends.temporal_reason == "tied_temporal_boundary"
    assert trends.games[1].kickoff_at == trends.games[2].kickoff_at


def test_contract_to_engine_to_trends_preserves_partial_coverage() -> None:
    payload = json.loads(
        (Path(__file__).parent / "fixtures/integration/complete_five.json").read_text(
            encoding="utf-8"
        )
    )
    payload["matches"][2]["score"]["status"] = "unverified"
    report = analyze_recent_matches(payload)
    trends = calculate_trends(report)
    metric = report.metrics["competitive"]
    assert trends.window.values is metric.values is None
    assert len(trends.window.used_ids) == metric.covered_matches == 4
    for key in (
        "wins",
        "draws",
        "losses",
        "average_goals_for",
        "average_goals_against",
    ):
        assert trends.window.covered_values[key] == metric.covered_values[key]
    assert trends.temporal_change is None


def test_timeout_preserves_factual_and_trend_sections() -> None:
    report = load_demo_report()
    before = report.model_dump_json()
    client = Mock()
    client.chat.side_effect = TimeoutError
    result = interpret_report(report, client)
    assert result.interpretation_status == "unavailable"
    assert "tempo de espera" in result.warning
    assert report.model_dump_json() == before
    assert "Tendências competitivas" in render_dashboard(report, result)


def test_catalog_ids_are_unique_stable_and_unavailable_facts_rejected() -> None:
    for scenario in ("complete_five", "partial_match", "empty"):
        report = load_demo_report(scenario)
        first = prepare_facts(report)
        second = prepare_facts(report)
        ids = [f.fact_id for f in first.facts]
        assert len(ids) == len(set(ids))
        assert first == second
        if scenario == "partial_match":
            assert "trend:window" not in ids
            assert "trend:temporal" not in ids
            client = Mock()
            client.chat.return_value = json.dumps(
                {
                    "summary": "selection",
                    "observations": [
                        {"fact_id": "trend:window", "references": ["match:901"]}
                    ],
                }
            )
            assert (
                interpret_report(report, client).interpretation_status == "unavailable"
            )


def test_all_scores_unverified_keep_aggregate_values_unavailable() -> None:
    report = load_demo_report()
    for match in report.matches:
        match.score_status = "unverified"
    trends = calculate_trends(report)
    assert trends.window.values is trends.window.covered_values is None
    assert trends.window.selected_ids == ("6", "7", "8", "9", "10")
    assert trends.window.used_ids == ()
    assert trends.temporal_change is None
    html = render_dashboard(report)
    assert "Cobertura 0/5" in html
    assert "Resultado não verificado" in html
    assert "unverified_result" not in html


def test_trends_are_navigable_and_display_rounding_is_explicit() -> None:
    report = load_demo_report()
    before = calculate_trends(report).to_dict()
    html = render_dashboard(report)
    assert '<a href="#trends">Tendências</a>' in html
    assert "≈ 1,333" in html
    assert "≈ -0,333" in html
    assert "-0.33333333333333337" not in html
    assert "não é um índice de estabilidade nem uma previsão" in html
    assert calculate_trends(report).to_dict() == before


def test_four_game_temporal_difference_matches_independent_means() -> None:
    report = load_demo_report()
    report.matches = report.matches[1:]
    trends = calculate_trends(report)
    assert trends.older.used_ids == ("6", "7")
    assert trends.newer.used_ids == ("8", "9")
    assert trends.temporal_change == {
        "average_goals_for": 1.0,
        "average_goals_against": -0.5,
    }
