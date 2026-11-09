"""Mapeamentos do DDL existente, sem configuração de Engine ou escrita ORM.

Pydantic valida dados de entrada; estes modelos descrevem linhas relacionais.
Mapped indica o tipo de um atributo ORM e mapped_column define a coluna SQL.
relationship permite navegar entre entidades através das chaves estrangeiras.
A persistência mantém Psycopg e o contrato transacional existente, sem Session.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from footballiq.db.base import Base


class Competition(Base):
    """Representa uma competição, opcional na associação a um jogo."""

    __tablename__ = "competitions"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str | None] = mapped_column(String(150), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )


class Team(Base):
    """Representa uma equipa, sem assumir unicidade global do seu nome."""

    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )


class Match(Base):
    """Relaciona duas equipas distintas com o identificador de um jogo na fonte."""

    __tablename__ = "matches"
    __table_args__ = (
        # O SQL deixa estes três nomes ao PostgreSQL; confirmar no catálogo
        # antes do baseline Alembic, como previsto no plano de migração.
        CheckConstraint("home_goals >= 0", name="matches_home_goals_check"),
        CheckConstraint("away_goals >= 0", name="matches_away_goals_check"),
        CheckConstraint("status = 'finished'", name="matches_status_check"),
        CheckConstraint(
            "home_team_id <> away_team_id", name="chk_matches_teams_different"
        ),
        UniqueConstraint(
            "source", "source_match_id", name="uq_matches_source_match_id"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    competition_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("competitions.id", name="fk_matches_competition"),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_match_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    home_team_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("teams.id", name="fk_matches_home_team"), nullable=False
    )
    away_team_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("teams.id", name="fk_matches_away_team"), nullable=False
    )
    home_goals: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    away_goals: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'finished'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("NOW()")
    )

    competition: Mapped[Competition | None] = relationship(viewonly=True)
    # Duas FKs apontam para teams: explicitar cada uma evita joins ambíguos.
    home_team: Mapped[Team] = relationship(foreign_keys=[home_team_id], viewonly=True)
    away_team: Mapped[Team] = relationship(foreign_keys=[away_team_id], viewonly=True)
