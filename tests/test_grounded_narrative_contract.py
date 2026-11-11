"""Testes do contrato de interpretação fundamentada e do avaliador offline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from footballiq.analytics import FactualReport, analyze_recent_matches
from footballiq.grounded_narrative import (
    EvidenceBundle,
    EvidenceReference,
    GroundedNarrativeValidator,
    NarrativeAssertion,
    NarrativePlan,
    NarrativeRelation,
    NarrativeSchemaVersion,
    OfflineNarrativeEvaluator,
    build_available_facts,
    render_plan,
)

VALID_FACTS = {
    "fact:team:benfica": {
        "team": "Benfica",
        "value": 2.1,
        "fact_version": "v1",
        "snapshot_version": "snapshot-001",
    },
    "fact:team:porto": {
        "team": "Porto",
        "value": 1.8,
        "fact_version": "v1",
        "snapshot_version": "snapshot-001",
    },
    "fact:season:2024": {
        "season": "2024/25",
        "value": 1.95,
        "fact_version": "v1",
        "snapshot_version": "snapshot-001",
    },
    "fact:goal_diff:match-1": {
        "team": "Benfica",
        "value": 1,
        "fact_version": "v1",
        "snapshot_version": "snapshot-001",
    },
    "fact:goal_diff:match-2": {
        "team": "Benfica",
        "value": 3,
        "fact_version": "v1",
        "snapshot_version": "snapshot-001",
    },
}


def _references(bundle: EvidenceBundle, fact_id: str) -> list[EvidenceReference]:
    """Obtém todas as referências autorizadas pelo backend para um facto."""
    return [
        EvidenceReference(
            fact_id=fact_id,
            fact_version=bundle[fact_id]["fact_version"],
            evidence_id=evidence_id,
            evidence_digest=bundle.evidence_digest,
            source="factual-engine",
        )
        for evidence_id in bundle.authorized_evidence_ids(fact_id)
    ]


def _valid_plan() -> NarrativePlan:
    return NarrativePlan(
        schema_version=NarrativeSchemaVersion.V1,
        evidence_snapshot_id="snapshot-001",
        evidence_digest="digest-123",
        coverage=0.85,
        sample_size=12,
        assertions=[
            NarrativeAssertion(
                assertion_type="observation",
                fact_ids=["fact:season:2024"],
                relation=NarrativeRelation.AGGREGATE_RESULT,
                presentation_order=1,
                references=[
                    EvidenceReference(
                        fact_id="fact:season:2024",
                        fact_version="v1",
                        evidence_id=EvidenceBundle(
                            "snapshot-001", "digest-123", VALID_FACTS
                        ).authorized_evidence_ids("fact:season:2024")[0],
                        evidence_digest="digest-123",
                        source="factual-engine",
                    )
                ],
                template="observation_aggregate_result",
            ),
            NarrativeAssertion(
                assertion_type="descriptive_comparison",
                fact_ids=["fact:team:benfica", "fact:team:porto"],
                relation=NarrativeRelation.GREATER_THAN_OR_EQUAL,
                left_fact_id="fact:team:benfica",
                right_fact_id="fact:team:porto",
                comparison_operator="gte",
                presentation_order=2,
                references=[
                    EvidenceReference(
                        fact_id="fact:team:benfica",
                        fact_version="v1",
                        evidence_id=EvidenceBundle(
                            "snapshot-001", "digest-123", VALID_FACTS
                        ).authorized_evidence_ids("fact:team:benfica")[0],
                        evidence_digest="digest-123",
                        source="factual-engine",
                    ),
                    EvidenceReference(
                        fact_id="fact:team:porto",
                        fact_version="v1",
                        evidence_id=EvidenceBundle(
                            "snapshot-001", "digest-123", VALID_FACTS
                        ).authorized_evidence_ids("fact:team:porto")[0],
                        evidence_digest="digest-123",
                        source="factual-engine",
                    ),
                ],
                template="comparison_mean_ordered",
            ),
        ],
    )


def test_valid_plan_is_accepted() -> None:
    """Um plano de narrativa válido deve ser aceite pelo validador."""
    plan = _valid_plan()
    validator = GroundedNarrativeValidator(
        available_facts=EvidenceBundle(
            snapshot_id="snapshot-001",
            evidence_digest="digest-123",
            facts=VALID_FACTS,
        )
    )

    validated = validator.validate(plan)

    assert validated.schema_version == NarrativeSchemaVersion.V1
    assert len(validated.assertions) == 2


def test_evidence_bundle_is_deeply_immutable() -> None:
    """O bundle e os factos aninhados devem ser imutáveis em profundidade."""
    bundle = EvidenceBundle(
        snapshot_id="snapshot-001",
        evidence_digest="digest-123",
        facts={
            "fact:team:benfica": {
                "team": "Benfica",
                "value": 2.1,
                "references": ["ref-1", "ref-2"],
            }
        },
    )

    fact = bundle.facts["fact:team:benfica"]
    with pytest.raises(TypeError):
        fact["team"] = "Porto"
    with pytest.raises(TypeError):
        bundle.facts["fact:team:benfica"]["value"] = 99

    assert fact["team"] == "Benfica"
    assert fact["references"] == ("ref-1", "ref-2")


def test_mapping_fact_input_is_rejected_in_public_validator() -> None:
    """Mapeamentos genéricos de factos não são aceites na interface pública."""
    with pytest.raises(TypeError, match="EvidenceBundle|trusted|raw Mapping"):
        GroundedNarrativeValidator(
            available_facts={"fact:team:benfica": {"value": 2.1}}
        )


def test_unknown_schema_is_rejected() -> None:
    """Schemas desconhecidos devem ser recusados de imediato."""
    plan = _valid_plan().model_copy(update={"schema_version": "v99"})
    bundle = EvidenceBundle(
        snapshot_id="snapshot-001",
        evidence_digest="digest-123",
        facts=VALID_FACTS,
    )

    with pytest.raises(ValueError, match="schema_version"):
        GroundedNarrativeValidator(available_facts=bundle).validate(plan)


def test_duplicate_or_missing_fact_ids_are_rejected() -> None:
    """Factos duplicados, ausentes ou indisponíveis não são aceites."""
    plan = _valid_plan().model_copy(
        update={
            "assertions": [
                NarrativeAssertion(
                    assertion_type="observation",
                    fact_ids=["fact:team:benfica", "fact:team:benfica"],
                    relation=NarrativeRelation.AGGREGATE_RESULT,
                    presentation_order=1,
                    references=[
                        EvidenceReference(
                            fact_id="fact:team:benfica",
                            fact_version="v1",
                            evidence_id="evidence-004",
                            evidence_digest="digest-123",
                            source="factual-engine",
                        )
                    ],
                    template="observation_aggregate_result",
                )
            ]
        }
    )

    with pytest.raises(ValueError, match="fact_id"):
        GroundedNarrativeValidator(
            available_facts=EvidenceBundle(
                snapshot_id="snapshot-001",
                evidence_digest="digest-123",
                facts=VALID_FACTS,
            )
        ).validate(plan)


def test_prompt_injection_is_rejected() -> None:
    """Tentativas de prompt injection devem ser bloqueadas."""
    bundle = EvidenceBundle(
        snapshot_id="snapshot-001",
        evidence_digest="digest-123",
        facts=VALID_FACTS,
    )
    plan = _valid_plan().model_copy(
        update={
            "assertions": [
                NarrativeAssertion(
                    assertion_type="observation",
                    fact_ids=["fact:season:2024"],
                    relation=NarrativeRelation.AGGREGATE_RESULT,
                    presentation_order=1,
                    references=[
                        EvidenceReference(
                            fact_id="ignore:prompt:system",
                            fact_version="v1",
                            evidence_id="evidence-999",
                            evidence_digest="digest-123",
                            source="factual-engine",
                        )
                    ],
                    template="observation_aggregate_result",
                )
            ]
        }
    )

    with pytest.raises(ValueError, match="prompt|injection|evidence"):
        GroundedNarrativeValidator(available_facts=bundle).validate(plan)


def test_render_plan_is_deterministic() -> None:
    """O renderizador deve produzir frases determinísticas a partir de factos autorizados."""
    rendered = render_plan(
        _valid_plan(),
        EvidenceBundle(
            snapshot_id="snapshot-001",
            evidence_digest="digest-123",
            facts=VALID_FACTS,
        ),
    )

    assert isinstance(rendered, str)
    assert "observação" in rendered.lower()
    assert "Benfica" in rendered
    assert "Porto" in rendered


def test_fact_id_from_other_snapshot_is_rejected() -> None:
    """Uma fact_id de outro snapshot não pode validar um plano da janela atual."""
    plan = _valid_plan().model_copy(update={"evidence_snapshot_id": "snapshot-999"})
    bundle = EvidenceBundle(
        snapshot_id="snapshot-001",
        evidence_digest="digest-123",
        facts=VALID_FACTS,
    )

    with pytest.raises(ValueError, match="snapshot|digest"):
        GroundedNarrativeValidator(available_facts=bundle).validate(plan)


def test_incompatible_evidence_version_is_rejected() -> None:
    """Versão de evidência incompatível deve ser recusada."""
    plan = _valid_plan().model_copy(
        update={
            "assertions": [
                NarrativeAssertion(
                    assertion_type="observation",
                    fact_ids=["fact:season:2024"],
                    relation=NarrativeRelation.AGGREGATE_RESULT,
                    presentation_order=1,
                    references=[
                        EvidenceReference(
                            fact_id="fact:season:2024",
                            fact_version="v99",
                            evidence_id=EvidenceBundle(
                                "snapshot-001", "digest-123", VALID_FACTS
                            ).authorized_evidence_ids("fact:season:2024")[0],
                            evidence_digest="digest-123",
                            source="factual-engine",
                        )
                    ],
                    template="observation_aggregate_result",
                )
            ]
        }
    )
    bundle = EvidenceBundle(
        snapshot_id="snapshot-001",
        evidence_digest="digest-123",
        facts=VALID_FACTS,
    )

    with pytest.raises(ValueError, match="version|fact_version|incompatible"):
        GroundedNarrativeValidator(available_facts=bundle).validate(plan)


def test_fabricated_reference_is_rejected() -> None:
    """Referências criadas fora do motor factual não são aceites."""
    plan = _valid_plan().model_copy(
        update={
            "assertions": [
                NarrativeAssertion(
                    assertion_type="observation",
                    fact_ids=["fact:season:2024"],
                    relation=NarrativeRelation.AGGREGATE_RESULT,
                    presentation_order=1,
                    references=[
                        EvidenceReference(
                            fact_id="fact:season:2024",
                            fact_version="v1",
                            evidence_id="evidence-fake",
                            evidence_digest="digest-123",
                            source="llm",
                        )
                    ],
                    template="observation_aggregate_result",
                )
            ]
        }
    )

    with pytest.raises(ValueError, match="factual engine|source"):
        GroundedNarrativeValidator(
            available_facts=EvidenceBundle(
                snapshot_id="snapshot-001",
                evidence_digest="digest-123",
                facts=VALID_FACTS,
            )
        ).validate(plan)


def test_contradictory_coverage_is_rejected() -> None:
    """Cobertura nula ou contraditória deve ser rejeitada."""
    plan = _valid_plan().model_copy(update={"coverage": 0.0})
    with pytest.raises(ValueError, match="coverage"):
        GroundedNarrativeValidator(
            available_facts=EvidenceBundle(
                snapshot_id="snapshot-001",
                evidence_digest="digest-123",
                facts=VALID_FACTS,
            )
        ).validate(plan)


def test_unavailable_fact_is_rejected() -> None:
    """Factos indisponíveis ou ausentes nunca passam na validação semântica."""
    plan = _valid_plan().model_copy(
        update={
            "assertions": [
                NarrativeAssertion(
                    assertion_type="observation",
                    fact_ids=["fact:missing:team"],
                    relation=NarrativeRelation.AGGREGATE_RESULT,
                    presentation_order=1,
                    references=[
                        EvidenceReference(
                            fact_id="fact:missing:team",
                            fact_version="v1",
                            evidence_id="evidence-missing",
                            evidence_digest="digest-123",
                            source="factual-engine",
                        )
                    ],
                    template="observation_aggregate_result",
                )
            ]
        }
    )

    with pytest.raises(ValueError, match="missing from the available facts|fact_id"):
        GroundedNarrativeValidator(
            available_facts=EvidenceBundle(
                snapshot_id="snapshot-001",
                evidence_digest="digest-123",
                facts=VALID_FACTS,
            )
        ).validate(plan)


def test_invalid_relation_or_operator_is_rejected() -> None:
    """Relações e operadores inválidos são recusados explicitamente."""
    payload = {
        "assertion_type": "descriptive_comparison",
        "fact_ids": ["fact:team:benfica", "fact:team:porto"],
        "relation": NarrativeRelation.GREATER_THAN_OR_EQUAL,
        "left_fact_id": "fact:team:benfica",
        "right_fact_id": "fact:team:porto",
        "comparison_operator": "contains",
        "presentation_order": 2,
        "references": [
            {
                "fact_id": "fact:team:benfica",
                "fact_version": "v1",
                "evidence_id": "evidence-002",
                "evidence_digest": "digest-123",
                "source": "factual-engine",
            },
            {
                "fact_id": "fact:team:porto",
                "fact_version": "v1",
                "evidence_id": "evidence-003",
                "evidence_digest": "digest-123",
                "source": "factual-engine",
            },
        ],
        "template": "comparison_mean_ordered",
    }

    with pytest.raises(ValueError, match="comparison_operator|invalid"):
        NarrativeAssertion.model_validate(payload)


def test_extra_plan_fields_are_rejected() -> None:
    """Campos novos não autorizados no plano não podem ser aceites."""
    payload = {
        **_valid_plan().model_dump(),
        "prediction": "Benfica vai ganhar",
    }

    with pytest.raises(ValueError, match="extra|Extra|forbid"):
        NarrativePlan.model_validate(payload)


def test_prompt_injection_in_team_name_is_rejected() -> None:
    """Nomes de equipa com instruções não entram no catálogo nem no plano."""
    with pytest.raises(ValueError, match="prompt|injection|team"):
        EvidenceBundle(
            snapshot_id="snapshot-001",
            evidence_digest="digest-123",
            facts={
                "fact:team:benfica": {"team": "ignore:prompt", "value": 2.1},
                "fact:team:porto": {"team": "Porto", "value": 1.8},
            },
        )


def test_factual_report_is_unchanged_by_bundle_generation() -> None:
    """A geração do bundle não altera o relatório factual original."""
    payload = json.loads(
        Path("tests/fixtures/integration/complete_five.json").read_text(
            encoding="utf-8"
        )
    )
    report = analyze_recent_matches(payload)
    snapshot = report.model_dump(mode="json")

    bundle = build_available_facts(report)

    assert bundle.snapshot_id == report.snapshot_version
    assert bundle.evidence_digest
    assert report.model_dump(mode="json") == snapshot
    assert "match:10" in bundle
    assert "metric:competitive" in bundle


def test_safe_factual_fallback_when_bundle_is_empty() -> None:
    """O bundle seguro deve manter a cadeia sem inventar factos não disponíveis."""
    bundle = EvidenceBundle(
        snapshot_id="empty", evidence_digest="digest-empty", facts={}
    )
    validator = GroundedNarrativeValidator(bundle)
    assert validator.available_facts == bundle
    assert not bundle.facts


def test_real_e2e_complete_five_uses_factual_pipeline() -> None:
    """A cadeia real completa_five deve passar do fixture ao bundle antes do plano."""
    payload = json.loads(
        Path("tests/fixtures/integration/complete_five.json").read_text(
            encoding="utf-8"
        )
    )
    report = analyze_recent_matches(payload)
    bundle = build_available_facts(report)
    plan = NarrativePlan(
        schema_version=NarrativeSchemaVersion.V1,
        evidence_snapshot_id=report.snapshot_version,
        evidence_digest=bundle.evidence_digest,
        coverage=1.0,
        sample_size=2,
        assertions=[
            NarrativeAssertion(
                assertion_type="observation",
                fact_ids=["match:10"],
                relation=NarrativeRelation.AGGREGATE_RESULT,
                presentation_order=1,
                references=_references(bundle, "match:10"),
                template="observation_aggregate_result",
            )
        ],
    )

    validated = GroundedNarrativeValidator(bundle).validate(plan)
    rendered = render_plan(validated, bundle)
    assert validated.assertions[0].fact_ids == ["match:10"]
    assert "Observação" in rendered


def test_e2e_partial_match_and_empty_are_safe_rejections() -> None:
    """Fixtures parciais e vazias devem permanecer seguras e sem factos sintéticos."""
    for fixture in ("partial_match", "empty"):
        payload = json.loads(
            Path(f"tests/fixtures/integration/{fixture}.json").read_text(
                encoding="utf-8"
            )
        )
        report = analyze_recent_matches(payload)
        bundle = build_available_facts(report)
        assert isinstance(bundle, EvidenceBundle)
        assert bundle.snapshot_id == report.snapshot_version
        assert all(
            fact_id.startswith(("match:", "metric:", "trend:"))
            for fact_id in bundle.facts
        )


def test_offline_evaluator_accepts_valid_and_rejects_invalid() -> None:
    """O avaliador offline deve medir aceitação e rejeição com regras reprodutíveis."""
    bundle = EvidenceBundle(
        snapshot_id="snapshot-001",
        evidence_digest="digest-123",
        facts=VALID_FACTS,
    )
    evaluator = OfflineNarrativeEvaluator(available_facts=bundle)

    valid_plan = _valid_plan()
    invalid_plan = _valid_plan().model_copy(update={"evidence_digest": "digest-999"})

    report = evaluator.evaluate_corpus([valid_plan, invalid_plan])

    assert report["accepted_valid"] == 1
    assert report["rejected_invalid"] == 1
    assert report["acceptance_rate"] == 0.5
    assert report["adversarial_acceptance_rate"] == 0.0


def test_relation_must_match_fact_ids_and_operators() -> None:
    """Relações devem cumprir as pré-condições explícitas para não misturar factos."""
    plan = _valid_plan().model_copy(
        update={
            "assertions": [
                NarrativeAssertion(
                    assertion_type="descriptive_comparison",
                    fact_ids=["fact:season:2024"],
                    relation=NarrativeRelation.GREATER_THAN_OR_EQUAL,
                    left_fact_id="fact:season:2024",
                    right_fact_id="fact:team:porto",
                    comparison_operator="gte",
                    presentation_order=2,
                    references=[
                        EvidenceReference(
                            fact_id="fact:season:2024",
                            fact_version="v1",
                            evidence_id="evidence-005",
                            evidence_digest="digest-123",
                            source="factual-engine",
                        ),
                        EvidenceReference(
                            fact_id="fact:team:porto",
                            fact_version="v1",
                            evidence_id="evidence-006",
                            evidence_digest="digest-123",
                            source="factual-engine",
                        ),
                    ],
                    template="comparison_mean_ordered",
                )
            ]
        }
    )

    bundle = EvidenceBundle(
        snapshot_id="snapshot-001",
        evidence_digest="digest-123",
        facts=VALID_FACTS,
    )

    with pytest.raises(ValueError, match="pré-condição|relation|comparison"):
        GroundedNarrativeValidator(available_facts=bundle).validate(plan)


def test_real_factual_report_builds_grounded_catalog() -> None:
    """O contrato deve usar o catálogo factual real do pipeline, não apenas factos externos."""
    payload = json.loads(
        Path("tests/fixtures/integration/complete_five.json").read_text(
            encoding="utf-8"
        )
    )
    report = analyze_recent_matches(payload)
    catalog = build_available_facts(report)

    assert "match:10" in catalog
    assert "match:9" in catalog
    assert catalog["match:10"]["goals_for"] == 2
    assert catalog["metric:competitive"]["value"]["goals_for"] == 4

    first_id = "match:10"
    second_id = "metric:competitive"
    third_id = "trend:window"

    bundle = build_available_facts(report)
    plan = NarrativePlan(
        schema_version=NarrativeSchemaVersion.V1,
        evidence_snapshot_id=report.snapshot_version,
        evidence_digest=bundle.evidence_digest,
        coverage=1.0,
        sample_size=2,
        assertions=[
            NarrativeAssertion(
                assertion_type="observation",
                fact_ids=[first_id],
                relation=NarrativeRelation.AGGREGATE_RESULT,
                presentation_order=1,
                references=_references(bundle, first_id),
                template="observation_aggregate_result",
            ),
            NarrativeAssertion(
                assertion_type="descriptive_comparison",
                fact_ids=[second_id, third_id],
                relation=NarrativeRelation.GREATER_THAN_OR_EQUAL,
                left_fact_id=second_id,
                right_fact_id=third_id,
                comparison_operator="gte",
                presentation_order=2,
                references=_references(bundle, second_id)
                + _references(bundle, third_id),
                template="comparison_mean_ordered",
            ),
        ],
    )

    validated = GroundedNarrativeValidator(report).validate(plan)
    assert validated.assertions[0].fact_ids == [first_id]

    with pytest.raises(ValueError, match="missing from the available facts"):
        GroundedNarrativeValidator(report).validate(
            plan.model_copy(
                update={
                    "assertions": [
                        NarrativeAssertion(
                            assertion_type="observation",
                            fact_ids=["match:missing"],
                            relation=NarrativeRelation.AGGREGATE_RESULT,
                            presentation_order=1,
                            references=[
                                EvidenceReference(
                                    fact_id="match:missing",
                                    fact_version="v1",
                                    evidence_id="evidence-missing",
                                    evidence_digest="digest-123",
                                    source="factual-engine",
                                )
                            ],
                            template="observation_aggregate_result",
                        )
                    ]
                }
            )
        )


def test_invented_evidence_id_audit_regression() -> None:
    """O identificador inventado da auditoria falha mesmo com metadados válidos."""
    bundle = EvidenceBundle(
        snapshot_id="snapshot-001", evidence_digest="digest-123", facts=VALID_FACTS
    )
    payload = _valid_plan().model_dump()
    payload["assertions"][0]["references"][0]["evidence_id"] = (
        "invented-reference-FI009-audit"
    )
    plan = NarrativePlan.model_validate(payload)
    with pytest.raises(ValueError, match="evidence_id"):
        GroundedNarrativeValidator(bundle).validate(plan)
    with pytest.raises(ValueError, match="evidence_id"):
        render_plan(plan, bundle)


def _fixture_report(name: str = "complete_five") -> FactualReport:
    """Carrega apenas o relatório sintético usado nos testes offline."""
    return analyze_recent_matches(
        json.loads(Path(f"tests/fixtures/integration/{name}.json").read_text())
    )


def _backend_plan(bundle: EvidenceBundle, *fact_ids: str) -> NarrativePlan:
    """Constrói um plano pela API pública com referências emitidas pelo backend."""
    return NarrativePlan(
        schema_version="1.0",
        evidence_snapshot_id=bundle.snapshot_id,
        evidence_digest=bundle.evidence_digest,
        coverage=1.0,
        sample_size=len(fact_ids),
        assertions=[
            NarrativeAssertion(
                assertion_type="observation",
                fact_ids=[fact_id],
                relation=NarrativeRelation.AGGREGATE_RESULT,
                presentation_order=index,
                references=_references(bundle, fact_id),
                template="observation_aggregate_result",
            )
            for index, fact_id in enumerate(fact_ids, 1)
        ],
    )


def test_backend_evidence_id_is_valid() -> None:
    """A identidade canónica emitida pelo bundle é aceite e renderizada."""
    bundle = build_available_facts(_fixture_report())
    plan = _backend_plan(bundle, "match:10")
    assert GroundedNarrativeValidator(bundle).validate(plan) == plan
    text = render_plan(plan, bundle)
    assert all(eid in text for eid in bundle.authorized_evidence_ids("match:10"))


def test_evidence_id_from_another_fact_is_rejected() -> None:
    """Existir no bundle não autoriza usar a evidência noutro facto."""
    bundle = build_available_facts(_fixture_report())
    payload = _backend_plan(bundle, "match:10").model_dump()
    payload["assertions"][0]["references"][0]["evidence_id"] = (
        bundle.authorized_evidence_ids("match:9")[0]
    )
    with pytest.raises(ValueError, match="evidence_id"):
        GroundedNarrativeValidator(bundle).validate(
            NarrativePlan.model_validate(payload)
        )


def test_evidence_id_from_another_snapshot_is_rejected() -> None:
    """O mesmo jogo e versão não autorizam reutilização entre snapshots."""
    report = _fixture_report()
    bundle = build_available_facts(report)
    changed = report.model_dump(mode="json")
    changed["snapshot_version"] = "other-snapshot"
    other = build_available_facts(type(report).model_validate(changed))
    payload = _backend_plan(bundle, "match:10").model_dump()
    payload["assertions"][0]["references"][0]["evidence_id"] = (
        other.authorized_evidence_ids("match:10")[0]
    )
    with pytest.raises(ValueError, match="evidence_id"):
        GroundedNarrativeValidator(bundle).validate(
            NarrativePlan.model_validate(payload)
        )


def test_evidence_id_from_another_version_is_rejected() -> None:
    """Um ID antigo não passa mesmo que o plano declare a versão atual."""
    report = _fixture_report()
    bundle = build_available_facts(report)
    changed = report.model_dump(mode="json")
    changed["matches"][0]["reference"]["data_version"] = "other-version"
    other = build_available_facts(type(report).model_validate(changed))
    payload = _backend_plan(bundle, "match:10").model_dump()
    payload["assertions"][0]["references"][0]["evidence_id"] = (
        other.authorized_evidence_ids("match:10")[0]
    )
    with pytest.raises(ValueError, match="evidence_id"):
        GroundedNarrativeValidator(bundle).validate(
            NarrativePlan.model_validate(payload)
        )


def test_evidence_id_is_required() -> None:
    """Uma referência sem evidence_id não é representável no contrato público."""
    bundle = build_available_facts(_fixture_report())
    payload = _backend_plan(bundle, "match:10").model_dump()
    del payload["assertions"][0]["references"][0]["evidence_id"]
    with pytest.raises(ValueError, match="evidence_id"):
        NarrativePlan.model_validate(payload)


def test_duplicate_evidence_id_is_rejected() -> None:
    """Duplicar uma referência válida não aumenta a evidência disponível."""
    bundle = build_available_facts(_fixture_report())
    payload = _backend_plan(bundle, "match:10").model_dump()
    refs = payload["assertions"][0]["references"]
    refs.append(dict(refs[0]))
    with pytest.raises(ValueError, match="duplicate evidence_id"):
        GroundedNarrativeValidator(bundle).validate(
            NarrativePlan.model_validate(payload)
        )


def test_valid_fact_with_false_reference_is_rejected() -> None:
    """O facto real não legitima uma referência livre com formato plausível."""
    bundle = build_available_facts(_fixture_report())
    payload = _backend_plan(bundle, "match:10").model_dump()
    payload["assertions"][0]["references"][0]["evidence_id"] = "evidence:" + "0" * 64
    with pytest.raises(ValueError, match="evidence_id"):
        render_plan(NarrativePlan.model_validate(payload), bundle)


def test_missing_metric_evidence_is_rejected() -> None:
    """Uma métrica agregada exige todas as referências que contribuíram para ela."""
    bundle = build_available_facts(_fixture_report())
    payload = _backend_plan(bundle, "metric:competitive").model_dump()
    refs = payload["assertions"][0]["references"]
    assert len(refs) == 5
    refs.pop()
    with pytest.raises(ValueError, match="missing required evidence_id"):
        GroundedNarrativeValidator(bundle).validate(
            NarrativePlan.model_validate(payload)
        )


def test_missing_asserted_fact_reference_is_rejected() -> None:
    """Uma comparação não pode omitir as referências de um dos seus factos."""
    bundle = EvidenceBundle("snapshot-001", "digest-123", VALID_FACTS)
    payload = _valid_plan().model_dump()
    payload["assertions"][1]["references"].pop()
    with pytest.raises(ValueError, match="missing required evidence_id"):
        GroundedNarrativeValidator(bundle).validate(
            NarrativePlan.model_validate(payload)
        )


def test_unasserted_fact_reference_is_rejected() -> None:
    """Mesmo autorizada, uma referência alheia à afirmação é rejeitada."""
    bundle = build_available_facts(_fixture_report())
    payload = _backend_plan(bundle, "match:10").model_dump()
    payload["assertions"][0]["references"].extend(
        ref.model_dump() for ref in _references(bundle, "match:9")
    )
    with pytest.raises(ValueError, match="evidence_id"):
        GroundedNarrativeValidator(bundle).validate(
            NarrativePlan.model_validate(payload)
        )


def test_mixed_plan_is_rejected_before_rendering(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A segunda afirmação inválida impede até a renderização da primeira."""
    from footballiq.grounded_narrative import contract

    bundle = build_available_facts(_fixture_report())
    payload = _backend_plan(bundle, "match:10", "match:9").model_dump()
    payload["assertions"][1]["references"][0]["evidence_id"] = (
        "invented-reference-FI009-audit"
    )

    def unexpected_render(*args: object, **kwargs: object) -> None:
        pytest.fail("O renderer começou antes da validação integral")

    monkeypatch.setattr(contract, "_numeric_value_from_fact", unexpected_render)
    with pytest.raises(ValueError, match="evidence_id"):
        render_plan(NarrativePlan.model_validate(payload), bundle)


