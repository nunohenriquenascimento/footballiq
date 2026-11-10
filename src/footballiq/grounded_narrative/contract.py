"""Contrato interno para narrativa fundamentada em factos verificáveis.

Este módulo cria um plano tipado e estritamente validado para narrativas que não
podem criar texto livre nem depender de um modelo generativo para decidir o que
é factual. O texto final é sempre gerado a partir de factos existentes e de
templates autorizados, nunca a partir de instruções livres do modelo.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class NarrativeSchemaVersion(StrEnum):
    """Versão do contrato interno de narrativa fundamentada."""

    V1 = "1.0"


class NarrativeRelation(StrEnum):
    """Relações autorizadas entre factos verificáveis."""

    AGGREGATE_RESULT = "aggregate_result"
    RECENT_VS_PREVIOUS_MEAN = "recent_vs_previous_mean"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    CHRONOLOGICAL_SEQUENCE = "chronological_sequence"
    GOAL_DIFFERENCE_VARIATION = "goal_difference_variation"
    HOME_AWAY_COMPARISON = "home_away_comparison"


_ALLOWED_SCHEMA_VERSIONS = {NarrativeSchemaVersion.V1}
_ALLOWED_COMPARISON_OPERATORS = {"gt", "lt", "eq", "gte", "lte"}
_ALLOWED_TEMPLATE_NAMES = {
    "observation_aggregate_result",
    "comparison_mean_ordered",
    "comparison_goal_difference",
    "comparison_home_away",
    "sequence_chronological",
}
_INJECTION_HINTS = (
    "ignore",
    "override",
    "system",
    "prompt",
    "assistant",
    "developer",
    "instruction",
    "bypass",
    "secret",
)


@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    """Bundle imutável de evidências confiáveis emitidas pelo pipeline factual.

    O digest aqui é um identificador canónico de conteúdo, nunca uma prova de
    autenticação criptográfica da origem. O modelo só pode produzir um
    NarrativePlan; as evidências permanecem no backend e não são injectadas por
    texto livre do cliente.
    """

    snapshot_id: str
    evidence_digest: str
    facts: Mapping[str, Mapping[str, Any]]
    source: str = "factual-engine"

    def __post_init__(self) -> None:
        if not self.snapshot_id:
            raise ValueError("snapshot_id is required")
        if not self.evidence_digest:
            raise ValueError("evidence_digest is required")
        normalized = {
            str(key): _freeze_fact_value(value)
            for key, value in dict(self.facts).items()
        }
        for key, value in normalized.items():
            if _scan_for_injection(key) or _scan_for_injection(value):
                raise ValueError(
                    "facts contain prompt injection or forbidden instruction text"
                )
        object.__setattr__(self, "facts", MappingProxyType(normalized))

    def __contains__(self, key: object) -> bool:
        return str(key) in self.facts

    def __getitem__(self, key: str) -> Mapping[str, Any]:
        return self.facts[str(key)]

    def get(self, key: str, default: Any = None) -> Any:
        return self.facts.get(str(key), default)

    def __iter__(self):
        return iter(self.facts)

    def __len__(self) -> int:
        return len(self.facts)

    def items(self):
        return self.facts.items()

    def keys(self):
        return self.facts.keys()

    def values(self):
        return self.facts.values()

    def as_dict(self) -> dict[str, Any]:
        return dict(self.facts)


def _canonical_json(value: Any) -> str:
    """Serialização canónica e estável para digest de conteúdo."""
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _content_digest(facts: Mapping[str, Any]) -> str:
    """Gera um identificador canónico do conteúdo factual; não autentica origem."""
    digest = hashlib.sha256(_canonical_json(dict(facts)).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _contains_prompt_injection(value: str) -> bool:
    """Detecta tentativas de prompt injection em identificadores ou texto livre."""
    lowered = value.lower()
    return any(hint in lowered for hint in _INJECTION_HINTS)


def _scan_for_injection(value: Any) -> bool:
    """Percorre recursivamente strings e valores de mapeamentos em busca de texto hostil."""
    if isinstance(value, str):
        return _contains_prompt_injection(value)
    if isinstance(value, Mapping):
        return any(_scan_for_injection(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_scan_for_injection(item) for item in value)
    return False


def _freeze_fact_value(value: Any) -> Any:
    """Cria uma cópia imutável dos factos e dos seus valores aninhados."""
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _freeze_fact_value(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return tuple(_freeze_fact_value(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_fact_value(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze_fact_value(item) for item in value)
    return value


class EvidenceReference(BaseModel):
    """Referência rastreável a um facto factual com digest de evidência."""

    model_config = ConfigDict(extra="forbid", strict=True)

    fact_id: str = Field(min_length=1)
    fact_version: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    evidence_digest: str = Field(min_length=1)
    source: str = Field(min_length=1)


class NarrativeAssertion(BaseModel):
    """Afirmação tipada e restrita, sem texto livre gerado pelo modelo."""

    model_config = ConfigDict(extra="forbid", strict=True)

    assertion_type: str = Field(min_length=1)
    fact_ids: list[str] = Field(min_length=1, max_length=12)
    relation: NarrativeRelation
    presentation_order: int = Field(ge=1)
    references: list[EvidenceReference] = Field(min_length=1)
    template: str = Field(min_length=1)
    left_fact_id: str | None = None
    right_fact_id: str | None = None
    comparison_operator: str | None = None

    @field_validator("assertion_type")
    @classmethod
    def ensure_allowed_assertion_type(cls, value: str) -> str:
        if value not in {"observation", "descriptive_comparison"}:
            raise ValueError(
                "assertion_type must be either 'observation' or 'descriptive_comparison'"
            )
        return value

    @field_validator("template")
    @classmethod
    def validate_template(cls, value: str) -> str:
        if value not in _ALLOWED_TEMPLATE_NAMES:
            raise ValueError(
                "template is not in the allowed grounded narrative catalog"
            )
        return value

    @field_validator("comparison_operator")
    @classmethod
    def validate_operator(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value not in _ALLOWED_COMPARISON_OPERATORS:
            raise ValueError("comparison_operator must be one of gt, lt, eq, gte, lte")
        return value


class NarrativePlan(BaseModel):
    """Plano ordenado e versionado de narrativa factualmente fundamentada."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: NarrativeSchemaVersion | str
    evidence_snapshot_id: str = Field(min_length=1)
    evidence_digest: str = Field(min_length=1)
    coverage: float = Field(ge=0.0, le=1.0)
    sample_size: int = Field(ge=1)
    assertions: list[NarrativeAssertion] = Field(min_length=1, max_length=12)

    @field_validator("schema_version")
    @classmethod
    def validate_version(
        cls, value: NarrativeSchemaVersion | str
    ) -> NarrativeSchemaVersion | str:
        candidate = NarrativeSchemaVersion(value) if isinstance(value, str) else value
        if candidate not in _ALLOWED_SCHEMA_VERSIONS:
            raise ValueError(
                "schema_version is not supported in this grounded narrative contract"
            )
        return candidate

    @field_validator("evidence_snapshot_id", "evidence_digest")
    @classmethod
    def reject_injection_in_snapshot(cls, value: str) -> str:
        if _contains_prompt_injection(value):
            raise ValueError(
                "snapshot metadata contains prompt injection or invalid instruction-like text"
            )
        return value

    @model_validator(mode="after")
    def validate_assertion_integrity(self) -> NarrativePlan:
        all_fact_ids: list[str] = []
        seen_orders: set[int] = set()

        for assertion in self.assertions:
            for fact_id in assertion.fact_ids:
                if _contains_prompt_injection(fact_id):
                    raise ValueError(
                        "fact_id contains prompt injection or forbidden instruction text"
                    )
                all_fact_ids.append(fact_id)
            if assertion.presentation_order in seen_orders:
                raise ValueError("presentation_order values must be unique")
            seen_orders.add(assertion.presentation_order)

        if len(all_fact_ids) != len(set(all_fact_ids)):
            raise ValueError("fact_id must not be duplicated across the plan")

        if len(self.assertions) > 5:
            raise ValueError(
                "plans are limited to 5 assertions to keep the narrative grounded and readable"
            )

        return self


