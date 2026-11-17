"""HTML Multi-Insights revalidado, com fixtures sintéticas e rede bloqueada."""

import html
import json
import re
import socket
from dataclasses import replace
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import Mock

import pytest

from footballiq import analyst_dashboard as dashboard
from footballiq import insight_presentation as view
from footballiq import ollama_client
from footballiq.analyst_demo import load_demo_report
from footballiq.analyst_interpretation import InterpretationResult
from footballiq.analytics import analyze_recent_matches
from footballiq.grounded_narrative import multi_insights as multi
from footballiq.grounded_narrative.contract import (
    EvidenceBundle,
    _content_digest,
    _plain_fact_value,
)
from footballiq.grounded_narrative.insights import build_insights
from footballiq.grounded_narrative.orchestrator import NarrativeResult
from footballiq.trends import calculate_trends


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Nem o renderer nem os exemplos podem consultar modelos ou outros serviços."""
    blocked = Mock(side_effect=AssertionError("network forbidden"))
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(ollama_client, "OllamaClient", blocked)
    yield
    blocked.assert_not_called()


def rich_report():
    data = json.loads(
        (Path(__file__).parent / "fixtures/integration/complete_five.json").read_text(
            encoding="utf-8"
        )
    )
    data["matches"] = data["matches"][:4]
    data["selection"]["returned_count"] = 4
    data["matches"][0]["kickoff_at"] = "2026-11-08T16:00:00Z"
    return analyze_recent_matches(data)


def selected(report, ids):
    return multi.narrate_insights(
        report,
        enabled=True,
        client=Mock(chat=Mock(return_value=json.dumps({"plan_ids": ids}))),
    )


class Document(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.elements = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def without_panel(document):
    return re.sub(
        r'<aside class="panel ai".*?</aside>', "", document, flags=re.S
    ).replace(dashboard._INSIGHT_CSS, "")


@pytest.mark.parametrize("size", [1, 2, 3])
def test_valid_cards_semantics_order_provenance_and_factual_invariance(
    size, monkeypatch
):
    report = rich_report()
    ids = ["insight:temporal_goals", "insight:recent_vs_older", "insight:form"][:size]
    result = selected(report, ids)
    before = report.model_dump_json()
    trends = calculate_trends(report).to_dict()
    bundle = build_insights(report)
    prepare = Mock(wraps=view.prepare_insights_presentation)
    monkeypatch.setattr(view, "prepare_insights_presentation", prepare)
    monkeypatch.setattr(
        multi, "narrate_insights", Mock(side_effect=AssertionError("no reselection"))
    )
    document = dashboard.render_dashboard(report, insights=result)
    prepare.assert_called_once_with(report, result)
    parsed = Document(document)
    assert (
        sum(
            tag == "aside" and attrs.get("id") == "analyst"
            for tag, attrs in parsed.elements
        )
        == 1
    )
    assert document.count('<h2 id="analyst-title">AI Analyst</h2>') == 1
    assert document.count('class="insight-card"') == size
    assert document.count('<h3 id="insight-title-') == size
    assert document.count("<summary>Proveniência comum da seleção</summary>") == 1
    assert 'data-insights-status="available"' in document
    local_ids = [a["id"] for _, a in parsed.elements if "id" in a]
    assert len(local_ids) == len(set(local_ids))
    for _, attrs in parsed.elements:
        if "href" in attrs:
            assert attrs["href"].startswith("#") and attrs["href"][1:] in local_ids
        assert "src" not in attrs
    assert not any(tag == "script" for tag, _ in parsed.elements)
    assert "script-src 'none'; connect-src 'none'" in document
    presentation = view.prepare_insights_presentation(report, result)
    positions = []
    for card in presentation.items:
        assert html.escape(card.canonical_text, quote=True) in document
        assert html.escape(card.display_text, quote=True) in document
        assert (
            f"Cobertura {card.covered_matches}/{card.selected_matches} · amostra {card.sample_size}"
            in document
        )
        positions.append(document.index(f"<dd>{html.escape(card.plan_id)}</dd>"))
        assert card.formula_version in document
        assert all(html.escape(e.evidence_id) in document for e in card.evidence_refs)
        assert all(
            html.escape(version) in document for _, version in card.match_versions
        )
    assert positions == sorted(positions)
    assert without_panel(document) == without_panel(dashboard.render_dashboard(report))
    assert report.model_dump_json() == before
    assert calculate_trends(report).to_dict() == trends
    assert build_insights(report) == bundle


def test_complete_five_two_cards():
    report = load_demo_report()
    result = selected(report, ["insight:form", "insight:recent_vs_older"])
    assert (
        dashboard.render_dashboard(report, insights=result).count(
            'class="insight-card"'
        )
        == 2
    )


@pytest.mark.parametrize(
    "reason",
    [
        "timeout",
        "invalid_selection",
        "insufficient_diversity",
        "invalid_plan",
        "no_facts",
        "no_eligible_insights",
        "invalid_settings",
        "connection_unavailable",
        "model_not_found",
        "client_required",
        "demo_only",
        "https://private.example/secret",
    ],
)
def test_unavailable_never_exposes_rejected_data(reason):
    report = load_demo_report()
    result = multi.InsightNarrativeResult(
        "unavailable",
        reason,
        "PRIVATE_TEXT",
        ("PRIVATE_ID",),
        ("PRIVATE_EVIDENCE",),
        "PRIVATE_SNAPSHOT",
        "PRIVATE_DIGEST",
    )
    document = dashboard.render_dashboard(report, insights=result)
    assert 'data-insights-status="unavailable"' in document
    assert "PRIVATE_" not in document and "https://private" not in document
    assert 'class="insight-card"' not in document
    assert "Proveniência comum da seleção" not in document
    assert without_panel(document) == without_panel(dashboard.render_dashboard(report))


def test_disabled_and_empty():
    disabled = multi.InsightNarrativeResult("disabled", "opt_in_required")
    document = dashboard.render_dashboard(load_demo_report(), insights=disabled)
    assert 'data-insights-status="disabled"' in document
    assert 'class="insight-card"' not in document
    empty = load_demo_report("empty")
    result = multi.narrate_insights(empty, enabled=True)
    document = dashboard.render_dashboard(empty, insights=result)
    assert "Sem jogos neste snapshot" in document
    assert without_panel(document) == without_panel(dashboard.render_dashboard(empty))


@pytest.mark.parametrize(
    "field,value",
    [
        ("text", "PRIVATE_TEXT"),
        ("references", ("PRIVATE_EVIDENCE",)),
        ("snapshot_id", "PRIVATE_SNAPSHOT"),
        ("evidence_digest", "PRIVATE_DIGEST"),
        ("plan_ids", ("insight:form", "insight:competitive")),
    ],
)
def test_atomic_rejection_of_forged_selection(field, value):
    report = rich_report()
    result = selected(report, ["insight:form", "insight:recent_vs_older"])
    document = dashboard.render_dashboard(
        report, insights=replace(result, **{field: value})
    )
    assert 'data-insights-status="unavailable"' in document
    assert 'class="insight-card"' not in document and "PRIVATE_" not in document
    assert "Proveniência comum da seleção" not in document


@pytest.mark.parametrize(
    "pair",
    ["interpretation_narrative", "interpretation_insights", "narrative_insights"],
)
def test_layers_are_mutually_exclusive(pair):
    options = dict(
        interpretation=InterpretationResult("unavailable"),
        narrative=NarrativeResult("disabled", "opt_in_required"),
        insights=multi.InsightNarrativeResult("disabled", "opt_in_required"),
    )
    options = {key: options[key] for key in pair.split("_")}
    with pytest.raises(ValueError, match="apenas uma camada"):
        dashboard.render_dashboard(load_demo_report(), **options)


@pytest.mark.parametrize("scenario", ["complete_five", "partial_match", "empty"])
def test_none_preserves_legacy_and_skips_adapter(scenario, monkeypatch):
    monkeypatch.setattr(
        view,
        "prepare_insights_presentation",
        Mock(side_effect=AssertionError("not requested")),
    )
    report = load_demo_report(scenario)
    assert dashboard.render_dashboard(report) == dashboard.render_dashboard(
        report, insights=None
    )


def test_formatting_fallback_and_adversarial_text_are_escaped(monkeypatch):
    report = rich_report()
    report.snapshot_version = 'snap"><img src=x onerror=alert(1)>'
    report.matches[0].reference.data_version = 'v"><img src=x onerror=alert(2)>'
    report.matches[0].opponent_name = "<img src=x onerror=alert(3)>"
    original = build_insights(report)
    facts = _plain_fact_value(original.facts)
    identity = "insight:form"
    facts[identity]["text"] += " <img src=x onerror=alert(4)>"
    bundle = EvidenceBundle(original.snapshot_id, _content_digest(facts), facts)
    monkeypatch.setattr(multi, "build_insights", lambda report: bundle)
    monkeypatch.setattr(view, "build_insights", lambda report: bundle)
    result = selected(report, [identity])
    assert result.status == "available"
    document = dashboard.render_dashboard(report, insights=result)
    assert 'data-insights-status="available"' in document
    assert html.escape(result.text, quote=True) in document
    assert "Projeção visual não disponível" in document
    assert not any(tag == "img" for tag, _ in Document(document).elements)
    assert "<img" not in document
    assert "&lt;img" in document


def test_partial_card_keeps_subtotal():
    data = json.loads(
        (Path(__file__).parent / "fixtures/integration/complete_five.json").read_text(
            encoding="utf-8"
        )
    )
    data["matches"][-1]["quality"]["score_events"]["status"] = "partial"
    data["matches"][-1]["score"]["status"] = "unverified"
    report = analyze_recent_matches(data)
    result = selected(report, ["insight:temporal_goals"])
    document = dashboard.render_dashboard(report, insights=result)
    assert "Cobertura 4/5 · amostra 4." in document
    assert '<p class="subtotal">Apenas subtotal dos jogos cobertos.</p>' in document


def test_arbitrary_presentation_is_not_trusted():
    presentation = view.InsightsPresentation("available", "validated", "UNTRUSTED")
    document = dashboard.render_dashboard(load_demo_report(), insights=presentation)
    assert 'data-insights-status="unavailable"' in document
    assert "UNTRUSTED" not in document
