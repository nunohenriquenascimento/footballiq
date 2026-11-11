"""Integração HTML offline: plano fechado, escaping e preservação factual."""

import html
import json
import re
import socket
from collections.abc import Iterator
from dataclasses import replace
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from footballiq.analyst_dashboard import render_dashboard
from footballiq.analyst_demo import load_demo_report, main, render_demo_dashboard
from footballiq.analytics import analyze_recent_matches
from footballiq.grounded_narrative import build_available_facts
from footballiq.grounded_narrative.orchestrator import NarrativeResult, narrate_report
from footballiq.trends import calculate_trends


@pytest.fixture(autouse=True)
def no_network() -> Iterator[None]:
    """Impede inferências reais e qualquer ligação, incluindo loopback."""
    with (
        patch.object(
            socket.socket, "connect", side_effect=AssertionError("No network")
        ),
        patch.object(
            socket, "create_connection", side_effect=AssertionError("No network")
        ),
    ):
        yield


def selected_client() -> Mock:
    """Simula apenas a escolha permitida; os factos vêm da fixture aprovada."""
    return Mock(chat=Mock(return_value='{"plan_id":"plan:1"}'))


def without_analyst(document: str) -> str:
    """Permite comparar byte a byte todas as secções factuais do HTML."""
    return re.sub(r'<aside class="panel ai".*?</aside>', "", document, flags=re.S)


def test_valid_narrative_uses_backend_and_preserves_all_other_sections() -> None:
    report = load_demo_report()
    before = report.model_dump_json()
    bundle = build_available_facts(report)
    trends = calculate_trends(report).to_dict()
    result = narrate_report(report, enabled=True, client=selected_client())
    document = render_dashboard(report, narrative=result)
    assert 'data-narrative-status="available"' in document
    assert "a equipa marcou 2 golos." in document
    assert "Amostra: 1 jogo." in document
    assert "Cobertura da observação: 1/5 jogos selecionados." in document
    assert "não é o total da janela" in document
    assert 'href="#match-0"' in document
    assert "<summary>Detalhes técnicos e evidências</summary>" in document
    assert all(identity in document for identity in result.references)
    assert without_analyst(document) == without_analyst(render_dashboard(report))
    assert report.model_dump_json() == before
    assert build_available_facts(report) == bundle
    assert calculate_trends(report).to_dict() == trends


def test_dataclass_text_and_references_are_never_authoritative() -> None:
    report = load_demo_report()
    result = narrate_report(report, enabled=True, client=selected_client())
    forged = replace(
        result, text="<script>RAW_MODEL_TEXT</script>", references=("invented",)
    )
    document = render_dashboard(report, narrative=forged)
    assert document == render_dashboard(report, narrative=result)
    assert "RAW_MODEL_TEXT" not in document and "invented" not in document


@pytest.mark.parametrize(
    "field", ["evidence", "snapshot", "coverage", "sample", "template", "missing_plan"]
)
def test_invalid_plan_never_displays_claims(field: str) -> None:
    report = load_demo_report()
    result = narrate_report(report, enabled=True, client=selected_client())
    assert result.plan is not None
    plan = result.plan.model_copy(deep=True)
    if field == "evidence":
        plan.assertions[0].references[0].evidence_id = "invented"
    elif field == "snapshot":
        plan.evidence_snapshot_id = "another-snapshot"
    elif field == "coverage":
        plan.coverage = 1.0
    elif field == "sample":
        plan.sample_size = 999
    elif field == "template":
        plan.assertions[0].template = "comparison_mean_ordered"
    document = render_dashboard(
        report,
        narrative=replace(result, plan=None if field == "missing_plan" else plan),
    )
    assert 'data-narrative-status="unavailable"' in document
    assert "a equipa marcou" not in document and "invented" not in document
    assert without_analyst(document) == without_analyst(render_dashboard(report))


@pytest.mark.parametrize(
    "error,expected",
    [(TimeoutError(), "tempo de espera"), (OSError(), "Narrativa indisponível")],
)
def test_transport_fallback_preserves_statistics(
    error: Exception, expected: str
) -> None:
    client = Mock(chat=Mock(side_effect=error))
    document = render_demo_dashboard(with_narrative=True, client=client)
    assert expected in document
    assert 'data-narrative-status="unavailable"' in document
    assert without_analyst(document) == without_analyst(render_demo_dashboard())
    client.chat.assert_called_once()


