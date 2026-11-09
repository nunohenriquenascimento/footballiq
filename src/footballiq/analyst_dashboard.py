"""Dashboard HTML autónomo, sem scripts, rede ou cálculos de métricas."""

from __future__ import annotations

import html
import tempfile
from pathlib import Path

from footballiq.analyst_interpretation import InterpretationResult, prepare_facts
from footballiq.analytics import FactualReport, MetricSummary
from footballiq.trends import TREND_LABELS, UNAVAILABLE_REASONS, calculate_trends

_CSS = """
:root{color-scheme:light;--ink:#152536;--muted:#526375;--line:#dde4e9;
--nav:#102131;--lime:#d1f979;--paper:#f3f6f8;--green:#176342;--red:#a52d42}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:24px}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif;overflow-wrap:anywhere}
a{color:#165581;text-underline-offset:3px}a:focus-visible,summary:focus-visible{outline:3px solid #a05b00;outline-offset:5px}
.skip{position:absolute;top:-80px;left:16px;background:white;padding:12px;z-index:5}.skip:focus{top:12px}
.sidebar{position:fixed;inset:0 auto 0 0;width:216px;background:var(--nav);color:#fff;padding:32px 24px;display:flex;flex-direction:column;gap:36px;overflow-y:auto}
.brand{font-size:23px;font-weight:800;letter-spacing:-1px;display:flex;align-items:center;gap:10px}
.brand-name{white-space:nowrap}.brand-mark{flex-shrink:0}
.brand-mark{display:grid;place-items:center;background:var(--lime);color:var(--nav);height:34px;width:34px;border-radius:10px;font-size:14px;letter-spacing:-1px}
.brand small{color:var(--lime)}.sidebar nav{display:grid;gap:8px}.sidebar nav a{color:#d3dfe9;text-decoration:none;padding:10px 12px;border-radius:8px}
.sidebar nav a:first-child{background:#21394a;color:var(--lime)}.sidebar nav a:hover{background:#21394a}.sidebar-note{margin-top:auto;font-size:12px;color:#bdcdd8;border-top:1px solid #314351;padding-top:20px}
main{max-width:1540px;margin-left:216px;padding:30px 42px 48px}.topbar{display:flex;justify-content:space-between;align-items:center;gap:14px;margin-bottom:32px}
.eyebrow{font-size:11px;text-transform:uppercase;letter-spacing:1.8px;font-weight:750;color:var(--muted)}.badge{font-size:11px;font-weight:800;letter-spacing:1px;border:1px solid #9bb56b;background:#edf7d9;color:#375014;border-radius:99px;padding:6px 12px}
h1{font-size:clamp(32px,4vw,44px);line-height:1.12;margin:6px 0 12px;letter-spacing:-1.6px}h2{font-size:20px;line-height:1.3;margin:0 0 6px;letter-spacing:-.4px}h3{font-size:15px;margin:0 0 8px}p{margin:0 0 12px}.muted{color:var(--muted)}.small{font-size:12px}
.hero{position:relative;overflow:hidden;border-radius:18px;background:var(--nav);color:#fff;padding:28px 32px;margin:24px 0}.hero:after{content:"";position:absolute;right:-25px;top:-60px;width:210px;height:210px;border:1px solid #4a665a;border-radius:50%;pointer-events:none}
.hero .eyebrow{color:var(--lime)}blockquote{margin:10px 0;font-size:clamp(19px,2.2vw,27px);line-height:1.45;max-width:820px;position:relative;z-index:1}.hero p{color:#d3dfe9;margin:12px 0 0;font-size:13px}
.section-head{display:flex;justify-content:space-between;align-items:end;gap:20px;margin-bottom:18px}.cards{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:14px;margin:20px 0}
.card,.panel{background:white;border:1px solid var(--line);border-radius:14px}.card{padding:18px 20px;min-width:0}.card-label{font-size:12px;color:var(--muted)}.card strong{display:block;font-size:34px;line-height:1.25;margin:8px 0;letter-spacing:-1px;font-variant-numeric:tabular-nums}.card small{font-size:11px;color:var(--muted)}
.form-strip{display:flex;justify-content:space-between;align-items:center;gap:18px;padding:16px 0 24px;flex-wrap:wrap}.sequence{display:flex;flex-wrap:wrap;gap:7px;list-style:none;padding:0;margin:8px 0}.result{display:inline-grid;place-items:center;min-width:32px;height:32px;padding:0 9px;border-radius:8px;font-size:12px;font-weight:800}
.win{color:var(--green);background:#e2f2e8}.draw{color:#5f4c0d;background:#fff3cb}.loss{color:var(--red);background:#fde9ed}.unknown{color:#536274;background:#e9edf2}.legend{font-size:12px;color:var(--muted)}
.two-columns{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(280px,1fr);gap:22px;align-items:start}.panel{padding:24px;min-width:0}.panel-header{display:flex;justify-content:space-between;gap:16px;margin-bottom:20px}.counter{font-size:12px;padding:4px 9px;border-radius:8px;background:#edf2f5;white-space:nowrap;height:fit-content}
.matches{list-style:none;margin:0;padding:0}.match{display:grid;grid-template-columns:36px minmax(0,1fr) auto;gap:12px;align-items:center;padding:16px 0;border-bottom:1px solid var(--line)}.match:last-child{border:0}.match-title{font-weight:650}.score{font-size:23px;font-weight:800;font-variant-numeric:tabular-nums;white-space:normal;overflow-wrap:anywhere}.match time{font-size:12px;color:var(--muted)}
.ai{border-top:3px solid #779b3e}.ai-header{display:flex;align-items:center;gap:10px;margin-bottom:12px}.ai-icon{display:grid;place-items:center;width:38px;height:38px;border-radius:11px;background:#edf7d9;font-weight:800;color:#375014}.state{font-size:11px;font-weight:750;display:inline-block;padding:4px 9px;border-radius:6px;background:#edf2f5;margin:6px 0 16px}.observations{padding-left:20px}.observations li{padding-bottom:14px}.observations a{font-size:12px}.notice{padding:12px 14px;border-radius:8px;background:#f2f5f7;font-size:12px;color:var(--muted)}
.metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-top:20px;align-items:start}.metric{padding:20px;border-radius:12px;background:white;border:1px solid var(--line)}.metric-head{display:flex;justify-content:space-between;gap:12px;align-items:start}.metric dl{margin:12px 0 0}.metric dl div{display:flex;justify-content:space-between;gap:16px;padding:5px 0}.metric dt{color:var(--muted);font-size:13px}.metric dd{margin:0;font-weight:650;font-variant-numeric:tabular-nums}.metric li{font-size:12px;color:var(--muted)}.metric ul{padding-left:18px}.subtotal{font-size:12px;font-weight:700;color:#775315}
section{margin-bottom:28px}.quality{margin-top:26px}.quality ul{margin-bottom:0;padding-left:20px;color:var(--muted);font-size:13px}.reference-list{display:grid;gap:10px;margin-top:18px}.reference-list details{background:#fff;border:1px solid var(--line);border-radius:10px;padding:12px 16px}.reference-list summary{cursor:pointer;font-weight:650;font-size:13px}.reference-list dl{font-size:12px;color:var(--muted);margin-bottom:0}.reference-list dt{font-weight:700;margin-top:8px}.reference-list dd{margin:0;overflow-wrap:anywhere}.meta{display:flex;flex-wrap:wrap;gap:8px 24px;font-size:12px;color:var(--muted);margin-top:14px}
.empty{padding:28px 12px;border:1px dashed #b8c6d0;border-radius:10px;text-align:center;color:var(--muted);margin-top:16px}.footer{margin-top:28px;border-top:1px solid var(--line);padding-top:18px;color:var(--muted);font-size:11px;display:flex;justify-content:space-between;gap:20px}.wrap{overflow-wrap:anywhere}
@media(max-width:1180px){main{padding:24px}.sidebar{width:188px;padding:28px 18px}main{margin-left:188px}.cards{gap:9px}.card{padding:16px 12px}.two-columns{grid-template-columns:minmax(0,1.3fr) minmax(260px,1fr)}}
@media(max-width:900px){.sidebar{position:static;width:auto;padding:16px 22px;gap:14px}.sidebar nav{display:flex;flex-wrap:wrap;gap:4px}.sidebar nav a{font-size:12px;padding:6px 10px}.sidebar-note{display:none}main{margin:0;padding:24px}.two-columns{grid-template-columns:1fr}.cards{grid-template-columns:repeat(3,minmax(0,1fr))}.hero{padding:24px}.topbar{margin-bottom:22px}}
@media(max-width:540px){.sidebar{padding:16px 14px}main{padding:18px 14px}.cards{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.card:last-child{grid-column:1/-1}.card strong{font-size:30px}.panel{padding:18px}.metrics{grid-template-columns:1fr}.topbar{align-items:start;flex-wrap:wrap}.hero{padding:22px}.section-head{align-items:start;flex-direction:column;gap:4px}.score{font-size:18px}.match{grid-template-columns:30px minmax(0,1fr) auto;gap:8px}.footer{flex-direction:column;gap:6px}.badge{font-size:9px}.counter{white-space:normal}blockquote{font-size:20px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
@media print{.sidebar,.skip{display:none}main{margin:0;padding:0}.card,.panel,.metric{break-inside:avoid}body{background:white}.hero{background:white;color:var(--ink);border:1px solid var(--line)}.hero:after{display:none}.hero .eyebrow,.hero p{color:var(--ink)}details::details-content{content-visibility:visible;display:block}}
"""

