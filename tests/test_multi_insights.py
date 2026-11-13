"""Seleções fechadas e adversariais, com motor factual real e rede bloqueada."""

import json
import socket
from pathlib import Path
from unittest.mock import Mock

import pytest

from footballiq import ollama_client
from footballiq.analyst_demo import load_demo_report, main, run_demo
from footballiq.analytics import FactualReport, analyze_recent_matches
from footballiq.grounded_narrative import multi_insights as multi
from footballiq.grounded_narrative.insights import build_insights, render_insight
from footballiq.grounded_narrative.orchestrator import narrate_report
from footballiq.ollama_client import OllamaClient, OllamaSettings, OllamaUnavailable
from footballiq.trends import calculate_trends


@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nenhum teste pode estabelecer ligações, mesmo em modo opt-in."""
    monkeypatch.setattr(
        socket.socket, "connect", Mock(side_effect=AssertionError("network"))
    )
    monkeypatch.setattr(
        socket, "create_connection", Mock(side_effect=AssertionError("network"))
    )


def payload() -> dict:
    """Lê exclusivamente a fixture sintética versionada."""
    return json.loads(
        (Path(__file__).parent / "fixtures/integration/complete_five.json").read_text(
            encoding="utf-8"
        )
    )


@pytest.fixture
def rich_report() -> FactualReport:
    """Quatro jogos com eventos e datas distintas permitem três famílias."""
    data = payload()
    data["matches"] = data["matches"][:4]
    data["selection"]["returned_count"] = 4
    data["matches"][0]["kickoff_at"] = "2026-11-08T16:00:00Z"
    return analyze_recent_matches(data)


def client_for(*ids: str) -> Mock:
    """Fabrica apenas uma seleção de IDs, nunca texto narrativo."""
    return Mock(chat=Mock(return_value=json.dumps({"plan_ids": list(ids)})))


def assert_unavailable(result: multi.InsightNarrativeResult) -> None:
    """Uma falha nunca expõe o fragmento válido de uma seleção múltipla."""
    assert result.status == "unavailable"
    assert not result.text and not result.plan_ids and not result.references
    assert not result.snapshot_id and not result.evidence_digest


@pytest.mark.parametrize(
    "ids",
    [
        ("insight:form",),
        ("insight:form", "insight:recent_vs_older", "insight:temporal_goals"),
    ],
)
def test_valid_one_or_three_insights(
    rich_report: FactualReport, ids: tuple[str, ...]
) -> None:
    result = multi.narrate_insights(rich_report, enabled=True, client=client_for(*ids))
    bundle = build_insights(rich_report)
    candidates = multi.prepare_insight_candidates(bundle)
    assert result.status == "available" and result.reason == "validated"
    assert result.plan_ids == ids
    assert result.text == "\n".join(
        render_insight(candidates[identity], bundle) for identity in ids
    )
    assert result.snapshot_id == bundle.snapshot_id
    assert result.evidence_digest == bundle.evidence_digest
    assert set(result.references) == {
        ref for identity in ids for ref in bundle.authorized_evidence_ids(identity)
    }


@pytest.mark.parametrize(
    "content",
    [
        "{",
        "{}",
        "[]",
        "null",
        '{"plan_id":"insight:form"}',
        '{"plan_ids":[]}',
        '{"plan_ids":null}',
        '{"plan_ids":"insight:form"}',
        '{"plan_ids":[1]}',
        '{"plan_ids":[true]}',
        '{"plan_ids":[{}]}',
        '{"plan_ids":["insight:missing"]}',
        '{"plan_ids":["insight:form","insight:form"]}',
        '{"plan_ids":["insight:form","insight:recent_vs_older","insight:temporal_goals","insight:winning_run"]}',
        '{"plan_ids":["insight:form"],"text":"invented tactical cause"}',
        '{"plan_ids":["insight:form"],"references":[]}',
        '{"plan_ids":["insight:form"],"coverage":1}',
        '{"plan_ids":["insight:form"],"plan_ids":["insight:competitive"]}',
        '{"plan_ids":[NaN]}',
        "x" * 8193,
        None,
    ],
)
def test_invalid_selection_is_atomic(
    rich_report: FactualReport, content: str | None
) -> None:
    result = multi.narrate_insights(
        rich_report, enabled=True, client=Mock(chat=Mock(return_value=content))
    )
    assert_unavailable(result)
    assert "invented tactical cause" not in repr(result)


@pytest.mark.parametrize(
    "ids",
    [
        ("insight:form", "insight:competitive"),
        ("insight:recent_vs_older", "insight:home_vs_away"),
        ("insight:winning_run", "insight:winless_run"),
    ],
)
def test_repeated_families_are_not_presented(
    rich_report: FactualReport, ids: tuple[str, ...]
) -> None:
    if ids[0] == "insight:winning_run":
        # Os dois IDs não coexistem num catálogo factual: também têm de ser recusados.
        expected = "invalid_selection"
    else:
        expected = "insufficient_diversity"
    result = multi.narrate_insights(rich_report, enabled=True, client=client_for(*ids))
    assert_unavailable(result)
    assert result.reason == expected


def test_small_catalog_respects_real_family_availability() -> None:
    report = load_demo_report()
    client = client_for("insight:form", "insight:recent_vs_older")
    assert (
        multi.narrate_insights(report, enabled=True, client=client).status
        == "available"
    )
    schema = client.chat.call_args.args[2]
    assert schema["properties"]["plan_ids"]["maxItems"] == 2
    result = multi.narrate_insights(report, enabled=True, deterministic=True)
    assert len(result.plan_ids) == 2


def test_partial_coverage_is_subtotal_not_zero() -> None:
    data = payload()
    data["matches"][2]["score"]["status"] = "unverified"
    report = analyze_recent_matches(data)
    result = multi.narrate_insights(
        report, enabled=True, client=client_for("insight:form")
    )
    assert result.status == "available"
    assert "Cobertura 4/5" in result.text and "Apenas subtotal" in result.text
    assert "insight:recent_vs_older" not in multi.prepare_insight_candidates(
        build_insights(report)
    )


def test_insufficient_coverage_never_calls_client() -> None:
    data = payload()
    for index in (1, 2, 4):
        data["matches"][index]["score"]["status"] = "unverified"
    report = analyze_recent_matches(data)
    client = client_for("insight:form")
    result = multi.narrate_insights(report, enabled=True, client=client)
    assert_unavailable(result)
    assert result.reason == "no_eligible_insights"
    client.chat.assert_not_called()


@pytest.mark.parametrize("scenario", ["empty", "partial_match"])
def test_no_data_never_calls_client(scenario: str) -> None:
    client = client_for("insight:form")
    result = multi.narrate_insights(
        load_demo_report(scenario), enabled=True, client=client
    )
    assert_unavailable(result)
    client.chat.assert_not_called()


@pytest.mark.parametrize(
    "tampering",
    [
        "snapshot",
        "digest",
        "invented",
        "swapped",
        "duplicate",
        "identity",
        "foreign_bundle",
    ],
)
def test_one_bad_plan_rejects_entire_selection(
    rich_report: FactualReport, monkeypatch: pytest.MonkeyPatch, tampering: str
) -> None:
    prepare = multi.prepare_insight_candidates
    other_report = rich_report.model_copy(deep=True)
    other_report.snapshot_version = "another-synthetic-snapshot"
    foreign = prepare(build_insights(other_report))

    def corrupted(bundle):
        plans = prepare(bundle)
        identity = "insight:recent_vs_older"
        plan = plans[identity].model_copy(deep=True)
        if tampering == "snapshot":
            plan.evidence_snapshot_id = "wrong-snapshot"
        elif tampering == "digest":
            plan.evidence_digest = "wrong-digest"
        elif tampering == "invented":
            plan.assertions[0].references[0].evidence_id = "invented"
        elif tampering == "swapped":
            plan.assertions[0].references[0].evidence_id = (
                plans["insight:form"].assertions[0].references[0].evidence_id
            )
        elif tampering == "duplicate":
            plan.assertions[0].references.append(
                plan.assertions[0].references[0].model_copy()
            )
        elif tampering == "identity":
            plan = plans["insight:form"]
        else:
            plan = foreign[identity]
        plans[identity] = plan
        return plans

    monkeypatch.setattr(multi, "prepare_insight_candidates", corrupted)
    result = multi.narrate_insights(
        rich_report,
        enabled=True,
        client=client_for("insight:form", "insight:recent_vs_older"),
    )
    assert_unavailable(result)
    assert result.reason == "invalid_plan"


def test_tied_dates_do_not_create_sequence_or_comparison(
    rich_report: FactualReport,
) -> None:
    for match in rich_report.matches:
        match.kickoff_at = rich_report.matches[0].kickoff_at
    candidates = multi.prepare_insight_candidates(build_insights(rich_report))
    assert "insight:winning_run" not in candidates
    assert "insight:recent_vs_older" not in candidates


@pytest.mark.parametrize(
    "error,reason",
    [
        (TimeoutError("private"), "timeout"),
        (OllamaUnavailable("timeout"), "timeout"),
        (OllamaUnavailable("connection_unavailable"), "connection_unavailable"),
        (OllamaUnavailable("private"), "transport_error"),
        (OSError("private"), "transport_error"),
    ],
)
def test_transport_failure_has_no_untrusted_text(
    rich_report: FactualReport, error: Exception, reason: str
) -> None:
    result = multi.narrate_insights(
        rich_report, enabled=True, client=Mock(chat=Mock(side_effect=error))
    )
    assert_unavailable(result)
    assert result.reason == reason and "private" not in repr(result)


def test_disabled_and_deterministic_modes_never_use_network(
    rich_report: FactualReport, monkeypatch: pytest.MonkeyPatch
) -> None:
    constructor = Mock(side_effect=AssertionError("client constructed"))
    monkeypatch.setattr(ollama_client, "OllamaClient", constructor)
    client = client_for("insight:form")
    assert multi.narrate_insights(rich_report, client=client).status == "disabled"
    assert main([]) == 0
    first = multi.narrate_insights(
        rich_report, enabled=True, client=client, deterministic=True
    )
    assert first == multi.narrate_insights(
        rich_report, enabled=True, deterministic=True
    )
    assert len(first.plan_ids) == 3
    client.chat.assert_not_called()
    constructor.assert_not_called()


def test_single_canonical_bundle_and_factual_immutability(
    rich_report: FactualReport, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = rich_report.model_dump_json()
    trends = calculate_trends(rich_report).to_dict()
    built = []

    def build(report):
        bundle = build_insights(report)
        built.append(bundle)
        return bundle

    renderer = Mock(wraps=multi.render_insight)
    monkeypatch.setattr(multi, "build_insights", build)
    monkeypatch.setattr(multi, "render_insight", renderer)
    result = multi.narrate_insights(rich_report, enabled=True, deterministic=True)
    assert result.status == "available" and len(built) == 1
    assert all(call.args[1] is built[0] for call in renderer.call_args_list)
    assert built[0] == build_insights(rich_report)
    with pytest.raises(TypeError):
        built[0]["insight:form"]["value"]["wins"] = 99
    assert rich_report.model_dump_json() == before
    assert calculate_trends(rich_report).to_dict() == trends


def test_actual_ollama_client_with_fake_transport(rich_report: FactualReport) -> None:
    def transport(settings, request):
        context = json.loads(json.loads(request)["messages"][1]["content"])
        assert all("family" in candidate for candidate in context["catalog"])
        assert "evidence:" not in json.dumps(context)
        assert "Equipa" not in json.dumps(context)
        return json.dumps(
            {
                "model": settings.model,
                "done": True,
                "message": {
                    "role": "assistant",
                    "content": '{"plan_ids":["insight:form"]}',
                },
            }
        ).encode()

    client = OllamaClient(OllamaSettings("synthetic-test"), transport)
    assert client.settings.timeout == 5 and client.settings.deadline == 15
    assert (
        multi.narrate_insights(rich_report, enabled=True, client=client).status
        == "available"
    )


def test_model_order_is_preserved(rich_report: FactualReport) -> None:
    identities = ("insight:temporal_goals", "insight:form", "insight:recent_vs_older")
    assert (
        multi.narrate_insights(
            rich_report, enabled=True, client=client_for(*identities)
        ).plan_ids
        == identities
    )


def test_legacy_api_and_cli_remain_compatible(capsys: pytest.CaptureFixture) -> None:
    report = load_demo_report()
    old_client = Mock(chat=Mock(return_value='{"plan_id":"plan:1"}'))
    assert narrate_report(report, enabled=True, client=old_client).status == "available"
    assert run_demo(with_narrative=True, client=old_client).startswith(run_demo())
    assert main(["--insights", "deterministic"]) == 0
    assert "insights_status=available; reason=deterministic" in capsys.readouterr().out
    assert run_demo(insights="ollama", client=client_for("insight:form")).startswith(
        run_demo()
    )


@pytest.mark.parametrize("extra", ["--html", "--with-narrative", "--with-llm"])
def test_insight_cli_does_not_change_html(extra: str) -> None:
    with pytest.raises(SystemExit) as error:
        main(["--insights", "deterministic", extra])
    assert error.value.code == 2


def test_actual_comparison_family_repetition_is_rejected() -> None:
    """Os dois tipos de comparação coexistem na fixture de cinco jogos."""
    result = multi.narrate_insights(
        load_demo_report(),
        enabled=True,
        client=client_for("insight:recent_vs_older", "insight:home_vs_away"),
    )
    assert_unavailable(result)
    assert result.reason == "insufficient_diversity"


def test_bundle_with_foreign_fact_snapshot_is_rejected(
    rich_report: FactualReport, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A inconsistência é recusada mesmo se não vier da resposta do modelo."""
    from footballiq.grounded_narrative.contract import EvidenceBundle

    bundle = build_insights(rich_report)
    facts = {identity: dict(fact) for identity, fact in bundle.items()}
    facts["insight:form"]["snapshot_version"] = "foreign-snapshot"
    corrupted = EvidenceBundle(bundle.snapshot_id, bundle.evidence_digest, facts)
    monkeypatch.setattr(multi, "build_insights", Mock(return_value=corrupted))
    client = client_for("insight:form")
    result = multi.narrate_insights(rich_report, enabled=True, client=client)
    assert_unavailable(result)
    client.chat.assert_not_called()


