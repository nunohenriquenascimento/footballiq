"""Shortlist determinística com motor real, mantendo a rejeição integral."""

import json
import socket
from pathlib import Path
from unittest.mock import Mock

import pytest

from footballiq.analytics import FactualReport, analyze_recent_matches
from footballiq.grounded_narrative import multi_insights as multi
from footballiq.grounded_narrative.insights import build_insights, render_insight
from footballiq.trends import calculate_trends


@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Uma regressão offline nunca pode consultar Ollama."""
    monkeypatch.setattr(
        socket.socket, "connect", Mock(side_effect=AssertionError("network"))
    )
    monkeypatch.setattr(
        socket, "create_connection", Mock(side_effect=AssertionError("network"))
    )


def report_with_families(count: int) -> FactualReport:
    """Produz variantes sintéticas sem modificar fixtures em disco."""
    data = json.loads(
        (Path(__file__).parent / "fixtures/integration/complete_five.json").read_text(
            encoding="utf-8"
        )
    )
    if count == 1:
        data["matches"][2]["score"]["status"] = "unverified"
    elif count in {3, 4}:
        data["matches"] = data["matches"][:4]
        data["selection"]["returned_count"] = 4
        if count == 4:
            data["matches"][0]["kickoff_at"] = "2026-11-08T16:00:00Z"
    return analyze_recent_matches(data)


def client_for(ids: list[str]) -> Mock:
    """Simula apenas a lista estruturada de IDs."""
    return Mock(chat=Mock(return_value=json.dumps({"plan_ids": ids})))


@pytest.mark.parametrize("count", [1, 2, 3, 4])
def test_one_representative_for_every_available_family(count: int) -> None:
    report = report_with_families(count)
    bundle = build_insights(report)
    candidates = multi.prepare_insight_candidates(bundle)
    shortlist = multi.prepare_insight_shortlist(bundle)
    families = [multi._TOPICS[identity][0] for identity in shortlist]
    assert len(shortlist) == len(set(families)) == count
    assert all(plan == candidates[identity] for identity, plan in shortlist.items())
    expected = {}
    for identity in candidates:
        expected.setdefault(multi._TOPICS[identity][0], identity)
    assert list(shortlist) == list(expected.values())
    ids = list(shortlist)[:3]
    client = client_for(ids)
    result = multi.narrate_insights(report, enabled=True, client=client)
    assert result.status == "available" and result.plan_ids == tuple(ids)
    context = json.loads(client.chat.call_args.args[1])
    schema = client.chat.call_args.args[2]["properties"]["plan_ids"]
    assert [entry["plan_id"] for entry in context["catalog"]] == list(shortlist)
    assert schema["items"]["enum"] == list(shortlist)
    assert schema["minItems"] == 1 and schema["maxItems"] == min(3, count)


def test_complete_catalog_and_same_family_alternatives_are_preserved() -> None:
    report = report_with_families(4)
    before = build_insights(report)
    candidates = multi.prepare_insight_candidates(before)
    assert {"insight:form", "insight:competitive"} <= candidates.keys()
    assert {"insight:recent_vs_older", "insight:home_vs_away"} <= candidates.keys()
    shortlist = multi.prepare_insight_shortlist(before)
    assert list(shortlist) == [
        "insight:form",
        "insight:recent_vs_older",
        "insight:temporal_goals",
        "insight:winning_run",
    ]
    assert "insight:competitive" in before and "insight:competitive" not in shortlist
    assert build_insights(report) == before
    assert (
        shortlist["insight:form"].evidence_digest
        == candidates["insight:form"].evidence_digest
    )
    assert shortlist["insight:form"].assertions == candidates["insight:form"].assertions


@pytest.mark.parametrize("size", [1, 2, 3])
def test_model_can_choose_fewer_than_available_families(size: int) -> None:
    report = report_with_families(4)
    shortlist = multi.prepare_insight_shortlist(build_insights(report))
    ids = list(reversed(shortlist))[:size]
    result = multi.narrate_insights(report, enabled=True, client=client_for(ids))
    assert result.status == "available" and result.plan_ids == tuple(ids)


@pytest.mark.parametrize("unoffered", ["insight:competitive", "insight:home_vs_away"])
def test_real_catalog_id_outside_presented_shortlist_rejects_everything(
    unoffered: str,
) -> None:
    report = report_with_families(4)
    assert unoffered in multi.prepare_insight_candidates(build_insights(report))
    assert unoffered not in multi.prepare_insight_shortlist(build_insights(report))
    result = multi.narrate_insights(
        report, enabled=True, client=client_for(["insight:form", unoffered])
    )
    assert result.status == "unavailable" and result.reason == "invalid_selection"
    assert not result.text and not result.references and not result.plan_ids


@pytest.mark.parametrize("deterministic", [False, True])
def test_backend_still_rejects_repeated_families_in_manipulated_shortlist(
    monkeypatch: pytest.MonkeyPatch, deterministic: bool
) -> None:
    report = report_with_families(4)
    candidates = multi.prepare_insight_candidates(build_insights(report))
    corrupted = {
        identity: candidates[identity]
        for identity in ["insight:form", "insight:competitive"]
    }
    monkeypatch.setattr(
        multi, "prepare_insight_shortlist", Mock(return_value=corrupted)
    )
    result = multi.narrate_insights(
        report,
        enabled=True,
        deterministic=deterministic,
        client=client_for(list(corrupted)),
    )
    assert result.status == "unavailable" and result.reason == "insufficient_diversity"
    assert not result.text and not result.references and not result.plan_ids


def test_representative_prefers_coverage_then_sample_then_fixed_priority() -> None:
    partial = multi.prepare_insight_shortlist(build_insights(report_with_families(1)))
    assert list(partial) == ["insight:away"]
    assert (
        partial["insight:away"].coverage == 1
        and partial["insight:away"].sample_size == 2
    )
    complete = multi.prepare_insight_shortlist(build_insights(report_with_families(2)))
    assert complete["insight:form"].sample_size == 5
    assert (
        "insight:competitive" not in complete
    )  # Cobertura/amostra empatadas: prioridade fixa.
    assert (
        "insight:recent_vs_older" in complete and "insight:home_vs_away" not in complete
    )


@pytest.mark.parametrize("count", [1, 2, 3, 4])
def test_deterministic_result_preserves_previous_valid_policy_and_integrity(
    count: int,
) -> None:
    report = report_with_families(count)
    before = report.model_dump_json()
    trends = calculate_trends(report).to_dict()
    bundle = build_insights(report)
    # Reproduz a regra anterior para confirmar compatibilidade do modo sem LLM.
    old_ids = []
    seen = set()
    candidates = multi.prepare_insight_candidates(bundle)
    for identity in candidates:
        family = multi._TOPICS[identity][0]
        if family not in seen:
            old_ids.append(identity)
            seen.add(family)
        if len(old_ids) == 3:
            break
    expected = "\n".join(
        render_insight(candidates[identity], bundle) for identity in old_ids
    )
    result = multi.narrate_insights(report, enabled=True, deterministic=True)
    assert result.status == "available" and result.plan_ids == tuple(old_ids)
    assert result.text == expected
    assert (
        result.evidence_digest == bundle.evidence_digest
        and result.snapshot_id == bundle.snapshot_id
    )
    report.matches.reverse()
    assert multi.prepare_insight_shortlist(
        build_insights(report)
    ) == multi.prepare_insight_shortlist(bundle)
    report.matches.reverse()
    assert (
        report.model_dump_json() == before
        and calculate_trends(report).to_dict() == trends
    )
    assert build_insights(report) == bundle
    with pytest.raises(TypeError):
        bundle["insight:form"]["value"]["wins"] = 99


def test_tied_dates_do_not_invent_sequence_family() -> None:
    shortlist = multi.prepare_insight_shortlist(build_insights(report_with_families(3)))
    assert len(shortlist) == 3
    assert all(multi._TOPICS[identity][0] != "sequence" for identity in shortlist)


def test_partial_timing_representative_keeps_subtotal_and_actual_denominator() -> None:
    """A shortlist não promove cobertura parcial a um total completo."""
    data = json.loads(
        (Path(__file__).parent / "fixtures/integration/complete_five.json").read_text(
            encoding="utf-8"
        )
    )
    data["matches"][-1]["quality"]["score_events"]["status"] = "partial"
    data["matches"][-1]["score"]["status"] = "unverified"
    report = analyze_recent_matches(data)
    result = multi.narrate_insights(
        report, enabled=True, client=client_for(["insight:temporal_goals"])
    )
    assert result.status == "available"
    assert "Cobertura 4/5" in result.text and "Apenas subtotal" in result.text