_OUTCOMES = {
    "win": ("V", "Vitória", "win"),
    "draw": ("E", "Empate", "draw"),
    "loss": ("D", "Derrota", "loss"),
    None: ("?", "Resultado não verificado", "unknown"),
}
_INTERPRETATION_ERRORS = (ValueError, KeyError, TypeError)
_CATEGORIES = {
    "shots": "Remates",
    "cards": "Cartões",
    "substitutions": "Substituições",
    "temporal_goals": "Distribuição temporal dos golos",
    "points": "Pontos",
}
_FIELDS = {
    "on_target": "Remates enquadrados",
    "off_target": "Remates desenquadrados",
    "blocked": "Remates bloqueados",
    "total": "Remates totais",
    "yellow": "Cartões amarelos",
    "red": "Cartões vermelhos",
    "substitutions": "Substituições",
    "points": "Pontos",
    "wins": "Vitórias",
    "draws": "Empates",
    "losses": "Derrotas",
    "goals_for": "Golos a favor",
    "goals_against": "Golos contra",
    "goal_difference": "Diferença de golos",
    "average_goals_for": "Média de golos a favor",
    "average_goals_against": "Média de golos contra",
}


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)


def _label(key: str) -> str:
    if key in _FIELDS:
        return _FIELDS[key]
    prefix, _, side = key.rpartition("_")
    perspective = "a favor" if side == "for" else "contra"
    if prefix.startswith("period_"):
        return f"Golos · {prefix.removeprefix('period_')}.º período · {perspective}"
    if prefix.startswith("minute_"):
        return f"Golos · minutos {prefix.removeprefix('minute_')} · {perspective}"
    return f"{_FIELDS.get(prefix, prefix)} · {perspective}"


