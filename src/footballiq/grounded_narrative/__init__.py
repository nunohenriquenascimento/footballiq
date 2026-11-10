"""Contrato interno e avaliador offline para narrativa fundamentada."""

from .contract import (
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

__all__ = [
    "EvidenceBundle",
    "EvidenceReference",
    "GroundedNarrativeValidator",
    "NarrativeAssertion",
    "NarrativePlan",
    "NarrativeRelation",
    "NarrativeSchemaVersion",
    "OfflineNarrativeEvaluator",
    "build_available_facts",
    "render_plan",
]