@pytest.mark.parametrize(
    "scenario,message",
    [("empty", "Sem jogos"), ("partial_match", "não estão verificados")],
)
def test_empty_and_unverified_skip_model(scenario: str, message: str) -> None:
    client = selected_client()
    document = render_demo_dashboard(scenario, with_narrative=True, client=client)
    assert message in document
    assert "a equipa marcou" not in document
    client.chat.assert_not_called()
    assert without_analyst(document) == without_analyst(render_demo_dashboard(scenario))


def test_partial_window_distinguishes_single_observation_coverage() -> None:
    payload = json.loads(
        (Path(__file__).parent / "fixtures/integration/complete_five.json").read_text(
            encoding="utf-8"
        )
    )
    payload["matches"][0]["score"]["status"] = "unverified"
    report = analyze_recent_matches(payload)
    result = narrate_report(report, enabled=True, client=selected_client())
    document = render_dashboard(report, narrative=result)
    assert "Cobertura da observação: 1/5" in document
    assert "não é o total da janela" in document
    assert "Cobertura 4/5" in document
    assert "Subtotal dos jogos cobertos" in document
    assert without_analyst(document) == without_analyst(render_dashboard(report))


def test_dynamic_names_are_escaped_even_for_valid_plans() -> None:
    report = load_demo_report()
    hostile = '<img src="https://invalid.test" onerror="alert(1)"> & Clube'
    report.matches[0].opponent_name = hostile
    result = narrate_report(report, enabled=True, client=selected_client())
    document = render_dashboard(report, narrative=result)
    assert 'data-narrative-status="available"' in document
    assert hostile not in document
    assert html.escape(hostile, quote=True) in document
    assert "<script" not in document and "<img" not in document
    assert "connect-src 'none'" in document and "script-src 'none'" in document
    assert "innerHTML" not in document


def test_unavailable_reason_cannot_expose_model_output() -> None:
    result = NarrativeResult(
        "unavailable", "<script>PRIVATE_RESPONSE</script>", "RAW_TEXT"
    )
    document = render_dashboard(load_demo_report(), narrative=result)
    assert "PRIVATE_RESPONSE" not in document and "RAW_TEXT" not in document


def test_default_and_disabled_do_not_consult_client() -> None:
    client = selected_client()
    assert render_demo_dashboard(client=client) == render_demo_dashboard()
    client.chat.assert_not_called()
    disabled = NarrativeResult("disabled", "opt_in_required")
    document = render_dashboard(load_demo_report(), narrative=disabled)
    assert "Não solicitada" in document
    assert 'data-narrative-status="disabled"' in document


def test_cli_html_narrative_is_explicit_and_preserves_options(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from footballiq import ollama_client

    client = selected_client()
    monkeypatch.setattr(ollama_client, "OllamaClient", Mock(return_value=client))
    path = tmp_path / "narrative.html"
    assert (
        main(["--html", "--with-narrative", "--model", "demo", "--output", str(path)])
        == 0
    )
    assert 'data-narrative-status="available"' in path.read_text(encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        main(["--html", "--with-narrative", "--with-llm"])
    assert error.value.code == 2


def test_json_and_schema_fallback_are_offline() -> None:
    for response in ("{", json.dumps({"plan_id": "plan:1", "text": "UNTRUSTED"})):
        client = Mock(chat=Mock(return_value=response))
        document = render_demo_dashboard(with_narrative=True, client=client)
        assert 'data-narrative-status="unavailable"' in document
        assert "UNTRUSTED" not in document


def test_narrative_html_uses_only_local_links_and_native_details() -> None:
    elements: list[tuple[str, dict[str, str | None]]] = []

    class Parser(HTMLParser):
        def handle_starttag(
            self, tag: str, attrs: list[tuple[str, str | None]]
        ) -> None:
            elements.append((tag, dict(attrs)))

    Parser().feed(render_demo_dashboard(with_narrative=True, client=selected_client()))
    ids = [attrs["id"] for _, attrs in elements if "id" in attrs]
    assert len(ids) == len(set(ids))
    assert any(tag == "details" for tag, _ in elements)
    for tag, attrs in elements:
        assert tag not in {"script", "iframe", "img", "link", "form"}
        assert not any(
            name.startswith("on") or name in {"src", "srcset"} for name in attrs
        )
        if "href" in attrs:
            href = attrs["href"]
            assert href is not None and href.startswith("#") and href[1:] in ids
