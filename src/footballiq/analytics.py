"""Motor factual offline: funções puras, sem PostgreSQL, rede ou LLM.

O pacote já contém a janela selecionada pelo produtor. Este módulo verifica-a,
mas não consegue provar que foram exportados todos os jogos elegíveis na origem.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import model_validator

from footballiq.schemas.integration import (
    ContractModel,
    Count,
    ExportPackage,
    ExternalReference,
    IntegrationMatch,
    ScoreProvenance,
    Selection,
    SourceID,
    SourceReference,
    Text,
    Timestamp,
    credited_team_id,
)


class PointsPolicy(ContractModel):
    """Define pontos sem os apresentar implicitamente como regulamento oficial."""

    policy_id: Text
    win: Count
    draw: Count
    loss: Count
    is_official: bool
    reference: Text
    competition_id: SourceID | None

    @model_validator(mode="after")
    def validate_official_scope(self) -> PointsPolicy:
        """Uma política oficial tem de identificar a competição a que se aplica."""
        if self.is_official and self.competition_id is None:
            raise ValueError("Política oficial exige competition_id.")
        return self


class EvidenceReference(ContractModel):
    """Conserva identidade composta e versões sem confundir IDs entre projetos."""

    source_system: Literal["match_tracker"]
    source_instance_id: Text
    source_match_id: SourceID
    data_version: Text
    event_ids: list[SourceID]


class MissingCoverage(ContractModel):
    """Explica por que um jogo selecionado não contribui para uma métrica."""

    source_match_id: SourceID
    reason: Text


class MetricSummary(ContractModel):
    """Distingue totais da janela e subtotais com denominador explícito.

    values é null se a janela não está inteiramente coberta. covered_values
    conserva apenas o subtotal identificado, sem extrapolação para cinco jogos.
    """

    formula_version: Literal["footballiq.analytics.v1"] = "footballiq.analytics.v1"
    values: dict[str, int | float] | None
    covered_values: dict[str, int | float] | None
    covered_matches: Count
    selected_matches: Count
    references: list[EvidenceReference]
    missing: list[MissingCoverage]


class MatchFacts(ContractModel):
    """Lista os jogos realmente analisados e o resultado válido para cada um."""

    reference: EvidenceReference
    source_reference: SourceReference
    external_references: list[ExternalReference]
    kickoff_at: Timestamp
    opponent_id: SourceID
    opponent_name: Text
    is_home: bool
    score_status: Text
    score_provenance: ScoreProvenance
    goals_for: Count | None
    goals_against: Count | None
    outcome: Literal["win", "draw", "loss"] | None


class FactualReport(ContractModel):
    """Relatório reproduzível do snapshot; não certifica autorização ou atualidade."""

    report_version: Literal["1.0"] = "1.0"
    source_system: Literal["match_tracker"]
    source_instance_id: Text
    snapshot_version: Text
    exported_at: Timestamp
    selection: Selection
    declared_scope_id: Text
    authorization_verified: Literal[False] = False
    interpretation_status: Literal["not_requested"] = "not_requested"
    points_policy: PointsPolicy | None
    matches: list[MatchFacts]
    metrics: dict[str, MetricSummary]
    warnings: list[Text]


def validate_package(
    payload: str | bytes | Mapping[str, Any] | ExportPackage,
) -> ExportPackage:
    """Valida JSON/dicionário v1 sem ler ficheiros, autenticar ou abrir ligações.

    Revalida também instâncias, para não confiar em objetos alterados depois da
    primeira validação. A allowlist de instalações pertence à futura fronteira
    autenticada; este núcleo offline apenas preserva a identidade declarada.
    """
    if isinstance(payload, ExportPackage):
        payload = payload.model_dump(mode="json")
    if isinstance(payload, Mapping):
        return ExportPackage.model_validate(dict(payload))
    return ExportPackage.model_validate_json(payload)


def _reference(package: ExportPackage, match: IntegrationMatch) -> EvidenceReference:
    return EvidenceReference(
        source_system=package.source_system,
        source_instance_id=package.source_instance_id,
        source_match_id=match.source_match_id,
        data_version=match.data_version,
        event_ids=[event.source_event_id for event in match.events],
    )


def _competitive(match: IntegrationMatch) -> dict[str, int] | None:
    if match.score.status != "verified":
        return None
    gf, ga = match.score.home_goals, match.score.away_goals
    if match.team_id == match.away_team.team_id:
        gf, ga = ga, gf
    # O DTO garante que verified tem ambos os resultados preenchidos.
    assert gf is not None and ga is not None
    return {
        "wins": int(gf > ga),
        "draws": int(gf == ga),
        "losses": int(gf < ga),
        "goals_for": gf,
        "goals_against": ga,
        "goal_difference": gf - ga,
    }


def _events_metric(match: IntegrationMatch, category: str) -> dict[str, int]:
    fields = {
        "shots": {
            "SHOT_ON_TARGET": "on_target",
            "SHOT_OFF_TARGET": "off_target",
            "SHOT_BLOCKED": "blocked",
        },
        "cards": {"YELLOW_CARD": "yellow", "RED_CARD": "red"},
        "substitutions": {"SUBSTITUTION": "substitutions"},
    }[category]
    result = {
        f"{field}_{side}": 0 for field in fields.values() for side in ("for", "against")
    }
    for event in match.events:
        if event.event_type in fields:
            side = "for" if event.team_id == match.team_id else "against"
            result[f"{fields[event.event_type]}_{side}"] += 1
    if category == "shots":
        for side in ("for", "against"):
            result[f"total_{side}"] = sum(
                result[f"{field}_{side}"] for field in fields.values()
            )
    return result


def _temporal_goals(match: IntegrationMatch) -> dict[str, int]:
    intervals = ("00-14", "15-29", "30-44", "45-59", "60-74", "75-89", "90+")
    result = {
        f"period_{period}_{side}": 0 for period in (1, 2) for side in ("for", "against")
    }
    result.update(
        {
            f"minute_{interval}_{side}": 0
            for interval in intervals
            for side in ("for", "against")
        }
    )
    for event in match.events:
        if event.event_type in {"GOAL", "OWN_GOAL"}:
            credited = credited_team_id(
                event, match.home_team.team_id, match.away_team.team_id
            )
            side = "for" if credited == match.team_id else "against"
            result[f"period_{event.period}_{side}"] += 1
            result[f"minute_{intervals[min(event.minute // 15, 6)]}_{side}"] += 1
    return result


def _summary(
    package: ExportPackage,
    rows: list[tuple[IntegrationMatch, dict[str, int]]],
    missing: list[MissingCoverage],
    *,
    averages: bool = False,
) -> MetricSummary:
    values: dict[str, int | float] | None = None
    if rows:
        values = {key: sum(row[key] for _, row in rows) for key in rows[0][1]}
        if averages:
            for key in ("goals_for", "goals_against"):
                values[f"average_{key}"] = values[key] / len(rows)
    return MetricSummary(
        values=values if len(rows) == len(package.matches) else None,
        covered_values=values,
        covered_matches=len(rows),
        selected_matches=len(package.matches),
        references=[_reference(package, match) for match, _ in rows],
        missing=missing,
    )


def analyze_recent_matches(
    payload: str | bytes | Mapping[str, Any] | ExportPackage,
    *,
    points_policy: PointsPolicy | Mapping[str, Any] | None = None,
) -> FactualReport:
    """Calcula factos da janela validada, sem preencher falhas ou chamar um LLM.

    A política de pontos é explícita. Métricas incompletas conservam subtotal,
    cobertura e referências, mas o total da janela permanece null. As médias
    usam o número de resultados verificados, nunca o limite pretendido de cinco.
    """
    package = validate_package(payload)
    policy = None
    if points_policy is not None:
        raw_policy = (
            points_policy.model_dump()
            if isinstance(points_policy, PointsPolicy)
            else dict(points_policy)
        )
        policy = PointsPolicy.model_validate(raw_policy)
        if policy.competition_id is not None and (
            package.selection.competition_scope != "single"
            or package.selection.competition_id != policy.competition_id
        ):
            raise ValueError(
                "Política competitiva exige seleção single da mesma competição."
            )
    metrics = {}
    facts = []
    warnings = [
        "Modo offline: o scope declarado não prova autorização nem autenticidade.",
        "Snapshot exportado: não foi confirmada a atualidade na origem.",
    ]
    if len(package.matches) < 5:
        warnings.append(f"Apenas {len(package.matches)} de 5 jogos encontrados.")
    for category in (
        "competitive",
        "points",
        "shots",
        "cards",
        "substitutions",
        "temporal_goals",
    ):
        rows = []
        missing = []
        for match in package.matches:
            reason = None
            row = None
            if category in {"competitive", "points"}:
                row = _competitive(match)
                if row is None:
                    reason = f"Resultado {match.score.status}."
                elif category == "points":
                    if policy is None:
                        reason, row = "Política de pontos não fornecida.", None
                    else:
                        row = {
                            "points": row["wins"] * policy.win
                            + row["draws"] * policy.draw
                            + row["losses"] * policy.loss
                        }
            else:
                quality_name = (
                    "score_events" if category == "temporal_goals" else category
                )
                quality = getattr(match.quality, quality_name)
                if quality.status != "complete":
                    reason = f"{quality_name}: {quality.status}."
                else:
                    row = (
                        _temporal_goals(match)
                        if category == "temporal_goals"
                        else _events_metric(match, category)
                    )
            if row is not None:
                rows.append((match, row))
            else:
                missing.append(
                    MissingCoverage(
                        source_match_id=match.source_match_id,
                        reason=reason or "Dados indisponíveis.",
                    )
                )
        metrics[category] = _summary(
            package, rows, missing, averages=category == "competitive"
        )
        if missing:
            warnings.append(
                f"{category}: cobertura {len(rows)}/{len(package.matches)}; total da janela indisponível."
            )
    if policy is None:
        warnings.append("Pontos indisponíveis: não foi fornecida uma política.")
    elif not policy.is_official:
        warnings.append(
            "Pontos segundo convenção analítica; não representam classificação oficial."
        )
    for match in package.matches:
        result = _competitive(match)
        is_home = match.team_id == match.home_team.team_id
        opponent = match.away_team if is_home else match.home_team
        outcome = None
        if result is not None:
            outcome = "win" if result["wins"] else "draw" if result["draws"] else "loss"
        facts.append(
            MatchFacts(
                reference=_reference(package, match),
                source_reference=match.source_reference,
                external_references=match.external_references,
                kickoff_at=match.kickoff_at,
                opponent_id=opponent.team_id,
                opponent_name=opponent.name,
                is_home=is_home,
                score_status=match.score.status,
                score_provenance=match.score.provenance,
                goals_for=result["goals_for"] if result else None,
                goals_against=result["goals_against"] if result else None,
                outcome=outcome,
            )
        )
    return FactualReport(
        source_system=package.source_system,
        source_instance_id=package.source_instance_id,
        snapshot_version=package.snapshot_version,
        exported_at=package.exported_at,
        selection=package.selection,
        declared_scope_id=package.authorized_scope.scope_id,
        points_policy=policy,
        matches=facts,
        metrics=metrics,
        warnings=warnings,
    )


def report_json(report: FactualReport) -> str:
    """Serializa o relatório de forma estável, sem relógio global nem escrita."""
    return json.dumps(
        report.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, indent=2
    )
