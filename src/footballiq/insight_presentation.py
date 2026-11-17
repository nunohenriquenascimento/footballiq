"""Adaptação offline de seleções fechadas, sem HTML ou transporte de modelos."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

from footballiq.analytics import FactualReport
from footballiq.grounded_narrative import multi_insights as selection
from footballiq.grounded_narrative.insights import build_insights, render_insight

_FORMAT_VERSION = "footballiq.insights.v1"
_LIMIT = "Descrição da janela exportada; não constitui previsão."
_SUBTOTAL = "Apenas subtotal dos jogos cobertos."
_ADAPTATION_ERRORS = (ValueError, TypeError, KeyError, AttributeError, RecursionError)
_MESSAGES = {
    "not_requested": "Não foi solicitada apresentação de insights.",
    "opt_in_required": "Os insights não foram solicitados.",
    "no_facts": "Sem jogos neste snapshot; não há observações para apresentar.",
    "no_eligible_insights": "A cobertura ou amostra não permite observações elegíveis.",
    "timeout": "A seleção excedeu o tempo de espera; o relatório factual está disponível.",
    "invalid_selection": "A seleção não pôde ser validada; não se apresentam observações.",
    "insufficient_diversity": "A seleção repete famílias; não se apresentam observações.",
    "invalid_plan": "Não foi possível verificar a seleção neste relatório.",
    "invalid_settings": "A configuração da seleção não é válida.",
    "connection_unavailable": "A seleção está indisponível; o relatório factual está disponível.",
    "model_not_found": "O modelo indicado não está disponível localmente.",
    "client_required": "A seleção não tem um cliente configurado.",
    "demo_only": "Os insights estão limitados à demonstração aprovada.",
    "unavailable": "Insights indisponíveis; o relatório factual está disponível.",
}


@dataclass(frozen=True, slots=True)
class EvidenceReferenceView:
    """Referência verificada de um plano, sem links ou texto fornecidos pelo cliente."""

    fact_id: str
    fact_version: str
    evidence_id: str
    evidence_digest: str
    source: str


@dataclass(frozen=True, slots=True)
class InsightCard:
    """Observação e metadados específicos, conservando o texto canónico integral."""

    ordinal: int
    plan_id: str
    family: str
    scope: str
    canonical_text: str
    display_text: str
    formatting_status: Literal["projected_v1", "canonical_fallback"]
    covered_matches: int
    selected_matches: int
    coverage: float
    sample_size: int
    subtotal_notice: str
    descriptive_limit: str
    fact_version: str
    formula_version: str
    match_refs: tuple[str, ...]
    match_versions: tuple[tuple[str, str], ...]
    match_event_ids: tuple[tuple[str, tuple[str, ...]], ...]
    evidence_refs: tuple[EvidenceReferenceView, ...]


@dataclass(frozen=True, slots=True)
class SharedProvenance:
    """Proveniência comum confirmada em todos os cartões, sem fundir fórmulas."""

    snapshot_id: str
    snapshot_version: str
    evidence_digest: str
    source: str
    schema_version: str
    catalog_version: str
    source_system: str
    source_instance_id: str
    descriptive_limit: str


@dataclass(frozen=True, slots=True)
class InsightsPresentation:
    """Resultado atómico da fronteira de apresentação; falhas não contêm cartões."""

    status: Literal["not_requested", "disabled", "unavailable", "available"]
    reason_code: str
    message: str
    items: tuple[InsightCard, ...] = ()
    provenance: SharedProvenance | None = None


def _unavailable(reason: str) -> InsightsPresentation:
    safe = reason if reason in _MESSAGES else "unavailable"
    return InsightsPresentation("unavailable", safe, _MESSAGES[safe])


def _project_text(
    canonical: str,
    version: str,
    covered: int,
    selected: int,
    snapshot: str,
    formula: str,
    versions: tuple[tuple[str, str], ...],
) -> tuple[str, Literal["projected_v1", "canonical_fallback"], str, str]:
    """Projeta apenas o sufixo v1 exato; qualquer outro formato fica integral."""
    subtotal = _SUBTOTAL if covered < selected else ""
    suffix = (
        f" Cobertura {covered}/{selected}; amostra {covered}."
        + (f" {subtotal}" if subtotal else "")
        + f" {_LIMIT}"
        + f" Snapshot {snapshot}; catálogo {_FORMAT_VERSION};"
        + f" fórmula {formula}; versões "
        + "; ".join(f"{identity}@{data_version}" for identity, data_version in versions)
        + "."
    )
    if version == _FORMAT_VERSION and canonical.endswith(suffix):
        body = canonical[: -len(suffix)]
        if body:
            return body, "projected_v1", subtotal, _LIMIT
    # Falha de formatação não é falha factual; nenhum carácter é removido.
    return canonical, "canonical_fallback", subtotal, ""


def prepare_insights_presentation(
    report: FactualReport, result: selection.InsightNarrativeResult | None
) -> InsightsPresentation:
    """Revalida toda a seleção contra um bundle atual, sem rede ou reparações.

    O bundle desta fronteira é independente do bundle interno da seleção.
    Os estados sem seleção não constroem evidências. Um dataclass available
    só é aceite após igualdade exata de texto, referências e proveniência.
    """
    if result is None:
        return InsightsPresentation(
            "not_requested", "not_requested", _MESSAGES["not_requested"]
        )
    if not isinstance(result, selection.InsightNarrativeResult):
        return _unavailable("invalid_plan")
    if result.status == "disabled":
        return InsightsPresentation(
            "disabled", "opt_in_required", _MESSAGES["opt_in_required"]
        )
    if result.status != "available":
        return _unavailable(result.reason if isinstance(result.reason, str) else "")
    if report.source_instance_id != "fictional-local-demo":
        return _unavailable("demo_only")
    if not report.matches:
        return _unavailable("no_facts")
    try:
        bundle = build_insights(report)
        shortlist = selection.prepare_insight_shortlist(bundle)
        if not shortlist:
            return _unavailable("no_eligible_insights")
        # Reutiliza a política real, incluindo diversidade; não mantém outro mapa.
        if not isinstance(result.plan_ids, tuple):
            return _unavailable("invalid_selection")
        identities = selection._validate_ids(list(result.plan_ids), shortlist)
        if (
            result.snapshot_id != bundle.snapshot_id
            or result.evidence_digest != bundle.evidence_digest
        ):
            return _unavailable("invalid_plan")
        cards: list[InsightCard] = []
        texts: list[str] = []
        references: list[str] = []
        common: list[SharedProvenance] = []
        for ordinal, identity in enumerate(identities, 1):
            plan = shortlist[identity]
            if len(plan.assertions) != 1 or plan.assertions[0].fact_ids != [identity]:
                return _unavailable("invalid_plan")
            canonical = render_insight(plan, bundle)
            fact = bundle[identity]
            resolved = tuple(
                bundle[ref]["match"]["reference"] if isinstance(ref, str) else ref
                for ref in fact["references"]
            )
            current = {m.reference.source_match_id: m.reference for m in report.matches}
            for ref in resolved:
                source_ref = current[ref["source_match_id"]]
                if (
                    ref["data_version"] != source_ref.data_version
                    or ref["source_system"] != source_ref.source_system
                    or ref["source_instance_id"] != source_ref.source_instance_id
                    or tuple(ref["event_ids"]) != tuple(source_ref.event_ids)
                ):
                    return _unavailable("invalid_plan")
            match_refs = tuple(f"match:{ref['source_match_id']}" for ref in resolved)
            versions = tuple(
                (
                    ref["source_match_id"],
                    ref["data_version"],
                )
                for ref in resolved
            )
            events = tuple(
                (ref["source_match_id"], tuple(ref["event_ids"])) for ref in resolved
            )
            display, formatting, subtotal, limit = _project_text(
                canonical,
                fact["fact_version"],
                fact["covered_matches"],
                fact["selected_matches"],
                fact["snapshot_version"],
                fact["formula_version"],
                versions,
            )
            evidence = tuple(
                EvidenceReferenceView(
                    ref.fact_id,
                    ref.fact_version,
                    ref.evidence_id,
                    ref.evidence_digest,
                    ref.source,
                )
                for ref in plan.assertions[0].references
            )
            family, scope = selection._TOPICS[identity]
            cards.append(
                InsightCard(
                    ordinal,
                    identity,
                    family,
                    scope,
                    canonical,
                    display,
                    formatting,
                    fact["covered_matches"],
                    fact["selected_matches"],
                    plan.coverage,
                    plan.sample_size,
                    subtotal,
                    limit,
                    fact["fact_version"],
                    fact["formula_version"],
                    match_refs,
                    versions,
                    events,
                    evidence,
                )
            )
            common.append(
                SharedProvenance(
                    bundle.snapshot_id,
                    fact["snapshot_version"],
                    bundle.evidence_digest,
                    bundle.source,
                    plan.schema_version.value,
                    fact["fact_version"],
                    fact["source_system"],
                    fact["source_instance_id"],
                    limit,
                )
            )
            texts.append(canonical)
            references.extend(ref.evidence_id for ref in evidence)
        if result.text != "\n".join(texts) or result.references != tuple(references):
            return _unavailable("invalid_plan")
        # Só agrega campos realmente iguais. O limite pode ficar por cartão
        # quando um formato futuro não o permitir verificar como campo comum.
        shared = common[0]
        if any(
            replace(entry, descriptive_limit="")
            != replace(shared, descriptive_limit="")
            for entry in common
        ):
            return _unavailable("invalid_plan")
        if any(entry.descriptive_limit != shared.descriptive_limit for entry in common):
            shared = replace(shared, descriptive_limit="")
        return InsightsPresentation(
            "available",
            "validated",
            "Seleção verificada no relatório atual.",
            tuple(cards),
            shared,
        )
    except selection._InvalidSelection as error:
        return _unavailable(str(error))
    except _ADAPTATION_ERRORS:
        return _unavailable("invalid_plan")