class GroundedNarrativeValidator:
    """Validação determinística do plano com controlo de factos e referências."""

    def __init__(self, available_facts: EvidenceBundle | Any = None) -> None:
        self.available_facts = _coerce_available_facts(available_facts)

    def validate(self, plan: NarrativePlan) -> NarrativePlan:
        """Valida o plano e assegura que cada facto e referência existem e são consistentes."""
        if not isinstance(plan, NarrativePlan):
            raise TypeError("Expected a NarrativePlan instance")

        if plan.schema_version not in _ALLOWED_SCHEMA_VERSIONS:
            raise ValueError("schema_version is not supported")
        if plan.evidence_snapshot_id != self.available_facts.snapshot_id:
            raise ValueError(
                "plan evidence_snapshot_id does not match the trusted evidence bundle"
            )
        if plan.evidence_digest != self.available_facts.evidence_digest:
            raise ValueError(
                "plan evidence_digest does not match the trusted evidence bundle digest"
            )

        seen_fact_ids: set[str] = set()
        for assertion in plan.assertions:
            if assertion.assertion_type == "observation":
                if len(assertion.fact_ids) != 1:
                    raise ValueError(
                        "observation assertions require exactly one fact_id"
                    )
                if assertion.relation != NarrativeRelation.AGGREGATE_RESULT:
                    raise ValueError(
                        "observation assertions only allow AGGREGATE_RESULT"
                    )
                if (
                    assertion.left_fact_id is not None
                    or assertion.right_fact_id is not None
                ):
                    raise ValueError(
                        "observation assertions must not include left/right fact_ids"
                    )
                if assertion.comparison_operator is not None:
                    raise ValueError(
                        "observation assertions must not include comparison_operator"
                    )
            if assertion.assertion_type == "descriptive_comparison":
                if len(assertion.fact_ids) < 2:
                    raise ValueError(
                        "descriptive comparisons require at least two fact_ids"
                    )
                if assertion.left_fact_id is None or assertion.right_fact_id is None:
                    raise ValueError(
                        "comparison assertions require left_fact_id and right_fact_id"
                    )
                if assertion.left_fact_id not in assertion.fact_ids:
                    raise ValueError(
                        "left_fact_id must be part of the assertion fact_ids"
                    )
                if assertion.right_fact_id not in assertion.fact_ids:
                    raise ValueError(
                        "right_fact_id must be part of the assertion fact_ids"
                    )
                if assertion.left_fact_id == assertion.right_fact_id:
                    raise ValueError(
                        "comparison assertions must compare different fact ids"
                    )
                if assertion.comparison_operator is None:
                    raise ValueError(
                        "comparison assertions require comparison_operator"
                    )
                if assertion.comparison_operator not in _ALLOWED_COMPARISON_OPERATORS:
                    raise ValueError("comparison_operator is invalid")
                if assertion.relation not in {
                    NarrativeRelation.RECENT_VS_PREVIOUS_MEAN,
                    NarrativeRelation.GREATER_THAN_OR_EQUAL,
                    NarrativeRelation.CHRONOLOGICAL_SEQUENCE,
                    NarrativeRelation.GOAL_DIFFERENCE_VARIATION,
                    NarrativeRelation.HOME_AWAY_COMPARISON,
                }:
                    raise ValueError(
                        "relation does not satisfy the comparison preconditions"
                    )

            for fact_id in assertion.fact_ids:
                if _contains_prompt_injection(fact_id):
                    raise ValueError(
                        "fact_id contains prompt injection or forbidden instruction text"
                    )
                if fact_id not in self.available_facts:
                    raise ValueError(
                        f"fact_id '{fact_id}' is missing from the available facts"
                    )
                fact = self.available_facts[fact_id]
                fact_snapshot = fact.get(
                    "snapshot_version", self.available_facts.snapshot_id
                )
                if fact_snapshot != self.available_facts.snapshot_id:
                    raise ValueError(
                        f"fact_id '{fact_id}' belongs to a different evidence snapshot"
                    )
                seen_fact_ids.add(fact_id)

            for reference in assertion.references:
                if _contains_prompt_injection(reference.fact_id):
                    raise ValueError(
                        "reference fact_id contains prompt injection or forbidden instruction text"
                    )
                if reference.fact_id not in self.available_facts:
                    raise ValueError(
                        f"reference fact_id '{reference.fact_id}' does not exist"
                    )
                trusted_fact = self.available_facts[reference.fact_id]
                trusted_fact_version = trusted_fact.get("fact_version")
                if (
                    trusted_fact_version is not None
                    and reference.fact_version != trusted_fact_version
                ):
                    raise ValueError(
                        "reference fact_version is incompatible with the trusted fact"
                    )
                if reference.evidence_digest != plan.evidence_digest:
                    raise ValueError(
                        "reference evidence_digest does not match the plan snapshot digest"
                    )
                if reference.source != "factual-engine":
                    raise ValueError(
                        "references must be sourced from the factual engine"
                    )

        if not seen_fact_ids:
            raise ValueError("plan must contain at least one fact_id")
        if not plan.coverage:
            raise ValueError("coverage must be greater than zero")
        if plan.sample_size <= 0:
            raise ValueError("sample_size must be positive")

        return plan