def _coverage(metric: MetricSummary) -> str:
    return f"{metric.covered_matches}/{metric.selected_matches}"


def _values(values: dict[str, int | float]) -> str:
    return (
        "<dl>"
        + "".join(
            f"<div><dt>{_e(_label(key))}</dt><dd>{_e(value)}</dd></div>"
            for key, value in values.items()
        )
        + "</dl>"
    )


def _metric(title: str, metric: MetricSummary) -> str:
    content = '<p class="muted small">Total da janela indisponível.</p>'
    if metric.values is not None:
        content = _values(metric.values)
    elif metric.covered_values is not None:
        content += '<p class="subtotal">Subtotal dos jogos cobertos — não é o total da janela.</p>'
        content += _values(metric.covered_values)
    if metric.missing:
        content += (
            "<ul>"
            + "".join(
                f"<li>Jogo {_e(item.source_match_id)}: {_e(item.reason)}</li>"
                for item in metric.missing
            )
            + "</ul>"
        )
    return (
        '<article class="metric"><div class="metric-head">'
        f'<h3>{_e(title)}</h3><span class="counter">Cobertura {_e(_coverage(metric))}</span>'
        f"</div>{content}</article>"
    )


def _ai(report: FactualReport, interpretation: InterpretationResult | None) -> str:
    state = (
        "not_requested"
        if interpretation is None
        else interpretation.interpretation_status
    )
    body = '<p class="muted">A leitura factual está pronta. Não foi solicitada seleção de factos por um modelo.</p>'
    if interpretation is not None and state == "available":
        # Reconfirma o catálogo: o dataclass por si só não prova validação.
        try:
            prepared = prepare_facts(report)
            catalog = {fact.fact_id: fact for fact in prepared.facts}
            selected = interpretation.observations
            valid = (
                interpretation.summary == prepared.summary
                and 1 <= len(selected) <= 5
                and len({fact.fact_id for fact in selected}) == len(selected)
                and all(catalog.get(fact.fact_id) == fact for fact in selected)
            )
        except _INTERPRETATION_ERRORS:
            valid = False
        if not valid:
            state = "unavailable"
            body = '<p class="muted">Interpretação não verificável. O relatório factual mantém-se disponível.</p>'
        else:
            anchors = {
                f"match:{m.reference.source_match_id}": index
                for index, m in enumerate(report.matches)
            }
            observations = []
            for fact in selected:
                links = " · ".join(
                    f'<a href="#match-{anchors[ref]}">{_e(ref)}</a>'
                    for ref in fact.references
                )
                observations.append(f"<li>{_e(fact.text)}<br>{links}</li>")
            body = f'<p>{_e(interpretation.summary)}</p><ol class="observations">{"".join(observations)}</ol>'
    elif interpretation is not None:
        body = f'<p class="muted">{_e(interpretation.warning)}</p><p class="small">O relatório factual mantém-se disponível.</p>'
    return (
        '<aside class="panel ai" id="analyst" aria-labelledby="analyst-title">'
        '<div class="ai-header"><span class="ai-icon" aria-hidden="true">AI</span>'
        '<div><h2 id="analyst-title">AI Analyst</h2><span class="small muted">Camada opcional de seleção</span></div></div>'
        f'<span class="state">{_e(state)}</span>{body}'
        '<p class="notice">O modelo seleciona factos conhecidos. Os números vêm do motor factual; não há hipóteses táticas nem prosa livre.</p></aside>'
    )


