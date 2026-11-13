"""Regressões do catálogo, usando apenas fixtures sintéticas e rede bloqueada."""

import json
import socket
from datetime import timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest

from footballiq.analyst_demo import load_demo_report
from footballiq.analytics import analyze_recent_matches
from footballiq.grounded_narrative.contract import build_available_facts
from footballiq.grounded_narrative.insights import (
    build_insights,
    prepare_insight_plans,
    render_insight,
)
from footballiq.grounded_narrative.orchestrator import prepare_plans
from footballiq.trends import calculate_trends


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    monkeypatch.setattr(
        socket.socket, "connect", Mock(side_effect=AssertionError("Rede"))
    )
    monkeypatch.setattr(
        socket, "create_connection", Mock(side_effect=AssertionError("Rede"))
    )


def package():
    return json.loads(
        (Path(__file__).parent / "fixtures/integration/complete_five.json").read_text(
            encoding="utf-8"
        )
    )


def test_valid_catalog_preserves_factual_and_old_catalog():
    report = load_demo_report()
    before = report.model_dump_json()
    old = build_available_facts(report)
    bundle = build_insights(report)
    for identity, fact in old.items():
        assert bundle[identity] == fact
    assert prepare_plans(report, old)
    plans = prepare_insight_plans(bundle)
    assert {
        "insight:form",
        "insight:competitive",
        "insight:recent_vs_older",
        "insight:home_vs_away",
    } <= plans.keys()
    assert bundle["insight:form"]["value"]["wins"] == 2
    assert bundle["insight:competitive"]["value"]["goals_for"] == 4
    for identity, plan in plans.items():
        text = render_insight(plan, bundle)
        assert text == render_insight(plan, bundle)
        assert "Cobertura" in text and report.snapshot_version in text
        assert set(ref.evidence_id for ref in plan.assertions[0].references) == set(
            bundle.authorized_evidence_ids(identity)
        )
    assert build_insights(report) == bundle
    assert report.model_dump_json() == before


def test_partial_coverage_uses_engine_subtotals():
    payload = package()
    payload["matches"][2]["score"]["status"] = "unverified"
    report = analyze_recent_matches(payload)
    bundle = build_insights(report)
    fact = bundle["insight:competitive"]
    assert fact["coverage"] == 4 / 5
    assert (
        fact["value"]["goals_for"]
        == report.metrics["competitive"].covered_values["goals_for"]
    )
    assert "Apenas subtotal" in fact["text"]
    assert "insight:recent_vs_older" not in bundle
    assert "match:8" not in bundle["insight:form"]["references"]


@pytest.mark.parametrize("scenario", ["empty", "partial_match"])
def test_no_verified_data_has_no_insight_plans(scenario):
    assert prepare_insight_plans(build_insights(load_demo_report(scenario))) == {}


@pytest.mark.parametrize(
    "field,value",
    [("evidence_snapshot_id", "other"), ("coverage", 0.1), ("sample_size", 99)],
)
def test_wrong_snapshot_or_denominator_rejected(field, value):
    bundle = build_insights(load_demo_report())
    plan = prepare_insight_plans(bundle)["insight:form"].model_copy(deep=True)
    setattr(plan, field, value)
    with pytest.raises(ValueError):
        render_insight(plan, bundle)


@pytest.mark.parametrize(
    "field,value",
    [
        ("evidence_id", "evidence:false"),
        ("fact_id", "match:999"),
        ("fact_version", "false"),
    ],
)
def test_false_reference_rejected(field, value):
    bundle = build_insights(load_demo_report())
    plan = prepare_insight_plans(bundle)["insight:form"].model_copy(deep=True)
    setattr(plan.assertions[0].references[0], field, value)
    with pytest.raises(ValueError):
        render_insight(plan, bundle)


def test_deeply_immutable_values_and_provenance():
    bundle = build_insights(load_demo_report())
    with pytest.raises(TypeError):
        bundle["insight:form"]["value"]["wins"] = 99
    with pytest.raises(TypeError):
        bundle["insight:competitive"]["references"][0]["event_ids"][0] = "false"