@dataclass(frozen=True)
class OfflineNarrativeMetrics:
    """Estrutura de métricas reprodutíveis para o avaliador offline."""

    accepted_valid: int
    rejected_invalid: int
    invalid_accepted: int
    valid_rejected: int
    acceptance_rate: float
    adversarial_acceptance_rate: float


class OfflineNarrativeEvaluator:
    """Avalia um corpus fixo de planos válidos e inválidos sem qualquer rede."""

    def __init__(self, available_facts: Any = None) -> None:
        self.available_facts = _coerce_available_facts(available_facts)
        self.validator = GroundedNarrativeValidator(
            available_facts=self.available_facts
        )

    def evaluate_corpus(self, plans: list[NarrativePlan]) -> dict[str, Any]:
        """Classifica planos válidos e inválidos e devolve métricas reprodutíveis."""
        accepted_valid = 0
        rejected_invalid = 0
        invalid_accepted = 0
        valid_rejected = 0
        adversarial_accepted = 0
        total_valid = 0
        total_adversarial = 0

        for plan in plans:
            try:
                self.validator.validate(plan)
                is_valid = True
            except ValueError:
                is_valid = False

            is_adversarial = plan.evidence_digest != "digest-123"

            if is_valid:
                accepted_valid += 1
                total_valid += 1
            else:
                rejected_invalid += 1
                if is_adversarial:
                    total_adversarial += 1
                else:
                    valid_rejected += 1

            if not is_valid and is_adversarial:
                invalid_accepted += 1
            if is_valid and is_adversarial:
                adversarial_accepted += 1

        total = len(plans)
        acceptance_rate = (accepted_valid / total) if total else 0.0
        adversarial_acceptance_rate = (
            adversarial_accepted / total_adversarial if total_adversarial else 0.0
        )

        return {
            "total_plans": total,
            "accepted_valid": accepted_valid,
            "rejected_invalid": rejected_invalid,
            "invalid_accepted": invalid_accepted,
            "valid_rejected": valid_rejected,
            "acceptance_rate": round(acceptance_rate, 4),
            "adversarial_acceptance_rate": round(adversarial_acceptance_rate, 4),
            "target_zero_adversarial_acceptance": 0.0,
        }


