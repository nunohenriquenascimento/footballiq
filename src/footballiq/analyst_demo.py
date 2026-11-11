"""Demonstração local do AI Analyst, só com fixtures fictícias e sem LLM."""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from footballiq.analytics import FactualReport, analyze_recent_matches

if TYPE_CHECKING:
    from footballiq.analyst_interpretation import ChatClient, InterpretationResult
    from footballiq.grounded_narrative.orchestrator import NarrativeResult

_FIXTURE_DIRECTORY = Path(__file__).resolve().parents[2] / "tests/fixtures/integration"
_LOAD_ERRORS = (OSError, ValueError)
# Estes hashes aprovam apenas os exemplos versionados, não pacotes de produção.
# A leitura em texto normaliza CRLF/LF para funcionar em Windows e no CI Linux.
_FIXTURE_HASHES = {
    "complete_five": "b95d57be8949e60d5bb6a8fa9c1d47cdb458bfab3e04c7050207222740e86f31",
    "partial_match": "57255d255cc1a48172b359a3d08e96032c0ea05e7a2caf59867ece47ae334a1e",
    "empty": "9d706da66f17b661c99253572566595b1bc2c1b09f0dc19cac6bab5296d542e6",
}
_CATEGORIES = {
    "competitive": "Resultados e golos",
    "points": "Pontos",
    "shots": "Remates",
    "cards": "Cartões",
    "substitutions": "Substituições",
    "temporal_goals": "Distribuição temporal dos golos",
}
_FIELDS = {
    "wins": "Vitórias",
    "draws": "Empates",
    "losses": "Derrotas",
    "goals_for": "Golos marcados",
    "goals_against": "Golos sofridos",
    "goal_difference": "Diferença de golos",
    "average_goals_for": "Média de golos marcados",
    "average_goals_against": "Média de golos sofridos",
    "points": "Pontos",
    "on_target": "Remates enquadrados",
    "off_target": "Remates desenquadrados",
    "blocked": "Remates bloqueados",
    "total": "Remates totais",
    "yellow": "Cartões amarelos",
    "red": "Cartões vermelhos",
    "substitutions": "Substituições",
}
_OUTCOMES = {
    "win": "vitória",
    "draw": "empate",
    "loss": "derrota",
    None: "indisponível",
}


def load_demo_report(scenario: str = "complete_five") -> FactualReport:
    """Analisa um exemplo aprovado do checkout, sem aceitar paths ou dados reais.

    O hash deteta alterações acidentais às fixtures antes de as apresentar como
    fictícias. Não autentica dados operacionais nem substitui autorização real.
    Todas as fórmulas pertencem ao Analytics Engine, chamado sem política de pontos.
    """
    if scenario not in _FIXTURE_HASHES:
        raise ValueError("Escolha complete_five, partial_match ou empty.")
    payload = (_FIXTURE_DIRECTORY / f"{scenario}.json").read_text(encoding="utf-8")
    if hashlib.sha256(payload.encode("utf-8")).hexdigest() != _FIXTURE_HASHES[scenario]:
        raise ValueError(
            "Fixture alterada: a demonstração só aceita exemplos aprovados."
        )
    return analyze_recent_matches(payload)


def _field_label(key: str) -> str:
    if key in _FIELDS:
        return _FIELDS[key]
    prefix, side = key.rsplit("_", 1)
    perspective = "a favor" if side == "for" else "contra"
    if prefix.startswith("period_"):
        return f"Golos no {prefix.removeprefix('period_')}.º período — {perspective}"
    if prefix.startswith("minute_"):
        return f"Golos nos minutos {prefix.removeprefix('minute_')} — {perspective}"
    return f"{_FIELDS[prefix]} — {perspective}"


