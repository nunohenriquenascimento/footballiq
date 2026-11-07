"""Modelo declarativo para validar partidas de futebol."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class FootballMatch(BaseModel):
    """Representa uma partida válida de futebol com regras de integridade.

    A validação declarativa mantém a regra em um único local e reduz a duplicação
    de condições no ETL. A estrutura também gera JSON de saída pronto para serializar.
    """

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        str_strip_whitespace=True,
    )

    match_id: int = Field(ge=1)
    home_team: str = Field(min_length=1)
    away_team: str = Field(min_length=1)
    home_goals: int = Field(ge=0)
    away_goals: int = Field(ge=0)
    status: Literal["finished"]

    @field_validator("match_id", "home_goals", "away_goals", mode="before")
    @classmethod
    def reject_boolean_integers(cls, value: object) -> object:
        """Rejeita booleanos, porque True/False são inteiros em Python, mas não em dados válidos."""
        if isinstance(value, bool):
            raise ValueError("must be an integer, not a boolean.")
        return value

    @field_validator("home_team", "away_team")
    @classmethod
    def normalize_team_names(cls, value: str) -> str:
        """Normaliza espaços em branco e garante que a equipa não fica vazia."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("must be a non-empty string.")
        return normalized

    @model_validator(mode="after")
    def ensure_distinct_teams(self) -> FootballMatch:
        """Impede equipas repetidas após a normalização de nomes."""
        if self.home_team == self.away_team:
            raise ValueError("home_team and away_team must be different.")
        return self