def test_disabled_mode_does_not_even_build_bundle(
    rich_report: FactualReport, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O opt-in antecede qualquer preparação ou cliente."""
    build = Mock(side_effect=AssertionError("bundle constructed"))
    monkeypatch.setattr(multi, "build_insights", build)
    assert multi.narrate_insights(rich_report, deterministic=True).status == "disabled"
    build.assert_not_called()


def test_missing_client_and_non_demo_report_are_safe(
    rich_report: FactualReport,
) -> None:
    """Não há cliente implícito nem habilitação de dados operacionais."""
    result = multi.narrate_insights(rich_report, enabled=True)
    assert_unavailable(result)
    assert result.reason == "client_required"
    rich_report.source_instance_id = "another-instance"
    result = multi.narrate_insights(rich_report, enabled=True, deterministic=True)
    assert_unavailable(result)
    assert result.reason == "demo_only"


def test_sequence_coverage_is_not_confused_with_missingness(
    rich_report: FactualReport,
) -> None:
    """Dois jogos consecutivos podem cobrir só metade da janela de quatro."""
    plans = multi.prepare_insight_candidates(build_insights(rich_report))
    assert plans["insight:winning_run"].coverage == 0.5
    assert (
        multi.narrate_insights(
            rich_report, enabled=True, client=client_for("insight:winning_run")
        ).status
        == "available"
    )


def test_one_game_is_insufficient_for_new_selection() -> None:
    """A observação individual continua disponível apenas pela API antiga."""
    data = payload()
    data["matches"] = data["matches"][:1]
    data["selection"]["returned_count"] = 1
    report = analyze_recent_matches(data)
    result = multi.narrate_insights(report, enabled=True, deterministic=True)
    assert_unavailable(result)
    assert result.reason == "no_eligible_insights"
    assert (
        narrate_report(
            report,
            enabled=True,
            client=Mock(chat=Mock(return_value='{"plan_id":"plan:1"}')),
        ).status
        == "available"
    )


def test_cli_invalid_settings_keeps_factual(capsys: pytest.CaptureFixture) -> None:
    """O endpoint externo é recusado antes de abrir qualquer ligação."""
    assert (
        main(
            [
                "--insights",
                "ollama",
                "--model",
                "synthetic-test",
                "--ollama-url",
                "https://example.com",
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert output.startswith(run_demo())
    assert "insights_status=unavailable; reason=invalid_settings" in output


def test_deterministic_ranking_and_render_are_repeatable(
    rich_report: FactualReport,
) -> None:
    """O desempate documentado prioriza dimensão, cobertura e ordem fixa."""
    first = multi.narrate_insights(rich_report, enabled=True, deterministic=True)
    assert first.plan_ids == (
        "insight:form",
        "insight:recent_vs_older",
        "insight:temporal_goals",
    )
    rich_report.matches.reverse()
    assert (
        multi.narrate_insights(rich_report, enabled=True, deterministic=True) == first
    )