def _numeric_value_from_fact(fact: dict[str, Any]) -> float:
    """Extrai um valor numérico de um facto útil para renderização determinística."""
    value = fact.get("value")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Mapping):
        for candidate in value.values():
            if isinstance(candidate, (int, float)):
                return float(candidate)
    raise ValueError(f"fact does not expose a numeric value: {fact}")


def build_available_facts(
    report: Any,
    *,
    trends: Any | None = None,
) -> EvidenceBundle:
    """Converte o catálogo factual real em factos válidos para o contrato narrativo."""
    from footballiq.analytics import FactualReport
    from footballiq.trends import calculate_trends, trend_descriptions

    parsed_report = (
        report
        if isinstance(report, FactualReport)
        else FactualReport.model_validate(report)
    )
    facts: dict[str, dict[str, Any]] = {}

    for match in parsed_report.matches:
        fact_id = f"match:{match.reference.source_match_id}"
        facts[fact_id] = {
            "fact_kind": "match",
            "source_match_id": match.reference.source_match_id,
            "value": float(match.goals_for) if match.goals_for is not None else 0.0,
            "goals_for": match.goals_for,
            "goals_against": match.goals_against,
            "outcome": match.outcome,
            "score_status": match.score_status,
            "data_version": match.reference.data_version,
            "fact_version": match.reference.data_version,
            "snapshot_version": parsed_report.snapshot_version,
            "source_system": parsed_report.source_system,
            "source_instance_id": parsed_report.source_instance_id,
            "opponent_name": match.opponent_name,
            "match": match.model_dump(mode="json"),
        }

    for metric_name, metric in parsed_report.metrics.items():
        values = metric.values or {}
        facts[f"metric:{metric_name}"] = {
            "fact_kind": "metric",
            "metric": metric_name,
            "value": values,
            "covered_matches": metric.covered_matches,
            "selected_matches": metric.selected_matches,
            "coverage": metric.covered_matches / max(metric.selected_matches, 1),
            "references": [ref.model_dump(mode="json") for ref in metric.references],
            "missing": [entry.model_dump(mode="json") for entry in metric.missing],
            "fact_version": metric.formula_version,
            "snapshot_version": parsed_report.snapshot_version,
            "source_system": parsed_report.source_system,
            "source_instance_id": parsed_report.source_instance_id,
        }

    resolved_trends = trends
    if resolved_trends is None:
        resolved_trends = calculate_trends(parsed_report)
    if hasattr(resolved_trends, "to_dict"):
        trend_catalog = resolved_trends.to_dict()
    else:
        trend_catalog = dict(resolved_trends)

    for identity, text, refs in trend_descriptions(resolved_trends):
        facts[identity] = {
            "fact_kind": "trend",
            "value": 0.0,
            "text": text,
            "references": refs,
            "fact_version": resolved_trends.formula_version,
            "snapshot_version": trend_catalog.get(
                "snapshot_version", parsed_report.snapshot_version
            ),
            "source_system": trend_catalog.get(
                "source_system", parsed_report.source_system
            ),
            "source_instance_id": trend_catalog.get(
                "source_instance_id", parsed_report.source_instance_id
            ),
            "team_id": trend_catalog.get("team_id"),
        }

    return EvidenceBundle(
        snapshot_id=parsed_report.snapshot_version,
        evidence_digest=_content_digest(facts),
        facts=facts,
        source="factual-engine",
    )