def test_unverified_game_interrupts_streak():
    report = load_demo_report()
    report.matches[1].score_status = "unverified"  # Jogo 9, entre 8 e 10.
    assert "insight:winning_run" not in build_insights(report)
    report.matches[0].score_status = "unverified"
    assert not any(identity.endswith("_run") for identity in build_insights(report))


def test_tied_dates_block_streaks_and_temporal_comparison():
    report = load_demo_report()
    for match in report.matches:
        match.kickoff_at = report.matches[0].kickoff_at
    first = build_insights(report)
    report.matches.reverse()
    second = build_insights(report)
    assert "insight:recent_vs_older" not in first
    assert not any(identity.endswith("_run") for identity in first)
    assert first["insight:form"]["text"] == second["insight:form"]["text"]


def test_comparisons_use_actual_unequal_samples_and_venue():
    report = load_demo_report()
    bundle = build_insights(report)
    trends = calculate_trends(report)
    temporal = bundle["insight:recent_vs_older"]
    assert temporal["value"]["left_n"] == 3
    assert temporal["value"]["right_n"] == 2
    assert "Recentes (n=3)" in temporal["text"] and "Antigos (n=2)" in temporal["text"]
    for name, sample in (("home", trends.home), ("away", trends.away)):
        assert bundle[f"insight:{name}"]["references"] == tuple(
            f"match:{mid}" for mid in sample.used_ids
        )
    venue = bundle["insight:home_vs_away"]
    assert venue["value"]["left_n"] == len(trends.home.used_ids)
    assert venue["value"]["right_n"] == len(trends.away.used_ids)


def test_small_samples_are_descriptions_without_comparisons():
    payload = package()
    payload["matches"] = payload["matches"][:1]
    payload["selection"]["returned_count"] = 1
    report = analyze_recent_matches(payload)
    bundle = build_insights(report)
    assert "insight:form" in bundle
    assert "insight:recent_vs_older" not in bundle
    assert "insight:home_vs_away" not in bundle
    assert not any(identity.endswith("_run") for identity in bundle)


def test_temporal_metrics_reuse_engine_and_event_provenance():
    payload = package()
    payload["matches"] = payload["matches"][:4]
    payload["selection"]["returned_count"] = 4
    report = analyze_recent_matches(payload)
    bundle = build_insights(report)
    fact = bundle["insight:temporal_goals"]
    assert dict(fact["value"]) == report.metrics["temporal_goals"].covered_values
    assert "Minutos 90+" in fact["text"]
    assert "Médias" not in fact["text"]
    assert all(ref["event_ids"] for ref in fact["references"])


def test_unresolved_aggregate_provenance_is_omitted():
    report = load_demo_report()
    report.metrics["competitive"].references[0].source_match_id = "999"
    assert "insight:competitive" not in build_insights(report)


def test_temporal_missing_event_provenance_is_not_fabricated():
    report = load_demo_report()
    report.metrics["temporal_goals"].references[0].event_ids = []
    assert "insight:temporal_goals" not in build_insights(report)


def test_partial_temporal_data_keeps_covered_denominator():
    payload = package()
    payload["matches"][-1]["quality"]["score_events"]["status"] = "partial"
    payload["matches"][-1]["score"]["status"] = "unverified"
    report = analyze_recent_matches(payload)
    bundle = build_insights(report)
    fact = bundle["insight:temporal_goals"]
    assert fact["covered_matches"] == 4 and fact["selected_matches"] == 5
    assert dict(fact["value"]) == report.metrics["temporal_goals"].covered_values
    assert "Apenas subtotal" in fact["text"]


