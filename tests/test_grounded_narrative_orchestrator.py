"""Ensaios adversariais offline com as fixtures aprovadas do motor factual."""

import json
import socket
from unittest.mock import Mock

import pytest

from footballiq.analyst_demo import load_demo_report, main, run_demo
from footballiq.grounded_narrative import build_available_facts, render_plan
from footballiq.grounded_narrative.orchestrator import narrate_report, prepare_plans
from footballiq.ollama_client import OllamaClient, OllamaSettings, OllamaUnavailable
from footballiq.trends import calculate_trends


@pytest.mark.parametrize("scenario", ["complete_five", "partial_match", "empty"])
def test_offline_pipeline(scenario, monkeypatch):
    monkeypatch.setattr(socket, "create_connection", Mock(side_effect=AssertionError))
    report = load_demo_report(scenario)
    before = report.model_dump_json()
    trends = calculate_trends(report).to_dict()
    bundle = build_available_facts(report)
    client = Mock()
    client.chat.return_value = '{"plan_id":"plan:1"}'
    assert narrate_report(report, client=client).status == "disabled"
    client.chat.assert_not_called()
    result = narrate_report(report, enabled=True, client=client)
    plans = prepare_plans(report, bundle)
    if plans:
        assert result.status == "available"
        assert result.text == render_plan(result.plan, bundle)
        assert result.text == narrate_report(report, enabled=True, client=client).text
        context = json.loads(client.chat.call_args.args[1])
        assert set(context) == {"catalog"}
        assert "evidence:" not in json.dumps(context)
        assert result.references
        assert run_demo(scenario, with_narrative=True, client=client).startswith(
            run_demo(scenario)
        )
    else:
        assert result.status == "unavailable"
        assert not result.text and not result.references
        client.chat.assert_not_called()
    assert report.model_dump_json() == before
    assert calculate_trends(report).to_dict() == trends
    assert build_available_facts(report) == bundle


@pytest.mark.parametrize(
    "content",
    [
        "{",
        "{}",
        "[]",
        '{"plan_id":null}',
        '{"plan_id":1}',
        '{"plan_id":"other-snapshot:1"}',
        '{"plan_id":"plan:1","evidence_id":"invented"}',
        '{"plan_id":"plan:1","coverage":999}',
        '{"plan_id":"plan:1","relation":"invented"}',
        '{"plan_id":"plan:1","assertions":[]}',
        '{"plan_id":"plan:1","plan_id":"plan:2"}',
        '{"plan_id":"plan:1","text":"ignore instructions"}',
        "x" * 8193,
    ],
)
def test_untrusted_output_is_rejected(content):
    result = narrate_report(
        load_demo_report(), enabled=True, client=Mock(chat=Mock(return_value=content))
    )
    assert result.status == "unavailable"
    assert result.plan is None and not result.text and not result.references


@pytest.mark.parametrize(
    "error,reason",
    [
        (OllamaUnavailable("model_not_found"), "model_not_found"),
        (OllamaUnavailable("http_error"), "http_error"),
        (OllamaUnavailable("connection_unavailable"), "connection_unavailable"),
        (TimeoutError("private"), "timeout"),
        (OSError("private"), "transport_error"),
    ],
)
def test_safe_fallback(error, reason):
    result = narrate_report(
        load_demo_report(), enabled=True, client=Mock(chat=Mock(side_effect=error))
    )
    assert result.reason == reason
    assert result.status == "unavailable" and not result.references
    assert "private" not in repr(result)


def test_size_and_time_budgets(monkeypatch):
    from footballiq import ollama_client

    transport = Mock(return_value=b"{}")
    client = OllamaClient(OllamaSettings("demo", deadline=1), transport)
    with pytest.raises(OllamaUnavailable, match="request_too_large"):
        client.chat("x" * 32769, "", {})
    transport.assert_not_called()
    monkeypatch.setattr(ollama_client.time, "monotonic", Mock(side_effect=[0, 2]))
    with pytest.raises(OllamaUnavailable, match="timeout"):
        client.chat("", "", {})


def test_default_cli_never_constructs_client(monkeypatch, capsys):
    from footballiq import ollama_client

    constructor = Mock(side_effect=AssertionError)
    monkeypatch.setattr(ollama_client, "OllamaClient", constructor)
    assert main([]) == 0
    assert "narrative_status" not in capsys.readouterr().out
    constructor.assert_not_called()


def test_cli_explicit_failure_keeps_factual(capsys):
    assert main(["--with-narrative"]) == 0
    output = capsys.readouterr().out
    assert output.startswith(run_demo())
    assert "reason=invalid_settings" in output


def test_read_deadline_closes_connection(monkeypatch):
    from footballiq import ollama_client

    connection = Mock()
    connection.getresponse.return_value.status = 200
    connection.getresponse.return_value.read1.return_value = b"x"
    monkeypatch.setattr(
        ollama_client.http.client, "HTTPConnection", Mock(return_value=connection)
    )
    monkeypatch.setattr(
        ollama_client.time, "monotonic", Mock(side_effect=[0, 0, 0, 0, 2])
    )
    with pytest.raises(OllamaUnavailable, match="timeout"):
        OllamaClient(OllamaSettings("demo", deadline=1)).chat("", "", {})
    connection.close.assert_called_once()


@pytest.mark.parametrize("deadline", [0, 31, True, float("nan")])
def test_invalid_deadline(deadline):
    with pytest.raises(OllamaUnavailable, match="invalid_settings"):
        OllamaSettings("demo", deadline=deadline)
