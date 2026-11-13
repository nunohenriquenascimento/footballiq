"""Catálogo offline aditivo; não altera o contrato narrativo nem o seletor Ollama."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from footballiq.analytics import FactualReport
from footballiq.trends import TREND_LABELS, calculate_trends

from .contract import (
    EvidenceBundle,
    EvidenceReference,
    GroundedNarrativeValidator,
    NarrativeAssertion,
    NarrativePlan,
    NarrativeRelation,
    _content_digest,
    _plain_fact_value,
    build_available_facts,
)

CATALOG_VERSION = "footballiq.insights.v1"
_LABELS = {
    **TREND_LABELS,
    "goals_for": "Golos marcados",
    "goals_against": "Golos sofridos",
}


def _number(value: int | float) -> str:
    return (
        str(value).replace(".", ",")
        if isinstance(value, int)
        else f"{value:.3f}".replace(".", ",")
    )


def build_insights(report: FactualReport) -> EvidenceBundle:
    """Acrescenta factos descritivos com proveniência, sem modificar o relatório.

    O relatório é uma entrada confiável do backend, não uma prova de origem.
    Subtotais conservam a sua amostra; nunca representam toda a janela.
    """
    report = FactualReport.model_validate(report.model_dump())
    trends = calculate_trends(report)
    base = build_available_facts(report, trends=trends)
    facts = _plain_fact_value(base.facts)
    matches = {m.reference.source_match_id: m for m in report.matches}

    def add(
        name: str,
        text: str,
        ids: tuple[str, ...],
        selected: int,
        formula: str,
        values: Mapping[str, Any],
    ) -> None:
        if not ids or not selected:
            return
        facts[f"insight:{name}"] = {
            "fact_kind": "insight",
            "fact_version": CATALOG_VERSION,
            "formula_version": formula,
            "snapshot_version": report.snapshot_version,
            "source_system": report.source_system,
            "source_instance_id": report.source_instance_id,
            "references": [f"match:{mid}" for mid in ids],
            "covered_matches": len(ids),
            "selected_matches": selected,
            "coverage": len(ids) / selected,
            "value": dict(values),
            "text": text
            + f" Cobertura {len(ids)}/{selected}; amostra {len(ids)}."
            + (" Apenas subtotal dos jogos cobertos." if len(ids) < selected else "")
            + " Descrição da janela exportada; não constitui previsão."
            + f" Snapshot {report.snapshot_version}; catálogo {CATALOG_VERSION};"
            + f" fórmula {formula}; versões "
            + "; ".join(f"{mid}@{matches[mid].reference.data_version}" for mid in ids)
            + ".",
        }

    for name, sample in (
        ("form", trends.window),
        ("home", trends.home),
        ("away", trends.away),
    ):
        values = sample.covered_values
        if values is None:
            continue
        keys = (
            "wins",
            "draws",
            "losses",
            "clean_sheets",
            "failed_to_score",
            "average_goals_for",
            "average_goals_against",
        )
        title = {"form": "Forma recente", "home": "Casa", "away": "Fora"}[name]
        add(
            name,
            title
            + ": "
            + "; ".join(f"{_LABELS[k]}: {_number(values[k])}" for k in keys)
            + ". Médias por jogo coberto, arredondadas a três casas decimais.",
            sample.used_ids,
            len(sample.selected_ids),
            trends.formula_version,
            {k: values[k] for k in keys},
        )

    for category in ("competitive", "temporal_goals"):
        metric = report.metrics.get(category)
        if metric is None or not metric.covered_values:
            continue
        ids = tuple(ref.source_match_id for ref in metric.references)
        # Só se reutilizam agregados com proveniência operacional resolúvel.
        if (
            len(ids) != metric.covered_matches
            or len(set(ids)) != len(ids)
            or metric.selected_matches != len(matches)
            or any(mid not in matches for mid in ids)
            or any(
                ref != matches[ref.source_match_id].reference
                for ref in metric.references
            )
        ):
            continue
        if category == "competitive" and any(
            matches[mid].score_status != "verified" for mid in ids
        ):
            continue
        if category == "temporal_goals" and any(
            not ref.event_ids for ref in metric.references
        ):
            # Um agregado sem IDs de eventos não permite auditar minutos.
            continue
        values = metric.covered_values
        if category == "competitive":
            keys = (
                "goals_for",
                "goals_against",
                "average_goals_for",
                "average_goals_against",
            )
            text = "Golos: " + "; ".join(
                f"{_LABELS[k]}: {_number(values[k])}" for k in keys
            )
            values = {k: values[k] for k in keys}
        else:
            text = "Distribuição temporal dos golos: " + "; ".join(
                f"{'Período' if k.startswith('period_') else 'Minutos'} {k.split('_')[1]} {'a favor' if k.endswith('_for') else 'contra'}: {_number(v)}"
                for k, v in sorted(values.items())
            )
        add(
            category,
            text
            + (
                ". Médias arredondadas a três casas decimais."
                if category == "competitive"
                else "."
            ),
            ids,
            metric.selected_matches,
            metric.formula_version,
            values,
        )
        facts[f"insight:{category}"]["references"] = [
            ref.model_dump(mode="json") for ref in metric.references
        ]

    for name, reason, left, right, labels in (
        (
            "recent_vs_older",
            trends.temporal_reason,
            trends.newer,
            trends.older,
            ("Recentes", "Antigos"),
        ),
        (
            "home_vs_away",
            trends.venue_reason,
            trends.home,
            trends.away,
            ("Casa", "Fora"),
        ),
    ):
        if reason is not None:
            continue
        assert left.values is not None and right.values is not None
        keys = ("average_goals_for", "average_goals_against")
        text = (
            "Comparação descritiva de médias por jogo (arredondadas a três casas decimais): "
            + "; ".join(
                f"{label} (n={len(sample.used_ids)}): "
                + ", ".join(f"{_LABELS[k]} {_number(sample.values[k])}" for k in keys)
                for label, sample in zip(labels, (left, right), strict=True)
            )
            + "."
        )
        add(
            name,
            text,
            left.used_ids + right.used_ids,
            len(left.selected_ids) + len(right.selected_ids),
            trends.formula_version,
            {
                "left": {k: left.values[k] for k in keys},
                "right": {k: right.values[k] for k in keys},
                "left_n": len(left.used_ids),
                "right_n": len(right.used_ids),
                "left_ids": left.used_ids,
                "right_ids": right.used_ids,
                "left_selected": len(left.selected_ids),
                "right_selected": len(right.selected_ids),
            },
        )

    games = trends.games
    if games and len({g.kickoff_at for g in games}) == len(games):
        for name, predicate, label in (
            ("winning_run", lambda g: g.outcome == "win", "vitórias consecutivas"),
            (
                "winless_run",
                lambda g: g.outcome in {"draw", "loss"},
                "jogos consecutivos sem vencer",
            ),
            ("drawing_run", lambda g: g.outcome == "draw", "empates consecutivos"),
            ("losing_run", lambda g: g.outcome == "loss", "derrotas consecutivas"),
        ):
            run = []
            for game in reversed(games):
                if game.reason is not None or not predicate(game):
                    break
                run.append(game.match_id)
            if len(run) >= 2:
                add(
                    name,
                    f"No final da janela exportada: {len(run)} {label}, com resultados verificados. Contagem limitada à janela, sem atravessar resultados desconhecidos.",
                    tuple(reversed(run)),
                    len(games),
                    CATALOG_VERSION,
                    {"length": len(run)},
                )

    return EvidenceBundle(base.snapshot_id, _content_digest(facts), facts)


def prepare_insight_plans(bundle: EvidenceBundle) -> dict[str, NarrativePlan]:
    """Cria planos v1 de uma observação sobre cada facto composto autorizado.

    A relação é observação de um agregado local, não uma relação numérica
    arbitrária que o validador v1 não consiga demonstrar.
    """
    plans = {}
    for identity, fact in bundle.items():
        if fact.get("fact_kind") != "insight":
            continue
        plan = NarrativePlan(
            schema_version="1.0",
            evidence_snapshot_id=bundle.snapshot_id,
            evidence_digest=bundle.evidence_digest,
            coverage=fact["coverage"],
            sample_size=fact["covered_matches"],
            assertions=[
                NarrativeAssertion(
                    assertion_type="observation",
                    fact_ids=[identity],
                    relation=NarrativeRelation.AGGREGATE_RESULT,
                    presentation_order=1,
                    references=[
                        EvidenceReference(
                            fact_id=identity,
                            fact_version=fact["fact_version"],
                            evidence_id=evidence_id,
                            evidence_digest=bundle.evidence_digest,
                            source="factual-engine",
                        )
                        for evidence_id in bundle.authorized_evidence_ids(identity)
                    ],
                    template="observation_aggregate_result",
                )
            ],
        )
        GroundedNarrativeValidator(bundle).validate(plan)
        plans[identity] = plan
    return plans


def render_insight(plan: NarrativePlan, bundle: EvidenceBundle) -> str:
    """Valida evidências e pertença ao catálogo antes de usar o template local.

    O validador v1 verifica referências; a igualdade com o plano fechado
    verifica também cobertura e amostra, que v1 apenas limita numericamente.
    """
    GroundedNarrativeValidator(bundle).validate(plan)
    if len(plan.assertions) != 1:
        raise ValueError("Expected one catalog observation")
    identity = plan.assertions[0].fact_ids[0]
    expected = prepare_insight_plans(bundle).get(identity)
    if expected is None or plan != expected:
        raise ValueError("Plan does not match the closed insight catalog")
    return bundle[identity]["text"]