def _trend_number(value: int | float) -> str:
    """Limita a apresentação a três decimais; assinala aproximações sem alterar factos."""
    if isinstance(value, int):
        return str(value)
    rounded = round(value, 3)
    text = f"{rounded:.3f}".rstrip("0").rstrip(".").replace(".", ",")
    return ("≈ " if rounded != value else "") + text


def _trends(report: FactualReport) -> str:
    """Apresenta amostras e motivos com escape, sem gráficos ou extrapolação."""
    trends = calculate_trends(report)
    labels = {"win": "V", "draw": "E", "loss": "D", None: "?"}
    rows = "".join(
        f"<li>Jogo {_e(g.match_id)} · {_e(g.kickoff_at)} · "
        f"{'Casa' if g.is_home else 'Fora'} · {_e(labels[g.outcome])} · "
        f"GF {_e(g.goals_for if g.goals_for is not None else 'Indisponível')} · "
        f"GA {_e(g.goals_against if g.goals_against is not None else 'Indisponível')} · "
        f"Diferença {_e(g.goal_difference if g.goal_difference is not None else 'Indisponível')} · "
        f"Versão {_e(g.data_version)} · {'Resultado não verificado' if g.reason else 'Resultado verificado'}</li>"
        for g in trends.games
    )
    samples = []
    for title, sample in (
        ("Janela", trends.window),
        ("Casa", trends.home),
        ("Fora", trends.away),
        ("Mais antigos", trends.older),
        ("Mais recentes", trends.newer),
    ):
        values = sample.covered_values
        body = (
            "<p>Indisponível.</p>"
            if values is None
            else "<dl>"
            + "".join(
                f"<div><dt>{_e(TREND_LABELS[key])}</dt><dd>{_e(_trend_number(value))}</dd></div>"
                for key, value in values.items()
            )
            + "</dl>"
        )
        samples.append(
            f'<article class="metric"><h3>{title}</h3><p>Cobertura {len(sample.used_ids)}/{len(sample.selected_ids)}; '
            f"IDs utilizados: {_e(', '.join(sample.used_ids) or 'Nenhum')}. "
            f"IDs selecionados: {_e(', '.join(sample.selected_ids) or 'Nenhum')}.</p>"
            f"<p>{_e(UNAVAILABLE_REASONS.get(sample.reason, 'Total da amostra disponível'))}</p>"
            + (
                "<p>Subtotal apenas — total indisponível.</p>"
                if sample.values is None and values
                else ""
            )
            + body
            + (
                "<p>Variabilidade indisponível: exige dois resultados verificados.</p>"
                if len(sample.used_ids) < 2
                else ""
            )
            + (
                f"<p>Estabilidade indisponível: {_e(UNAVAILABLE_REASONS[sample.stability_reason])}</p>"
                if sample.stability_reason
                else ""
            )
            + "</article>"
        )
    comparison = "Indisponível: " + UNAVAILABLE_REASONS.get(trends.temporal_reason, "")
    if trends.temporal_change is not None:
        comparison = (
            f"Média GF: {_trend_number(trends.temporal_change['average_goals_for'])}; "
            f"média GA: {_trend_number(trends.temporal_change['average_goals_against'])}."
        )
    return (
        '<section id="trends" aria-labelledby="trends-title"><h2 id="trends-title">Tendências competitivas</h2>'
        "<p>Dados fictícios. Ordem: mais antigo primeiro. V Vitória · E Empate · D Derrota · ? Indisponível.</p>"
        + (
            f"<ol>{rows}</ol>"
            if rows
            else "<p>Não há jogos para apresentar tendências.</p>"
        )
        + f'<div class="metrics">{"".join(samples)}</div>'
        f"<p>Comparação temporal, recente menos antigo: {_e(comparison)}</p>"
        f"<p>Comparação casa/fora: {_e(UNAVAILABLE_REASONS.get(trends.venue_reason, 'disponível; consultar amostras e denominadores acima'))}</p>"
        "<p>Grupos pequenos e de dimensão possivelmente diferente; médias descritivas, sem significância estatística. "
        "Variância e amplitude exigem dois resultados; estabilidade usa apenas pares adjacentes verificados, sem saltar lacunas. "
        "A contagem de resultados iguais não é um índice de estabilidade nem uma previsão. "
        "Empates de data/hora são ordenados pelo ID, sem estabelecer precedência temporal. "
        "Valores apresentados com até três decimais; ≈ indica arredondamento. "
        "Não permitem concluir causas nem extrapolar para a época.</p>"
        f"<p>Snapshot {_e(trends.snapshot_version)} · Fórmula {_e(trends.formula_version)}</p></section>"
    )


