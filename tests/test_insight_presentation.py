"""Revalidação e projeção de apresentação com fixtures sintéticas e rede bloqueada."""

import json
import socket
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from unittest.mock import Mock

import pytest

from footballiq import insight_presentation as view
from footballiq.analyst_demo import load_demo_report
from footballiq.analytics import analyze_recent_matches
from footballiq.grounded_narrative import multi_insights as multi
from footballiq.grounded_narrative.contract import EvidenceBundle, _content_digest
from footballiq.grounded_narrative.insights import build_insights
from footballiq.trends import calculate_trends


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Qualquer ligação, incluindo loopback, faz falhar o teste."""
    blocked = Mock(side_effect=AssertionError("network forbidden"))
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    yield
    blocked.assert_not_called()


def report_for(rich=True, partial=False):
    """Reutiliza variantes sintéticas sem editar fixtures em disco."""
    data = json.loads(
        (Path(__file__).parent / "fixtures/integration/complete_five.json").read_text(
            encoding="utf-8"
        )
    )
    if rich:
        data["matches"] = data["matches"][:4]
        data["selection"]["returned_count"] = 4
        data["matches"][0]["kickoff_at"] = "2026-11-08T16:00:00Z"
    if partial:
        data["matches"][-1]["quality"]["score_events"]["status"] = "partial"
        data["matches"][-1]["score"]["status"] = "unverified"
    return analyze_recent_matches(data)


def selected(report, ids):
    return multi.narrate_insights(
        report,
        enabled=True,
        client=Mock(chat=Mock(return_value=json.dumps({"plan_ids": ids}))),
    )


def assert_rejected(result):
    assert result.status == "unavailable"
    assert not result.items and result.provenance is None


@pytest.mark.parametrize("size", [1, 2, 3])
def test_valid_cards_order_provenance_and_immutability(size, monkeypatch):
    report = report_for()
    ids = ["insight:temporal_goals", "insight:recent_vs_older", "insight:form"][:size]
    result = selected(report, ids)
    before = report.model_dump_json()
    trends = calculate_trends(report).to_dict()
    bundle = build_insights(report)
    builder = Mock(wraps=view.build_insights)
    renderer = Mock(wraps=view.render_insight)
    monkeypatch.setattr(view, "build_insights", builder)
    monkeypatch.setattr(view, "render_insight", renderer)
    presentation = view.prepare_insights_presentation(report, result)
    assert presentation.status == "available"
    assert [c.plan_id for c in presentation.items] == ids
    assert [c.ordinal for c in presentation.items] == list(range(1, size + 1))
    assert len({c.family for c in presentation.items}) == size
    builder.assert_called_once_with(report)
    assert len(renderer.call_args_list) == size
    assert len({id(call.args[1]) for call in renderer.call_args_list}) == 1
    assert report.model_dump_json() == before
    assert calculate_trends(report).to_dict() == trends
    assert build_insights(report) == bundle
    assert presentation.provenance.snapshot_id == bundle.snapshot_id
    assert presentation.provenance.evidence_digest == bundle.evidence_digest
    assert "\n".join(c.canonical_text for c in presentation.items) == result.text
    assert (
        tuple(e.evidence_id for c in presentation.items for e in c.evidence_refs)
        == result.references
    )
    for card in presentation.items:
        assert card.formatting_status == "projected_v1"
        assert card.display_text and card.canonical_text.startswith(card.display_text)
        assert card.descriptive_limit
        assert card.coverage == card.covered_matches / card.selected_matches
        assert card.sample_size == card.covered_matches
        assert card.fact_version == "footballiq.insights.v1"
        assert card.formula_version == bundle[card.plan_id]["formula_version"]
        expected_refs = tuple(
            ref if isinstance(ref, str) else f"match:{ref['source_match_id']}"
            for ref in bundle[card.plan_id]["references"]
        )
        assert card.match_refs == expected_refs
        assert all(e.fact_id == card.plan_id for e in card.evidence_refs)
        assert all(
            e.evidence_digest == bundle.evidence_digest for e in card.evidence_refs
        )
        with pytest.raises(FrozenInstanceError):
            card.display_text = "changed"
        with pytest.raises(FrozenInstanceError):
            card.evidence_refs[0].evidence_id = "changed"
    with pytest.raises(FrozenInstanceError):
        presentation.provenance.snapshot_id = "changed"
    with pytest.raises(FrozenInstanceError):
        presentation.items = ()


def test_complete_five_two_families():
    report = load_demo_report()
    result = selected(report, ["insight:form", "insight:recent_vs_older"])
    assert len(view.prepare_insights_presentation(report, result).items) == 2


@pytest.mark.parametrize(
    "ids",
    [
        (),
        ("insight:missing",),
        ("insight:form", "insight:form"),
        ("insight:competitive",),
        ("insight:form", "insight:competitive"),
        ("insight:form", "insight:missing"),
        (
            "insight:form",
            "insight:recent_vs_older",
            "insight:temporal_goals",
            "insight:winning_run",
        ),
    ],
)
def test_invalid_ids_are_atomic(ids):
    report = report_for()
    valid = selected(report, ["insight:form"])
    presentation = view.prepare_insights_presentation(
        report, replace(valid, plan_ids=ids)
    )
    assert_rejected(presentation)
    assert presentation.reason_code == "invalid_selection"


@pytest.mark.parametrize(
    "field,value",
    [
        ("text", "UNTRUSTED"),
        ("references", ("invented",)),
        ("snapshot_id", "old"),
        ("evidence_digest", "old"),
    ],
)
def test_tampered_result_is_atomic(field, value):
    report = report_for()
    result = selected(report, ["insight:form", "insight:recent_vs_older"])
    assert_rejected(
        view.prepare_insights_presentation(report, replace(result, **{field: value}))
    )


def test_reference_order_and_multiplicity_are_exact():
    report = report_for()
    result = selected(report, ["insight:form", "insight:recent_vs_older"])
    for references in [
        tuple(reversed(result.references)),
        result.references + result.references[:1],
        result.references[:-1],
    ]:
        assert_rejected(
            view.prepare_insights_presentation(
                report, replace(result, references=references)
            )
        )


@pytest.mark.parametrize("change", ["snapshot", "data_version", "opponent", "report"])
def test_old_or_foreign_result_is_rejected(change):
    report = report_for()
    result = selected(report, ["insight:form", "insight:recent_vs_older"])
    if change == "snapshot":
        report.snapshot_version = "new-snapshot"
    elif change == "data_version":
        report.matches[0].reference.data_version = "new-version"
    elif change == "opponent":
        report.matches[0].opponent_name = "Outro clube sintético"
    else:
        report = load_demo_report()
    assert_rejected(view.prepare_insights_presentation(report, result))


@pytest.mark.parametrize(
    "reason",
    [
        "no_facts",
        "no_eligible_insights",
        "timeout",
        "invalid_selection",
        "insufficient_diversity",
        "invalid_plan",
        "invalid_settings",
        "connection_unavailable",
        "model_not_found",
        "client_required",
        "demo_only",
        "https://secret.example/password",
        "http_error",
    ],
)
def test_safe_states_without_bundle(reason, monkeypatch):
    builder = Mock(side_effect=AssertionError("bundle not needed"))
    monkeypatch.setattr(view, "build_insights", builder)
    result = multi.InsightNarrativeResult(
        "unavailable", reason, "SECRET", ("secret",), ("secret",), "secret", "secret"
    )
    presentation = view.prepare_insights_presentation(load_demo_report(), result)
    assert_rejected(presentation)
    assert "SECRET" not in repr(presentation) and "https://" not in repr(presentation)
    assert presentation.reason_code in view._MESSAGES
    builder.assert_not_called()


def test_none_disabled_unknown_and_empty(monkeypatch):
    report = load_demo_report()
    builder = Mock(side_effect=AssertionError("bundle not needed"))
    monkeypatch.setattr(view, "build_insights", builder)
    assert view.prepare_insights_presentation(report, None).status == "not_requested"
    disabled = multi.InsightNarrativeResult("disabled", "private")
    assert view.prepare_insights_presentation(report, disabled).status == "disabled"
    unknown = multi.InsightNarrativeResult("unknown", "private")
    assert_rejected(view.prepare_insights_presentation(report, unknown))
    available = multi.InsightNarrativeResult("available", "validated")
    assert (
        view.prepare_insights_presentation(
            load_demo_report("empty"), available
        ).reason_code
        == "no_facts"
    )
    builder.assert_not_called()


def test_partial_temporal_subtotal_keeps_denominator():
    report = report_for(rich=False, partial=True)
    result = selected(report, ["insight:temporal_goals"])
    presentation = view.prepare_insights_presentation(report, result)
    assert presentation.status == "available"
    card = presentation.items[0]
    assert (card.covered_matches, card.selected_matches, card.sample_size) == (4, 5, 4)
    assert card.coverage == 0.8 and card.subtotal_notice == view._SUBTOTAL
    assert card.formatting_status == "projected_v1"


def test_family_policy_is_reused_even_with_manipulated_shortlist(monkeypatch):
    report = report_for()
    candidates = multi.prepare_insight_candidates(build_insights(report))
    monkeypatch.setattr(multi, "prepare_insight_shortlist", lambda bundle: candidates)
    forged = multi.InsightNarrativeResult(
        "available", "validated", plan_ids=("insight:form", "insight:competitive")
    )
    presentation = view.prepare_insights_presentation(report, forged)
    assert_rejected(presentation)
    assert presentation.reason_code == "insufficient_diversity"


def test_one_bad_plan_rejects_previous_good_card(monkeypatch):
    report = report_for()
    result = selected(report, ["insight:form", "insight:recent_vs_older"])
    prepare = multi.prepare_insight_shortlist

    def corrupt(bundle):
        plans = prepare(bundle)
        plans["insight:recent_vs_older"].assertions[0].references[
            0
        ].fact_version = "wrong"
        return plans

    monkeypatch.setattr(multi, "prepare_insight_shortlist", corrupt)
    assert_rejected(view.prepare_insights_presentation(report, result))


@pytest.mark.parametrize("format_change", ["version", "suffix", "body_terms", "mixed"])
def test_trusted_format_projection_and_fallback_without_changing_catalog(
    format_change, monkeypatch
):
    # Simula saída futura do backend, não texto ou evidências de um modelo.
    report = report_for()
    original = build_insights(report)
    from footballiq.grounded_narrative.contract import _plain_fact_value

    facts = _plain_fact_value(original.facts)
    ids = ["insight:form", "insight:recent_vs_older"]
    if format_change == "version":
        for identity in ids:
            facts[identity]["fact_version"] = "footballiq.insights.v2"
    elif format_change in {"suffix", "mixed"}:
        facts[ids[0]]["text"] += " Novo formato."
    else:
        facts[ids[0]]["text"] = (
            "Snapshot e Cobertura no corpo futebolístico. " + facts[ids[0]]["text"]
        )
    bundle = EvidenceBundle(original.snapshot_id, _content_digest(facts), facts)
    monkeypatch.setattr(multi, "build_insights", lambda report: bundle)
    monkeypatch.setattr(view, "build_insights", lambda report: bundle)
    result = selected(report, ids)
    assert result.status == "available"
    presentation = view.prepare_insights_presentation(report, result)
    assert presentation.status == "available"
    card = presentation.items[0]
    if format_change == "body_terms":
        assert card.formatting_status == "projected_v1"
        assert card.display_text.startswith(
            "Snapshot e Cobertura no corpo futebolístico."
        )
    else:
        assert card.formatting_status == "canonical_fallback"
        assert card.display_text == card.canonical_text == facts[ids[0]]["text"]
        assert not presentation.provenance.descriptive_limit
    assert bundle.evidence_digest == _content_digest(facts)


def test_projection_preserves_reference_order_and_exact_suffix():
    versions = (("2", "b"), ("1", "a"))
    suffix = (
        " Cobertura 2/2; amostra 2. "
        + view._LIMIT
        + " Snapshot s; catálogo footballiq.insights.v1; fórmula f; versões 2@b; 1@a."
    )
    text = "Snapshot e Cobertura são termos do corpo." + suffix
    projected = view._project_text(
        text, "footballiq.insights.v1", 2, 2, "s", "f", versions
    )
    assert projected[0] == "Snapshot e Cobertura são termos do corpo."
    assert (
        view._project_text(
            text, "footballiq.insights.v1", 2, 2, "s", "f", tuple(reversed(versions))
        )[0]
        == text
    )


def test_available_without_eligible_data_is_safe():
    forged = multi.InsightNarrativeResult("available", "validated")
    result = view.prepare_insights_presentation(
        load_demo_report("partial_match"), forged
    )
    assert_rejected(result)
    assert result.reason_code == "no_eligible_insights"


def test_incompatible_card_versions_are_not_grouped(monkeypatch):
    from footballiq.grounded_narrative.contract import _plain_fact_value

    report = report_for()
    original = build_insights(report)
    facts = _plain_fact_value(original.facts)
    facts["insight:recent_vs_older"]["fact_version"] = "footballiq.insights.v2"
    bundle = EvidenceBundle(original.snapshot_id, _content_digest(facts), facts)
    monkeypatch.setattr(multi, "build_insights", lambda report: bundle)
    monkeypatch.setattr(view, "build_insights", lambda report: bundle)
    result = selected(report, ["insight:form", "insight:recent_vs_older"])
    assert result.status == "available"
    assert_rejected(view.prepare_insights_presentation(report, result))
