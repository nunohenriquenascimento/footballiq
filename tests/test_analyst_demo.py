"""Verifica a apresentação factual da demonstração, sem serviços externos."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

from footballiq import analyst_demo as demo
from footballiq.analytics import analyze_recent_matches

FIXTURES = Path(__file__).parent / "fixtures/integration"


@pytest.fixture(autouse=True)
def no_network() -> Iterator[None]:
    """Uma tentativa de rede faz falhar qualquer teste desta demonstração."""
    with (
        patch.object(socket.socket, "connect", side_effect=AssertionError("Sem rede")),
        patch.object(
            socket, "create_connection", side_effect=AssertionError("Sem rede")
        ),
    ):
        yield


def test_five_games_have_expected_results_and_metrics() -> None:
    """Os totais apresentados correspondem ao exemplo calculado manualmente."""
    output = demo.run_demo()
    assert "Dados fictícios — demonstração" in output
    assert "Jogos analisados: 5/5." in output
    for expected in (
        "Vitórias: 2",
        "Empates: 2",
        "Derrotas: 1",
        "Golos marcados: 4",
        "Golos sofridos: 4",
        "Média de golos marcados: 0.8",
        "Remates — cobertura 5/5",
        "Remates totais — a favor: 1",
        "Remates totais — contra: 0",
    ):
        assert expected in output
    report = demo.load_demo_report()
    assert report.points_policy is None
    assert report.metrics["points"].values is None
    assert "Política de pontos não fornecida." in output


def test_partial_fixture_preserves_unknown_instead_of_zero() -> None:
    """Um jogo incompleto não permite inventar resultado, vitória ou zero remates."""
    output = demo.run_demo("partial_match")
    assert "Jogos analisados: 1/5." in output
    assert "Resultados e golos — cobertura 0/1" in output
    assert "Resultado unverified." in output
    assert "shots: unknown." in output
    assert " | indisponível; estado declarado: unverified." in output
    assert "Apenas 1 de 5 jogos encontrados." in output
    assert "Golos marcados: 0" not in output
    assert "Remates totais — a favor: 0" not in output
    assert "0–0" not in output


def test_empty_fixture_has_no_fabricated_totals() -> None:
    """Zero jogos não equivale a zero golos nem a médias nulas."""
    output = demo.run_demo("empty")
    assert "Jogos analisados: 0/5." in output
    assert "Nenhum jogo disponível" in output
    assert "cobertura 0/0" in output
    assert "Vitórias: 0" not in output
    assert "Golos marcados: 0" not in output
    assert "Apenas 0 de 5 jogos encontrados." in output


def test_partial_window_labels_subtotal_separately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A apresentação conserva o subtotal do motor sem o chamar total dos cinco."""
    payload = json.loads((FIXTURES / "complete_five.json").read_text(encoding="utf-8"))
    payload["matches"][0]["score"]["status"] = "unverified"
    report = analyze_recent_matches(payload)
    monkeypatch.setattr(demo, "load_demo_report", lambda scenario: report)
    output = demo.run_demo()
    assert (
        "Resultados e golos — cobertura 4/5\n  Total da janela: indisponível." in output
    )
    assert "Subtotal apenas dos jogos cobertos (não é total da janela):" in output
    assert "Golos marcados: 2" in output
    assert "Jogo 10: Resultado unverified." in output


def test_order_dates_versions_and_match_results_are_preserved() -> None:
    """Datas iguais mantêm o desempate numérico; cada jogo conserva a sua versão."""
    output = demo.run_demo()
    rows = [
        line
        for line in output.splitlines()
        if line.startswith("- Jogo") and " | " in line
    ]
    assert [line.split(" | ")[0] for line in rows] == [
        "- Jogo 10",
        "- Jogo 9",
        "- Jogo 8",
        "- Jogo 7",
        "- Jogo 6",
    ]
    assert [line.split(" | ")[-1].split(" (")[0] for line in rows] == [
        "2–1",
        "1–0",
        "1–1",
        "0–2",
        "0–0",
    ]
    assert "2026-11-08T15:00:00Z" in rows[0]
    assert "2026-11-08T15:00:00Z" in rows[1]
    assert "Snapshot: synthetic-five-v1" in output
    assert "Origem: match_tracker/fictional-local-demo" in output
    assert "Fórmulas: footballiq.analytics.v1" in output
    for mid in (10, 9, 8, 7, 6):
        assert f"Jogo {mid}: versão synthetic-match-{mid}-v1" in output
        assert f"fonte internal_match:{mid}" in output
    assert "eventos [1000" in output