def _render_report(report: FactualReport) -> str:
    lines = [
        "Dados fictícios — demonstração",
        "FootballIQ AI Analyst — resposta factual, sem LLM",
        'Pergunta: "Analisa os últimos cinco jogos da minha equipa."',
        "",
        f"Jogos analisados: {report.selection.returned_count}/5.",
        f"Equipa: {report.selection.team_id}; época: {report.selection.season_id}.",
        "Autorização e autenticidade não verificadas; qualidade declarada na fixture.",
        "",
        "JOGOS — do mais recente para o mais antigo; datas em UTC",
        "Resultados na perspetiva da equipa analisada (marcados–sofridos).",
    ]
    if not report.matches:
        lines.append(
            "Nenhum jogo disponível; não existem totais ou médias calculáveis."
        )
    for match in report.matches:
        result = (
            "indisponível"
            if match.goals_for is None or match.goals_against is None
            else f"{match.goals_for}–{match.goals_against}"
        )
        outcome = "" if match.outcome is None else f" ({_OUTCOMES[match.outcome]})"
        lines.append(
            f"- Jogo {match.reference.source_match_id} | "
            f"{match.kickoff_at.isoformat().replace('+00:00', 'Z')} | "
            f"{'casa' if match.is_home else 'fora'} vs {match.opponent_name} | "
            f"{result}{outcome}; "
            f"estado declarado: {match.score_status}."
        )
    lines.extend(["", "MÉTRICAS — cobertura sobre os jogos efetivamente selecionados"])
    for category, title in _CATEGORIES.items():
        metric = report.metrics[category]
        lines.append(
            f"{title} — cobertura {metric.covered_matches}/{metric.selected_matches}"
        )
        if metric.values is None:
            lines.append("  Total da janela: indisponível.")
        else:
            lines.extend(
                f"  {_field_label(key)}: {value}"
                for key, value in metric.values.items()
            )
        if metric.values is None and metric.covered_values is not None:
            lines.append(
                "  Subtotal apenas dos jogos cobertos (não é total da janela):"
            )
            lines.extend(
                f"    {_field_label(key)}: {value}"
                for key, value in metric.covered_values.items()
            )
        for missing in metric.missing:
            lines.append(f"  Jogo {missing.source_match_id}: {missing.reason}")
    lines.extend(["", "AVISOS DE QUALIDADE"])
    lines.extend(f"- {warning}" for warning in report.warnings)
    lines.append("- Não se apresentam pontos oficiais sem regulamento validado.")
    lines.extend(
        [
            "",
            "REFERÊNCIAS AUDITÁVEIS",
            f"Origem: {report.source_system}/{report.source_instance_id}",
            f"Snapshot: {report.snapshot_version}",
            f"Exportado em: {report.exported_at.isoformat()}",
            f"Limite da seleção: {report.selection.as_of.isoformat()}",
            f"Fórmulas: {report.metrics['competitive'].formula_version}",
        ]
    )
    for match in report.matches:
        reference = match.reference
        events = ", ".join(reference.event_ids) if reference.event_ids else "nenhum"
        evidence = ", ".join(match.score_provenance.reference_ids) or "nenhuma"
        lines.append(
            f"- Jogo {reference.source_match_id}: versão {reference.data_version}; "
            f"fonte {match.source_reference.resource}:{match.source_reference.id}; "
            f"eventos [{events}]; proveniência {match.score_provenance.method}; "
            f"evidências [{evidence}]."
        )
    return "\n".join(lines) + "\n"


def run_demo(
    scenario: str = "complete_five",
    *,
    with_llm: bool = False,
    with_narrative: bool = False,
    model: str = "",
    ollama_url: str = "http://127.0.0.1:11434",
    client: ChatClient | None = None,
) -> str:
    """Preserva o factual; só faz um pedido opcional com opt-in explícito.

    O cliente injetado permite demonstrar respostas e falhas sem servidor real.
    O estado da interpretação pertence à secção opcional, sem alterar o relatório.
    """
    report = load_demo_report(scenario)
    factual = _render_report(report)
    if with_narrative:
        result = _select_narrative(report, model, ollama_url, client)
        return factual + (
            "\nNARRATIVA FUNDAMENTADA — observação de golos marcados num jogo\n"
            f"narrative_status={result.status}; reason={result.reason}\n"
            + (
                result.text + "\n"
                if result.text
                else "Narrativa indisponível; conserva-se o relatório factual.\n"
            )
        )
    if not with_llm:
        return factual
    from footballiq.analyst_interpretation import render_interpretation

    interpretation = _select_interpretation(report, model, ollama_url, client)
    return factual + render_interpretation(interpretation)


def _select_interpretation(
    report: FactualReport,
    model: str,
    ollama_url: str,
    client: ChatClient | None,
) -> InterpretationResult:
    from footballiq.analyst_interpretation import InterpretationResult, interpret_report
    from footballiq.ollama_client import OllamaClient, OllamaSettings

    try:
        if client is None:
            client = OllamaClient(OllamaSettings(model=model, url=ollama_url))
        interpretation = interpret_report(report, client)
    except ValueError:
        interpretation = InterpretationResult(
            "unavailable",
            warning="Configure um modelo e um endpoint HTTP local válido.",
        )
    return interpretation