def test_rejection_preserves_factual_fallback() -> None:
    """O consumidor pode conservar o factual intacto quando o plano é rejeitado.

    O contrato não implementa um orquestrador de fallback: propaga ValueError.
    Este teste verifica a política do consumidor sem acrescentar outra API.
    """
    report = _fixture_report()
    before = report.model_dump(mode="json")
    bundle = build_available_facts(report)
    payload = _backend_plan(bundle, "match:10").model_dump()
    payload["assertions"][0]["references"][0]["evidence_id"] = (
        "invented-reference-FI009-audit"
    )
    with pytest.raises(ValueError, match="evidence_id"):
        render_plan(NarrativePlan.model_validate(payload), bundle)
    assert report.model_dump(mode="json") == before
    assert build_available_facts(report) == bundle
    # O fallback é o relatório factual original, sem texto parcial do plano.
    assert "invented-reference-FI009-audit" not in report.model_dump_json()


@pytest.mark.parametrize("scenario", ["complete_five", "partial_match", "empty"])
def test_offline_backend_evidence_pipeline(
    scenario: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Percorre o pipeline sintético sem permitir ligações de rede."""
    import socket

    from footballiq.trends import calculate_trends

    def forbidden_network(*args: object, **kwargs: object) -> None:
        pytest.fail("O pipeline offline tentou aceder à rede")

    monkeypatch.setattr(socket, "socket", forbidden_network)
    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    report = _fixture_report(scenario)
    before = report.model_dump(mode="json")
    trends = calculate_trends(report)
    bundle = build_available_facts(report, trends=trends)
    assert bundle == build_available_facts(report)
    if not report.matches:
        # Sem jogos não há plano admissível com amostra positiva: mantém-se
        # o factual vazio. Não se fabrica uma observação para forçar um render.
        with pytest.raises(ValueError, match="sample_size|assertions"):
            _backend_plan(bundle)
        assert not any(key.startswith("match:") for key in bundle)
    else:
        fid = f"match:{report.matches[0].reference.source_match_id}"
        plan = _backend_plan(bundle, fid)
        GroundedNarrativeValidator(bundle).validate(plan)
        text = render_plan(plan, bundle)
        assert text == render_plan(plan, bundle)
        assert text.split("Referência: ", 1)[1].removesuffix(".") == ", ".join(
            bundle.authorized_evidence_ids(fid)
        )
        with pytest.raises(TypeError):
            bundle[fid]["match"]["reference"]["data_version"] = "changed"
    assert report.model_dump(mode="json") == before


@pytest.mark.parametrize("missing", ["references", "empty_references"])
def test_assertion_requires_explicit_references(missing: str) -> None:
    """A API pública rejeita listas ausentes ou vazias antes de validar o plano."""
    bundle = build_available_facts(_fixture_report())
    payload = _backend_plan(bundle, "match:10").model_dump()
    if missing == "references":
        del payload["assertions"][0]["references"]
    else:
        payload["assertions"][0]["references"] = []
    with pytest.raises(ValueError, match="references"):
        NarrativePlan.model_validate(payload)