@pytest.mark.parametrize("scenario", ["complete_five", "partial_match", "empty"])
def test_same_fixture_produces_same_output_and_keeps_input(scenario: str) -> None:
    """Sem relógio global ou escrita, repetir um cenário mantém bytes e resposta."""
    path = FIXTURES / f"{scenario}.json"
    before = path.read_bytes()
    assert demo.run_demo(scenario) == demo.run_demo(scenario)
    assert path.read_bytes() == before
    assert demo.load_demo_report(scenario).authorization_verified is False


@pytest.mark.parametrize("scenario", ["../.env", "/tmp/real.json", "unknown"])
def test_custom_paths_are_not_accepted(scenario: str) -> None:
    """O ponto de entrada não aceita ficheiros operacionais nem caminhos livres."""
    with pytest.raises(ValueError, match="Escolha"):
        demo.run_demo(scenario)


def test_altered_fixture_is_rejected_without_displaying_content(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Uma fixture substituída não pode ser apresentada como demonstração aprovada."""
    (tmp_path / "complete_five.json").write_text(
        "DO_NOT_DISPLAY_PRIVATE", encoding="utf-8"
    )
    monkeypatch.setattr(demo, "_FIXTURE_DIRECTORY", tmp_path)
    assert demo.main([]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "DO_NOT_DISPLAY_PRIVATE" not in captured.err
    assert "fixture aprovada" in captured.err


def test_line_endings_do_not_invalidate_approved_fixture(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """O mesmo JSON aprovado mantém-se utilizável nos checkouts Windows e Linux."""
    text = (FIXTURES / "empty.json").read_text(encoding="utf-8")
    (tmp_path / "empty.json").write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    monkeypatch.setattr(demo, "_FIXTURE_DIRECTORY", tmp_path)
    assert "Jogos analisados: 0/5." in demo.run_demo("empty")


def test_missing_checkout_has_clear_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Uma instalação sem as fixtures falha claramente, sem procurar outra origem."""
    monkeypatch.setattr(demo, "_FIXTURE_DIRECTORY", tmp_path)
    assert demo.main([]) == 1
    assert "checkout completo" in capsys.readouterr().err


def test_cli_runs_without_database_or_llm_imports() -> None:
    """Exercita a entrada executável num processo novo, bloqueando infraestrutura."""
    script = """
import importlib.abc, runpy, socket, sys
from unittest.mock import patch

class NoInfrastructure(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {"psycopg", "sqlalchemy", "httpx", "ollama"} or fullname.startswith("footballiq.db"):
            raise AssertionError("Demo must not import database or LLM infrastructure")

def forbidden(*args, **kwargs):
    raise AssertionError("Demo must not connect")

sys.meta_path.insert(0, NoInfrastructure())
sys.argv = ["footballiq.analyst_demo", "--fixture", "complete_five"]
with patch.object(socket.socket, "connect", forbidden), patch.object(socket, "create_connection", forbidden):
    runpy.run_module("footballiq.analyst_demo", run_name="__main__")
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", script],
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Dados fictícios — demonstração" in result.stdout
    assert "Vitórias: 2" in result.stdout


def test_quality_warnings_are_visible() -> None:
    """A demonstração não apresenta o scope declarado como autorização real."""
    output = demo.run_demo()
    assert "Autorização e autenticidade não verificadas" in output
    assert "Modo offline: o scope declarado não prova autorização" in output
    assert "não foi confirmada a atualidade na origem" in output
    assert "Não se apresentam pontos oficiais sem regulamento validado." in output