def _select_narrative(
    report: FactualReport, model: str, ollama_url: str, client: ChatClient | None
) -> NarrativeResult:
    """Partilha a fronteira opt-in entre texto e HTML sem alterar os timeouts."""
    from footballiq.grounded_narrative.orchestrator import (
        NarrativeResult,
        narrate_report,
    )
    from footballiq.ollama_client import OllamaClient, OllamaSettings, OllamaUnavailable

    try:
        narrative_client = (
            client
            if client is not None
            else OllamaClient(OllamaSettings(model=model, url=ollama_url))
        )
        return narrate_report(report, enabled=True, client=narrative_client)
    except OllamaUnavailable:
        return NarrativeResult("unavailable", "invalid_settings")


def render_demo_dashboard(
    scenario: str = "complete_five",
    *,
    with_llm: bool = False,
    with_narrative: bool = False,
    model: str = "",
    ollama_url: str = "http://127.0.0.1:11434",
    client: ChatClient | None = None,
) -> str:
    """Gera HTML de uma fixture aprovada; só consulta Ollama com opt-in explícito."""
    from footballiq.analyst_dashboard import render_dashboard

    report = load_demo_report(scenario)
    if with_narrative:
        if with_llm:
            raise ValueError("Escolha --with-narrative ou --with-llm.")
        narrative = _select_narrative(report, model, ollama_url, client)
        return render_dashboard(report, narrative=narrative)
    interpretation = (
        _select_interpretation(report, model, ollama_url, client) if with_llm else None
    )
    return render_dashboard(report, interpretation)


def main(argv: Sequence[str] | None = None) -> int:
    """Mostra o relatório; grava HTML e abre o navegador apenas por opções explícitas."""
    parser = argparse.ArgumentParser(
        description="FootballIQ AI Analyst: dados fictícios."
    )
    parser.add_argument(
        "--fixture", choices=tuple(_FIXTURE_HASHES), default="complete_five"
    )
    parser.add_argument(
        "--with-llm",
        action="store_true",
        help="Ativa seleção opcional de factos por Ollama.",
    )
    parser.add_argument(
        "--with-narrative",
        action="store_true",
        help="Ativa planos fundamentados por seleção fechada em Ollama.",
    )
    parser.add_argument(
        "--model", default="", help="Nome exato de um modelo já instalado."
    )
    parser.add_argument(
        "--ollama-url",
        default="http://127.0.0.1:11434",
        help="Endpoint HTTP de loopback; não aceita credenciais ou proxies.",
    )
    parser.add_argument(
        "--html", action="store_true", help="Gera um dashboard HTML local autónomo."
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Destino .html; por defeito cria um ficheiro temporário.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Autoriza substituir um destino .html existente.",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Abre o HTML no navegador depois de o guardar.",
    )
    arguments = parser.parse_args(argv)
    if arguments.with_narrative and arguments.with_llm:
        parser.error("--with-narrative não combina com --with-llm.")
    if not arguments.html and (
        arguments.output or arguments.overwrite or arguments.open
    ):
        parser.error("--output, --overwrite e --open exigem --html.")
    try:
        renderer = render_demo_dashboard if arguments.html else run_demo
        narrative_options = {"with_narrative": True} if arguments.with_narrative else {}
        output = renderer(
            arguments.fixture,
            with_llm=arguments.with_llm,
            model=arguments.model,
            ollama_url=arguments.ollama_url,
            **narrative_options,
        )
    except _LOAD_ERRORS:
        print(
            "Não foi possível carregar a fixture aprovada. "
            "Execute a demonstração num checkout completo do FootballIQ.",
            file=sys.stderr,
        )
        return 1
    if arguments.html:
        from footballiq.analyst_dashboard import save_dashboard

        try:
            destination = save_dashboard(
                output, arguments.output, overwrite=arguments.overwrite
            )
        except _LOAD_ERRORS:
            print(
                "Não foi possível guardar o HTML. Verifique o diretório e a extensão; um ficheiro existente exige --overwrite.",
                file=sys.stderr,
            )
            return 1
        print(f"Dashboard criado: {destination}")
        if arguments.open:
            import webbrowser

            try:
                opened = webbrowser.open(destination.as_uri())
            except webbrowser.Error:
                opened = False
            except OSError:
                opened = False
            if not opened:
                print(
                    "O navegador não abriu. Abra manualmente o ficheiro indicado.",
                    file=sys.stderr,
                )
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
