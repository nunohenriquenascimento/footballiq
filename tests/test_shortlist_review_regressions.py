"""Regressões mínimas da revisão offline da shortlist existente."""

import socket
from unittest.mock import Mock

import pytest

from footballiq.analyst_demo import load_demo_report
from footballiq.grounded_narrative.multi_insights import narrate_insights


@pytest.mark.parametrize(
    "content",
    ["", '{"plan_ids":["insight:form","insight:missing"]}'],
)
def test_empty_or_partially_unknown_response_is_atomic_without_retry(
    monkeypatch: pytest.MonkeyPatch, content: str
) -> None:
    """Rejeita a resposta inteira sem usar rede nem repetir a seleção."""
    connect = Mock(side_effect=AssertionError("network forbidden"))
    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket, "create_connection", connect)
    client = Mock(chat=Mock(return_value=content))
    result = narrate_insights(load_demo_report(), enabled=True, client=client)
    assert result.status == "unavailable" and result.reason == "invalid_selection"
    assert not result.text and not result.plan_ids and not result.references
    assert not result.snapshot_id and not result.evidence_digest
    client.chat.assert_called_once()
    connect.assert_not_called()