@pytest.mark.parametrize(
    "outcome,name",
    [
        ("win", "winning_run"),
        ("draw", "drawing_run"),
        ("loss", "losing_run"),
        ("draw", "winless_run"),
    ],
)
def test_verified_streaks_are_limited_to_window(outcome, name):
    report = load_demo_report()
    report.matches[0].kickoff_at += timedelta(hours=1)
    for match in report.matches[:2]:
        match.outcome = outcome
    bundle = build_insights(report)
    assert bundle[f"insight:{name}"]["value"]["length"] >= 2
    assert "janela" in bundle[f"insight:{name}"]["text"]


def test_unverified_streak_is_not_bridged_with_distinct_dates():
    report = load_demo_report()
    report.matches[0].kickoff_at += timedelta(hours=1)
    report.matches[1].score_status = "unverified"
    assert "insight:winning_run" not in build_insights(report)


def test_bundle_digest_binds_content_and_snapshot():
    report = load_demo_report()
    first = build_insights(report)
    report.snapshot_version = "another-snapshot"
    second = build_insights(report)
    assert first.evidence_digest != second.evidence_digest
    assert first.authorized_evidence_ids(
        "insight:form"
    ) != second.authorized_evidence_ids("insight:form")
    with pytest.raises(ValueError):
        render_insight(prepare_insight_plans(first)["insight:form"], second)


@pytest.mark.parametrize("tampering", ["duplicate", "swapped", "missing"])
def test_duplicate_swapped_or_missing_evidence_is_rejected(tampering: str) -> None:
    """IDs reais também são recusados se não pertencerem exatamente ao facto."""
    bundle = build_insights(load_demo_report())
    plan = prepare_insight_plans(bundle)["insight:form"].model_copy(deep=True)
    references = plan.assertions[0].references
    if tampering == "duplicate":
        references.append(references[0].model_copy())
    elif tampering == "swapped":
        references[0].evidence_id = bundle.authorized_evidence_ids("insight:home")[0]
    else:
        references.pop()
    with pytest.raises(ValueError):
        render_insight(plan, bundle)


@pytest.mark.parametrize("tampering", ["duplicate", "version", "events", "source"])
def test_metric_provenance_must_exactly_match_match_reference(tampering: str) -> None:
    """Não basta existir um jogo com o mesmo ID para autorizar um agregado."""
    report = load_demo_report()
    references = report.metrics["competitive"].references
    if tampering == "duplicate":
        references[1] = references[0].model_copy(deep=True)
    elif tampering == "version":
        references[0].data_version = "wrong-version"
    elif tampering == "events":
        references[0].event_ids = ["999999"]
    else:
        references[0].source_instance_id = "another-source"
    assert "insight:competitive" not in build_insights(report)


def test_expanded_bundle_invalidates_old_evidence_ids_without_changing_old_facts() -> (
    None
):
    """O digest liga cada plano a todo o conteúdo do respetivo bundle."""
    report = load_demo_report()
    old = build_available_facts(report)
    expanded = build_insights(report)
    assert old.snapshot_id == expanded.snapshot_id
    assert old.evidence_digest != expanded.evidence_digest
    assert old["match:10"] == expanded["match:10"]
    assert old.authorized_evidence_ids("match:10") != expanded.authorized_evidence_ids(
        "match:10"
    )
    with pytest.raises(ValueError):
        render_insight(prepare_plans(report, old)["plan:1"], expanded)


def test_equal_instants_with_different_timezones_still_block_sequences() -> None:
    """Um offset diferente não transforma um empate temporal numa sequência."""
    report = load_demo_report()
    report.matches[0].kickoff_at = report.matches[1].kickoff_at.astimezone(
        timezone(timedelta(hours=2))
    )
    bundle = build_insights(report)
    assert not any(identity.endswith("_run") for identity in bundle)


def test_winning_sequence_uses_portuguese_agreement() -> None:
    """A frase mantém a concordância sem depender do género do resultado."""
    report = load_demo_report()
    report.matches[0].kickoff_at += timedelta(hours=1)
    bundle = build_insights(report)
    plan = prepare_insight_plans(bundle)["insight:winning_run"]
    assert "2 vitórias consecutivas, com resultados verificados." in render_insight(
        plan, bundle
    )
