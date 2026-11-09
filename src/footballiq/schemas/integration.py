"""DTOs estritos do contrato Match Tracker v1, independentes de ORM e autorização.

Validar um ficheiro prova apenas coerência estrutural: não autentica a origem
nem certifica a completude declarada pelo produtor.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)


def _canonical_id(value: str) -> str:
    if re.fullmatch(r"[1-9][0-9]*", value) is None:
        raise ValueError("O ID deve ser uma string decimal positiva canónica.")
    return value


def _aware_timestamp(value: object) -> datetime:
    if isinstance(value, str):
        if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", value) is None:
            raise ValueError("O instante deve usar ISO 8601 com segundos e offset.")
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("O instante exige timezone explícito.")
    return value.astimezone(UTC)


SourceID = Annotated[str, AfterValidator(_canonical_id)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Count = Annotated[int, Field(ge=0)]
Timestamp = Annotated[datetime, BeforeValidator(_aware_timestamp)]
EventType = Literal[
    "GOAL",
    "OWN_GOAL",
    "SHOT_ON_TARGET",
    "SHOT_OFF_TARGET",
    "SHOT_BLOCKED",
    "CORNER",
    "FREE_KICK",
    "FOUL",
    "YELLOW_CARD",
    "RED_CARD",
    "OFFSIDE",
    "SUBSTITUTION",
    "PENALTY",
    "SAVE",
]


class ContractModel(BaseModel):
    """Rejeita coerções e campos desconhecidos em todos os objetos aninhados."""

    model_config = ConfigDict(
        extra="forbid", strict=True, revalidate_instances="always"
    )


class AuthorizedScope(ContractModel):
    """Transporta o âmbito declarado; não constitui uma credencial de acesso."""

    scope_id: Text
    club_id: Text
    team_id: SourceID
    permission: Literal["matches:export"]


class Selection(ContractModel):
    """Descreve filtros explícitos e ordem da janela já selecionada na origem."""

    team_id: SourceID
    season_id: SourceID
    competition_scope: Literal["all", "single"]
    competition_id: SourceID | None
    as_of: Timestamp
    limit: Annotated[int, Field(ge=5, le=5)]
    returned_count: Annotated[int, Field(ge=0, le=5)]
    order: Literal["kickoff_at_desc_source_match_id_numeric_desc"]

    @model_validator(mode="after")
    def validate_competition(self) -> Selection:
        """Exige uma competição apenas no âmbito single."""
        if (self.competition_scope == "single") != (self.competition_id is not None):
            raise ValueError("competition_id deve estar preenchido apenas em single.")
        return self


class TeamReference(ContractModel):
    """Identifica uma equipa na instalação de origem, sem deduplicar por nome."""

    team_id: SourceID
    name: Text


class PlayerReference(TeamReference):
    """Identifica uma inscrição por equipa e época, não uma pessoa universal."""

    source_player_id: SourceID
    season_id: SourceID


class ScoreProvenance(ContractModel):
    """Explica como o resultado foi obtido e onde pode ser verificado."""

    method: Literal["events", "official_capture", "manual_verified", "unknown"]
    reference_ids: list[Text]
    verified_at: Timestamp | None


class Score(ContractModel):
    """Distingue golos conhecidos de um resultado apto para cálculo competitivo."""

    home_goals: Count | None
    away_goals: Count | None
    status: Literal["verified", "unverified", "conflict", "unavailable"]
    provenance: ScoreProvenance

    @model_validator(mode="after")
    def validate_verification(self) -> Score:
        """Não aceita um resultado verificado sem valores e proveniência."""
        if (self.home_goals is None) != (self.away_goals is None):
            raise ValueError("Os dois golos devem ser preenchidos ou null em conjunto.")
        if self.status == "unavailable" and self.home_goals is not None:
            raise ValueError("Resultado unavailable não pode conter golos.")
        if self.status == "verified" and (
            self.home_goals is None
            or self.provenance.method == "unknown"
            or self.provenance.verified_at is None
            or not self.provenance.reference_ids
        ):
            raise ValueError("Resultado verified exige golos e evidência datada.")
        return self


class QualityCategory(ContractModel):
    """Declara se a ausência de eventos pode ser interpretada como zero."""

    status: Literal["complete", "partial", "unavailable", "unknown"]
    evidence: Text | None
    assessed_at: Timestamp | None

    @model_validator(mode="after")
    def validate_evidence(self) -> QualityCategory:
        """Uma declaração complete requer evidência não vazia."""
        if self.status == "complete" and self.evidence is None:
            raise ValueError("Qualidade complete exige evidência.")
        return self


class MatchQuality(ContractModel):
    """Mantém a completude separada por categoria, sem inferências cruzadas."""

    score_events: QualityCategory
    shots: QualityCategory
    cards: QualityCategory
    substitutions: QualityCategory
    other_events: QualityCategory
    player_attribution: QualityCategory
    squad: QualityCategory


class IntegrationEvent(ContractModel):
    """Representa um acontecimento com tempo acumulado e referências de origem."""

    source_event_id: SourceID
    source_match_id: SourceID
    event_type: EventType
    team_id: SourceID
    period: Annotated[int, Field(ge=1, le=2)]
    elapsed_seconds: Count
    minute: Count
    player: PlayerReference | None
    related_player: PlayerReference | None

    @model_validator(mode="after")
    def validate_event(self) -> IntegrationEvent:
        """Confirma o minuto derivado e os papéis do segundo jogador."""
        if self.minute != self.elapsed_seconds // 60:
            raise ValueError("minute deve corresponder a elapsed_seconds // 60.")
        if self.related_player is not None:
            if self.event_type not in {"GOAL", "SUBSTITUTION"}:
                raise ValueError("Este tipo não admite related_player.")
            if self.player and (
                self.player.source_player_id == self.related_player.source_player_id
            ):
                raise ValueError("Os dois jogadores devem ser diferentes.")
        return self


class SquadEntry(ContractModel):
    """Transporta convocatória e titularidade, sem inferir minutos jogados."""

    source_squad_id: SourceID
    player: PlayerReference
    is_starter: bool


class SourceReference(ContractModel):
    """Aponta para o jogo interno sem executar pedidos ao path declarado."""

    resource: Literal["internal_match"]
    id: SourceID
    path: Text | None = None

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str | None) -> str | None:
        """Aceita apenas paths locais simples, sem autoridades ou travessias."""
        if value is not None and (
            not value.startswith("/")
            or "//" in value
            or ".." in value
            or "\\" in value
            or "%" in value
            or "?" in value
            or "#" in value
            or any(ord(char) < 32 for char in value)
        ):
            raise ValueError("path deve ser uma referência local simples.")
        return value


class ExternalReference(ContractModel):
    """Conserva uma referência externa tipada, sem a transformar noutro jogo."""

    resource: Literal["competition_fixture", "official_capture"]
    id: Text


def credited_team_id(event: IntegrationEvent, home_id: str, away_id: str) -> str:
    """Resolve o beneficiário de um golo, invertendo a equipa nos autogolos."""
    if event.event_type not in {"GOAL", "OWN_GOAL"}:
        raise ValueError("A atribuição de golos só aceita GOAL ou OWN_GOAL.")
    if event.team_id not in {home_id, away_id}:
        raise ValueError("Evento de uma equipa que não participa no jogo.")
    if event.event_type == "OWN_GOAL":
        return away_id if event.team_id == home_id else home_id
    return event.team_id


class IntegrationMatch(ContractModel):
    """Valida um jogo terminado e a coerência das suas referências aninhadas."""

    source_match_id: SourceID
    team_id: SourceID
    season_id: SourceID
    competition_id: SourceID | None
    kickoff_at: Timestamp
    timezone: Text
    status: Literal["FINISHED"]
    home_team: TeamReference
    away_team: TeamReference
    score: Score
    events: list[IntegrationEvent]
    squad: list[SquadEntry] | None
    quality: MatchQuality
    data_version: Text
    updated_at: Timestamp | None
    source_reference: SourceReference
    external_references: list[ExternalReference] = Field(default_factory=list)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        """Exige uma zona IANA disponível, sem converter datas ingénuas."""
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Zona IANA desconhecida.") from exc
        return value

    @model_validator(mode="after")
    def validate_references(self) -> IntegrationMatch:
        """Impede eventos, inscrições e resultados contraditórios."""
        home, away = self.home_team.team_id, self.away_team.team_id
        if home == away or self.team_id not in {home, away}:
            raise ValueError(
                "Equipas distintas e equipa-alvo presente são obrigatórias."
            )
        if self.source_reference.id != self.source_match_id:
            raise ValueError("source_reference não corresponde ao jogo.")
        ids = [event.source_event_id for event in self.events]
        if len(ids) != len(set(ids)):
            raise ValueError("IDs de evento duplicados.")
        order = [
            (e.period, e.elapsed_seconds, int(e.source_event_id)) for e in self.events
        ]
        if order != sorted(order):
            raise ValueError("Eventos fora da ordem contratual.")
        squad_players = {entry.player.source_player_id for entry in self.squad or []}
        squad_ids = [entry.source_squad_id for entry in self.squad or []]
        if len(squad_players) != len(self.squad or []) or len(set(squad_ids)) != len(
            squad_ids
        ):
            raise ValueError("Inscrição ou ID de convocatória duplicado.")
        if self.quality.squad.status == "complete" and self.squad is None:
            raise ValueError("Convocatória complete não pode ser null.")
        if self.quality.squad.status == "unavailable" and self.squad is not None:
            raise ValueError("Convocatória unavailable deve ser null.")
        for entry in self.squad or []:
            self._check_player(entry.player, self.team_id)
        players = {
            entry.player.source_player_id: entry.player for entry in self.squad or []
        }
        category_types = {
            "score_events": {"GOAL", "OWN_GOAL"},
            "shots": {"SHOT_ON_TARGET", "SHOT_OFF_TARGET", "SHOT_BLOCKED"},
            "cards": {"YELLOW_CARD", "RED_CARD"},
            "substitutions": {"SUBSTITUTION"},
            "other_events": {
                "CORNER",
                "FREE_KICK",
                "FOUL",
                "OFFSIDE",
                "PENALTY",
                "SAVE",
            },
        }
        for category, types in category_types.items():
            if getattr(self.quality, category).status == "unavailable" and any(
                event.event_type in types for event in self.events
            ):
                raise ValueError("Categoria unavailable não pode fornecer eventos.")
        for event in self.events:
            if event.source_match_id != self.source_match_id or event.team_id not in {
                home,
                away,
            }:
                raise ValueError("Evento de outro jogo ou equipa.")
            for player in (event.player, event.related_player):
                if player is not None:
                    self._check_player(player, event.team_id)
                    if (
                        player.source_player_id in players
                        and players[player.source_player_id] != player
                    ):
                        raise ValueError(
                            "Referências contraditórias à mesma inscrição."
                        )
                    players[player.source_player_id] = player
                    if player.team_id == self.team_id and self.squad is not None:
                        if player.source_player_id not in squad_players:
                            raise ValueError("Jogador fora da convocatória conhecida.")
            if (
                self.quality.player_attribution.status == "complete"
                and event.team_id == self.team_id
            ):
                if (
                    event.event_type in {"GOAL", "SUBSTITUTION"}
                    and event.player is None
                ):
                    raise ValueError("Autoria completa exige jogador neste evento.")
                if event.event_type == "SUBSTITUTION" and event.related_player is None:
                    raise ValueError("Substituição completa exige jogador que entra.")
        if self.score.provenance.method == "events":
            references = {f"event:{event_id}" for event_id in ids}
            if not set(self.score.provenance.reference_ids) <= references | {
                f"match:{self.source_match_id}"
            }:
                raise ValueError("Proveniência aponta para eventos/jogos inexistentes.")
        if self.score.status == "verified":
            if (
                self.score.provenance.method == "events"
                and self.quality.score_events.status != "complete"
            ):
                raise ValueError("Resultado por eventos exige score_events complete.")
            if self.score.provenance.method == "official_capture":
                captures = {
                    f"official_capture:{ref.id}"
                    for ref in self.external_references
                    if ref.resource == "official_capture"
                }
                if not set(self.score.provenance.reference_ids) <= captures:
                    raise ValueError(
                        "Captura oficial ausente das referências externas."
                    )
        if (
            self.score.status == "verified"
            and self.quality.score_events.status == "complete"
        ):
            goals = [
                credited_team_id(e, home, away)
                for e in self.events
                if e.event_type in {"GOAL", "OWN_GOAL"}
            ]
            if (goals.count(home), goals.count(away)) != (
                self.score.home_goals,
                self.score.away_goals,
            ):
                raise ValueError("Resultado não reconcilia com golos e autogolos.")
        return self

    def _check_player(self, player: PlayerReference, team_id: str) -> None:
        if player.team_id != team_id or player.season_id != self.season_id:
            raise ValueError("Inscrição de outra equipa ou época.")


class ExportPackage(ContractModel):
    """Pacote v1 de até cinco jogos; o scope declarado não autentica o ficheiro."""

    schema_version: Literal["1.0"]
    source_system: Literal["match_tracker"]
    source_instance_id: Text
    exported_at: Timestamp
    snapshot_version: Text
    authorized_scope: AuthorizedScope
    selection: Selection
    matches: Annotated[list[IntegrationMatch], Field(max_length=5)]

    @model_validator(mode="after")
    def validate_window(self) -> ExportPackage:
        """Confirma âmbito, unicidade e desempate numérico sem reordenar o input."""
        selection = self.selection
        if selection.team_id != self.authorized_scope.team_id:
            raise ValueError("Selection e scope referem equipas diferentes.")
        if selection.returned_count != len(self.matches):
            raise ValueError("returned_count não corresponde aos jogos.")
        match_ids = [match.source_match_id for match in self.matches]
        event_ids = [e.source_event_id for match in self.matches for e in match.events]
        if len(set(match_ids)) != len(match_ids) or len(set(event_ids)) != len(
            event_ids
        ):
            raise ValueError("IDs de jogos/eventos duplicados na instalação.")
        order = [(m.kickoff_at, int(m.source_match_id)) for m in self.matches]
        if order != sorted(order, reverse=True):
            raise ValueError("Jogos fora da ordem cronológica e do desempate numérico.")
        for match in self.matches:
            if (
                match.team_id != selection.team_id
                or match.season_id != selection.season_id
            ):
                raise ValueError("Jogo fora da equipa/época selecionadas.")
            if (
                selection.competition_scope == "single"
                and match.competition_id != selection.competition_id
            ):
                raise ValueError("Jogo fora da competição selecionada.")
            if (
                match.kickoff_at > selection.as_of
                or match.kickoff_at > self.exported_at
            ):
                raise ValueError("Kickoff posterior ao limite temporal.")
            dates = [match.updated_at, match.score.provenance.verified_at]
            dates.extend(
                getattr(match.quality, name).assessed_at
                for name in MatchQuality.model_fields
            )
            if any(date is not None and date > self.exported_at for date in dates):
                raise ValueError("Atualização/verificação posterior à exportação.")
        return self