def render_dashboard(
    report: FactualReport,
    interpretation: InterpretationResult | None = None,
) -> str:
    """Renderiza valores do motor com escape, sem os recalcular ou contactar serviços.

    A CLI fornece apenas fixtures aprovadas. A identidade fictícia não é uma
    fronteira de autorização: este documento destina-se exclusivamente à demonstração.
    """
    if report.source_instance_id != "fictional-local-demo":
        raise ValueError("O dashboard aceita apenas o relatório de demonstração.")
    competitive = report.metrics["competitive"]
    cards = []
    for key, title in [
        ("wins", "Vitórias"),
        ("draws", "Empates"),
        ("losses", "Derrotas"),
        ("goals_for", "Golos a favor"),
        ("goals_against", "Golos contra"),
    ]:
        value = None if competitive.values is None else competitive.values[key]
        display = "—" if value is None else _e(value)
        note = f"Cobertura {_coverage(competitive)}"
        if value is None:
            note = f"Indisponível · {note}"
        cards.append(
            f'<article class="card"><span class="card-label">{title}</span><strong>{display}</strong><small>{_e(note)}</small></article>'
        )
    matches = []
    sequence = []
    references = []
    for index, match in enumerate(report.matches):
        symbol, outcome, style = _OUTCOMES[match.outcome]
        stamp = match.kickoff_at.isoformat().replace("+00:00", "Z")
        day = match.kickoff_at.strftime("%d/%m/%Y · %H:%M UTC")
        score = (
            "Indisponível"
            if match.goals_for is None or match.goals_against is None
            else f"{match.goals_for}–{match.goals_against}"
        )
        sequence.append(
            f'<li><span class="result {style}" role="img" title="{_e(outcome)}" aria-label="{_e(outcome)}">{symbol}</span></li>'
        )
        matches.append(
            f'<li class="match" id="match-{index}"><span class="result {style}" role="img" aria-label="{_e(outcome)}">{symbol}</span>'
            f'<div><div class="match-title">{_e(match.opponent_name)}</div><time datetime="{_e(stamp)}">{_e(day)}</time>'
            f'<div class="small muted">{"Casa" if match.is_home else "Fora"} · Jogo {_e(match.reference.source_match_id)} · {_e(match.score_status)}</div></div>'
            f'<span class="score">{_e(score)}</span></li>'
        )
        evidence = ", ".join(match.score_provenance.reference_ids) or "Nenhuma"
        events = ", ".join(match.reference.event_ids) or "Nenhum"
        external = (
            "; ".join(f"{ref.resource}:{ref.id}" for ref in match.external_references)
            or "Nenhuma"
        )
        references.append(
            f"<details><summary>Jogo {_e(match.reference.source_match_id)} · {_e(day)}</summary><dl>"
            f"<dt>Versão dos dados</dt><dd>{_e(match.reference.data_version)}</dd>"
            f"<dt>Fonte</dt><dd>{_e(match.source_reference.resource)}:{_e(match.source_reference.id)}</dd>"
            f"<dt>Eventos</dt><dd>{_e(events)}</dd><dt>Proveniência declarada</dt><dd>{_e(match.score_provenance.method)} · {_e(evidence)}</dd>"
            f"<dt>Referências externas</dt><dd>{_e(external)}</dd></dl></details>"
        )
    count = report.selection.returned_count
    summary = f"{count} jogos analisados de um máximo de {report.selection.limit}."
    if competitive.values is None:
        summary += " Os totais competitivos estão indisponíveis; consulte a cobertura e os motivos."
    else:
        summary += f" Cobertura dos resultados: {_coverage(competitive)}. Resultados na perspetiva da equipa."
    if not matches:
        match_content = '<div class="empty"><h3>Ainda sem jogos neste snapshot</h3><p>Não existem resultados, totais ou médias calculáveis.</p></div>'
    else:
        match_content = f'<ol class="matches">{"".join(matches)}</ol>'
    metrics = _metric("Resultados e médias", competitive) + "".join(
        _metric(title, report.metrics[key]) for key, title in _CATEGORIES.items()
    )
    warnings = "".join(f"<li>{_e(warning)}</li>" for warning in report.warnings)
    reference_content = (
        "".join(references)
        or '<p class="muted">Sem referências de jogos neste snapshot.</p>'
    )
    return f"""<!doctype html>
<html lang="pt-PT"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'none'; connect-src 'none'; img-src 'none'; base-uri 'none'; form-action 'none'">
<meta name="referrer" content="no-referrer"><title>FootballIQ · AI Analyst · Demonstração</title><style>{_CSS}</style></head>
<body><a class="skip" href="#content">Saltar para o conteúdo</a>
<header class="sidebar"><div class="brand"><span class="brand-mark">FIQ</span><span class="brand-name">Football<small>IQ</small></span></div>
<nav aria-label="Navegação do relatório"><a href="#overview">Visão geral</a><a href="#games">Jogos analisados</a><a href="#statistics">Estatísticas</a><a href="#trends">Tendências</a><a href="#analyst">AI Analyst</a><a href="#references">Referências</a></nav>
<p class="sidebar-note">LABORATÓRIO LOCAL<br>Snapshot de demonstração<br>Sem ligação a dados operacionais</p></header>
<main id="content" tabindex="-1"><div class="topbar"><span class="eyebrow">Demonstração / Análise da equipa</span><span class="badge">DADOS FICTÍCIOS</span></div>
<section id="overview" aria-labelledby="page-title"><div class="eyebrow">Inteligência a partir dos factos</div><h1 id="page-title">AI Analyst</h1><p class="muted">A leitura dos últimos jogos, com cobertura e evidência à vista.</p>
<div class="hero"><span class="eyebrow">A pergunta analisada</span><blockquote>Analisa os últimos cinco jogos da minha equipa.</blockquote><p>Equipa {_e(report.selection.team_id)} · Época {_e(report.selection.season_id)} · Até {_e(report.selection.as_of.strftime("%d/%m/%Y · %H:%M UTC"))}</p></div>
<div class="section-head"><div><h2>Resumo executivo factual</h2><p class="muted small">{_e(summary)}</p></div><span class="counter">{_e(count)}/{_e(report.selection.limit)} jogos</span></div>
<div class="cards">{"".join(cards)}</div><div class="form-strip"><div><span class="eyebrow">Sequência · mais recente primeiro</span><ol class="sequence" aria-label="Sequência de resultados">{"".join(sequence)}</ol></div><p class="legend">V Vitória · E Empate · D Derrota · ? Não verificado</p></div></section>
<section class="two-columns" aria-label="Jogos e interpretação"><article class="panel" id="games"><div class="panel-header"><div><h2>Jogos analisados</h2><p class="muted small">Ordem cronológica inversa · marcados–sofridos</p></div><span class="counter">{_e(count)} jogos</span></div>{match_content}</article>{_ai(report, interpretation)}</section>
<section id="statistics" aria-labelledby="statistics-title"><div class="section-head"><div><h2 id="statistics-title">Estatísticas com contexto</h2><p class="muted small">Cobertura n/N dos jogos selecionados. Indisponível não significa zero.</p></div></div><div class="metrics">{metrics}</div></section>
{_trends(report)}
<section class="panel quality" aria-labelledby="quality-title"><h2 id="quality-title">Qualidade e limites de leitura</h2><ul>{warnings}<li>Dados fictícios: estados verified/complete são declarações da fixture, não certificação operacional.</li><li>Não se apresentam pontos oficiais sem regulamento validado.</li><li>Este HTML não prova autorização, autenticidade ou atualidade na origem.</li></ul></section>
<section id="references" aria-labelledby="references-title"><h2 id="references-title">Referências auditáveis</h2><p class="muted small">Expanda cada jogo para consultar versões e evidências.</p><div class="meta"><span>Origem: {_e(report.source_system)}/{_e(report.source_instance_id)}</span><span class="wrap">Snapshot: {_e(report.snapshot_version)}</span><span>Fórmulas: {_e(competitive.formula_version)}</span><span>Exportado: {_e(report.exported_at.isoformat())}</span></div><div class="reference-list">{reference_content}</div></section>
<footer class="footer"><span>FootballIQ · Dados fictícios — demonstração local</span><span>Factos primeiro. Interpretação separada.</span></footer></main></body></html>"""


def save_dashboard(
    document: str, output: Path | None = None, *, overwrite: bool = False
) -> Path:
    """Guarda HTML local; usa ficheiro temporário por defeito e recusa sobrescrita.

    Um destino explícito exige extensão .html e diretório já existente. Links
    simbólicos não são aceites, mesmo com overwrite. Não abre o navegador.
    """
    if output is None:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".html",
            prefix="footballiq-demo-",
            delete=False,
        ) as file:
            file.write(document)
            return Path(file.name)
    output = output.absolute()
    if output.suffix.lower() != ".html" or output.is_symlink():
        raise ValueError("Escolha um ficheiro .html normal, sem link simbólico.")
    with output.open("w" if overwrite else "x", encoding="utf-8") as file:
        file.write(document)
    return output
