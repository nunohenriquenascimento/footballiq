"""Integração CLI/API dos insights HTML, exclusivamente offline."""

import json
import socket
import webbrowser
from pathlib import Path
from unittest.mock import Mock

import pytest

from footballiq import analyst_demo as demo
from footballiq import ollama_client
from footballiq.grounded_narrative import multi_insights as multi


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Bloqueia todas as ligações, incluindo inferência em loopback."""
    blocked = Mock(side_effect=AssertionError("network forbidden"))
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    yield
    blocked.assert_not_called()


def fake_client():
    return Mock(
        chat=Mock(
            return_value=json.dumps(
                {"plan_ids": ["insight:form", "insight:recent_vs_older"]}
            )
        )
    )


def test_deterministic_api_two_cards_without_client(monkeypatch):
    constructor = Mock(side_effect=AssertionError("no client"))
    monkeypatch.setattr(ollama_client, "OllamaClient", constructor)
    client = fake_client()
    document = demo.render_demo_dashboard(insights="deterministic", client=client)
    assert document.count('class="insight-card"') == 2
    assert 'data-insights-status="available"' in document
    client.chat.assert_not_called()
    constructor.assert_not_called()


def test_html_open_command_writes_two_cards_and_opens_only_local_file(
    tmp_path, monkeypatch, capsys
):
    destination = tmp_path / "insights.html"
    opened = Mock(return_value=True)
    monkeypatch.setattr(webbrowser, "open", opened)
    monkeypatch.setattr(
        ollama_client, "OllamaClient", Mock(side_effect=AssertionError("no client"))
    )
    assert (
        demo.main(
            [
                "--html",
                "--insights",
                "deterministic",
                "--open",
                "--output",
                str(destination),
            ]
        )
        == 0
    )
    document = destination.read_text(encoding="utf-8")
    assert document.count('class="insight-card"') == 2
    opened.assert_called_once_with(destination.as_uri())
    assert "Dashboard criado:" in capsys.readouterr().out


def test_exact_requested_command_uses_default_temporary_file(tmp_path, monkeypatch):
    from footballiq import analyst_dashboard

    save = analyst_dashboard.save_dashboard
    destination = tmp_path / "temporary.html"
    writer = Mock(
        side_effect=lambda document, output, overwrite: save(
            document, destination, overwrite=overwrite
        )
    )
    monkeypatch.setattr(analyst_dashboard, "save_dashboard", writer)
    opened = Mock(return_value=True)
    monkeypatch.setattr(webbrowser, "open", opened)
    assert demo.main(["--html", "--insights", "deterministic", "--open"]) == 0
    assert writer.call_args.args[1] is None
    assert destination.read_text(encoding="utf-8").count('class="insight-card"') == 2
    opened.assert_called_once_with(destination.as_uri())


@pytest.mark.parametrize("html_mode", [False, True])
def test_same_selector_is_called_once_for_text_and_html(html_mode, monkeypatch):
    client = fake_client()
    selector = Mock(wraps=multi.narrate_insights)
    monkeypatch.setattr(multi, "narrate_insights", selector)
    renderer = demo.render_demo_dashboard if html_mode else demo.run_demo
    output = renderer(insights="ollama", client=client)
    selector.assert_called_once()
    client.chat.assert_called_once()
    assert (
        ('data-insights-status="available"' in output)
        if html_mode
        else ("insights_status=available" in output)
    )


def test_html_cli_ollama_uses_injected_fake_constructor_once(tmp_path, monkeypatch):
    client = fake_client()
    constructor = Mock(return_value=client)
    monkeypatch.setattr(ollama_client, "OllamaClient", constructor)
    opened = Mock()
    monkeypatch.setattr(webbrowser, "open", opened)
    destination = tmp_path / "fake.html"
    assert (
        demo.main(
            [
                "--html",
                "--insights",
                "ollama",
                "--model",
                "synthetic-model",
                "--output",
                str(destination),
            ]
        )
        == 0
    )
    constructor.assert_called_once()
    settings = constructor.call_args.args[0]
    assert settings.timeout == 5 and settings.deadline == 15
    assert settings.url == "http://127.0.0.1:11434"
    client.chat.assert_called_once()
    opened.assert_not_called()
    assert destination.read_text(encoding="utf-8").count('class="insight-card"') == 2


@pytest.mark.parametrize("scenario", ["empty", "partial_match"])
@pytest.mark.parametrize("mode", ["ollama", "deterministic"])
def test_no_eligible_data_never_calls_chat(scenario, mode):
    client = fake_client()
    document = demo.render_demo_dashboard(scenario, insights=mode, client=client)
    client.chat.assert_not_called()
    assert 'data-insights-status="unavailable"' in document
    assert 'class="insight-card"' not in document


@pytest.mark.parametrize(
    "response",
    [
        "{",
        '{"plan_ids":["insight:form","insight:competitive"]}',
        '{"plan_ids":["insight:form","insight:missing"]}',
    ],
)
def test_invalid_selection_no_retry_no_partial_html(response):
    client = Mock(chat=Mock(return_value=response))
    document = demo.render_demo_dashboard(insights="ollama", client=client)
    assert 'data-insights-status="unavailable"' in document
    assert 'class="insight-card"' not in document
    client.chat.assert_called_once()


def test_timeout_has_safe_html_without_retry():
    client = Mock(chat=Mock(side_effect=TimeoutError("PRIVATE_ERROR")))
    document = demo.render_demo_dashboard(insights="ollama", client=client)
    assert "tempo de espera" in document and "PRIVATE_ERROR" not in document
    assert 'class="insight-card"' not in document
    client.chat.assert_called_once()


def test_invalid_settings_never_construct_client(monkeypatch):
    constructor = Mock(side_effect=AssertionError("no client"))
    monkeypatch.setattr(ollama_client, "OllamaClient", constructor)
    document = demo.render_demo_dashboard(
        insights="ollama", model="invalid model", ollama_url="https://private.example"
    )
    assert 'data-insights-status="unavailable"' in document
    assert "private.example" not in document
    constructor.assert_not_called()


@pytest.mark.parametrize("option", ["--with-llm", "--with-narrative"])
def test_cli_competing_layers_fail_before_selection(option, monkeypatch):
    selector = Mock(side_effect=AssertionError("no selection"))
    monkeypatch.setattr(demo, "_select_insights", selector)
    with pytest.raises(SystemExit) as error:
        demo.main(["--html", "--insights", "deterministic", option])
    assert error.value.code == 2
    selector.assert_not_called()


@pytest.mark.parametrize(
    "options", [{"with_llm": True}, {"with_narrative": True}, {"insights": "unknown"}]
)
def test_api_competing_or_invalid_modes_rejected(options):
    kwargs = {"insights": "deterministic", **options}
    with pytest.raises(ValueError, match="único modo"):
        demo.render_demo_dashboard(**kwargs)


def test_overwrite_and_open_safety(tmp_path, monkeypatch):
    destination = tmp_path / "existing.html"
    destination.write_text("KEEP", encoding="utf-8")
    opened = Mock(return_value=True)
    monkeypatch.setattr(webbrowser, "open", opened)
    args = [
        "--html",
        "--insights",
        "deterministic",
        "--output",
        str(destination),
        "--open",
    ]
    assert demo.main(args) == 1
    assert destination.read_text() == "KEEP"
    opened.assert_not_called()
    assert demo.main([*args, "--overwrite"]) == 0
    assert destination.read_text(encoding="utf-8").count('class="insight-card"') == 2
    opened.assert_called_once()


@pytest.mark.parametrize("flag", ["--open", "--overwrite"])
def test_html_options_still_require_html(flag):
    with pytest.raises(SystemExit) as error:
        demo.main(["--insights", "deterministic", flag])
    assert error.value.code == 2


def test_three_cards_via_api_with_rich_synthetic_report(monkeypatch):
    from footballiq.analytics import analyze_recent_matches

    data = json.loads(
        (Path(__file__).parent / "fixtures/integration/complete_five.json").read_text(
            encoding="utf-8"
        )
    )
    data["matches"] = data["matches"][:4]
    data["selection"]["returned_count"] = 4
    data["matches"][0]["kickoff_at"] = "2026-11-08T16:00:00Z"
    report = analyze_recent_matches(data)
    monkeypatch.setattr(demo, "load_demo_report", Mock(return_value=report))
    assert (
        demo.render_demo_dashboard(insights="deterministic").count(
            'class="insight-card"'
        )
        == 3
    )