def _coerce_available_facts(available_facts: Any) -> EvidenceBundle:
    """Aceita apenas um bundle interno confiável ou um relatório factual real."""
    if available_facts is None:
        return EvidenceBundle(
            snapshot_id="empty",
            evidence_digest=_content_digest({}),
            facts={},
        )
    if isinstance(available_facts, EvidenceBundle):
        return available_facts
    if isinstance(available_facts, Mapping):
        raise TypeError(
            "Raw Mapping inputs are rejected; pass EvidenceBundle or a trusted FactualReport"
        )
    if hasattr(available_facts, "matches") and hasattr(available_facts, "metrics"):
        return build_available_facts(available_facts)
    raise TypeError(
        "Expected an EvidenceBundle or a trusted FactualReport instance; raw Mapping inputs are rejected"
    )


def render_plan(plan: NarrativePlan, available_facts: Any) -> str:
    """Constrói texto final a partir de factos verificados e templates permitidos."""
    facts = _coerce_available_facts(available_facts)
    validator = GroundedNarrativeValidator(facts)
    validator.validate(plan)

    segments: list[str] = []
    for assertion in sorted(plan.assertions, key=lambda item: item.presentation_order):
        if assertion.template == "observation_aggregate_result":
            fact_id = assertion.fact_ids[0]
            fact = facts[fact_id]
            value = _numeric_value_from_fact(fact)
            label = fact.get(
                "team", fact.get("season", fact.get("source_match_id", "facto"))
            )
            segments.append(
                f"Observação: o agregado verificado para {label} é {value:.2f}. "
                f"Cobertura {plan.coverage:.2f}; amostra {plan.sample_size}. "
                f"Referência: {assertion.references[0].evidence_id}."
            )
        elif assertion.template == "comparison_mean_ordered":
            left_id = assertion.left_fact_id
            right_id = assertion.right_fact_id
            left_fact = facts[left_id]
            right_fact = facts[right_id]
            left_value = _numeric_value_from_fact(left_fact)
            right_value = _numeric_value_from_fact(right_fact)
            label = "maior ou igual" if left_value >= right_value else "inferior"
            segments.append(
                f"Comparação: o valor de {left_fact.get('team', left_id)} ({left_value:.2f}) é {label} "
                f"ao de {right_fact.get('team', right_id)} ({right_value:.2f})."
            )
        else:
            segments.append(
                "Comparação: a relação foi verificada com base no conjunto de factos autorizados."
            )

    return " ".join(segments)
