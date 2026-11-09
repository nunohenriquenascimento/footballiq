"""Verifica metadata e compilação PostgreSQL, sem contactar uma base real."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint, inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import configure_mappers
from sqlalchemy.schema import CreateTable

from footballiq.db.base import Base
from footballiq.db.models import Competition, Match, Team

DIALECT = postgresql.dialect()
EXPECTED_TYPES = {
    "competitions": {
        "id": "BIGINT",
        "name": "VARCHAR(150)",
        "slug": "VARCHAR(150)",
        "created_at": "TIMESTAMP WITH TIME ZONE",
    },
    "teams": {
        "id": "BIGINT",
        "name": "VARCHAR(150)",
        "created_at": "TIMESTAMP WITH TIME ZONE",
    },
    "matches": {
        "id": "BIGINT",
        "competition_id": "BIGINT",
        "source": "VARCHAR(50)",
        "source_match_id": "BIGINT",
        "home_team_id": "BIGINT",
        "away_team_id": "BIGINT",
        "home_goals": "SMALLINT",
        "away_goals": "SMALLINT",
        "status": "VARCHAR(20)",
        "created_at": "TIMESTAMP WITH TIME ZONE",
    },
}
REFERENCE_SQL = (
    Path(__file__).resolve().parents[1] / "sql/schema/001_initial_schema.sql"
).read_text(encoding="utf-8")


def test_metadata_contains_exactly_the_reference_tables() -> None:
    """Impede tabelas adicionais ou modelos ligados a outra Base."""
    assert set(Base.metadata.tables) == set(EXPECTED_TYPES)
    for model in (Competition, Team, Match):
        assert model.__table__.metadata is Base.metadata
        assert f"CREATE TABLE {model.__tablename__} (" in REFERENCE_SQL
        assert model.__table__.schema is None


@pytest.mark.parametrize("table_name", EXPECTED_TYPES)
def test_column_contract_matches_postgresql_ddl(table_name: str) -> None:
    """Verifica todas as colunas, tipos, limites de texto e nulabilidade."""
    table = Base.metadata.tables[table_name]
    assert {
        column.name: column.type.compile(dialect=DIALECT) for column in table.c
    } == (EXPECTED_TYPES[table_name])
    nullable_columns = {"slug"} if table_name == "competitions" else set()
    if table_name == "matches":
        nullable_columns = {"competition_id"}
    assert {column.name for column in table.c if column.nullable} == nullable_columns
    assert list(table.primary_key.columns.keys()) == ["id"]
    for column in table.c:
        if column.name not in {"id", "created_at", "status"}:
            assert column.server_default is None
        assert column.default is None
        assert column.onupdate is None


@pytest.mark.parametrize("table_name", EXPECTED_TYPES)
def test_identity_and_server_defaults_compile_for_postgresql(table_name: str) -> None:
    """Confirma geração no servidor, sem criar tabelas nem gerar IDs em Python."""
    table = Base.metadata.tables[table_name]
    assert table.c.id.identity is not None
    assert table.c.id.identity.always is True
    assert str(table.c.created_at.server_default.arg) == "NOW()"
    assert table.c.created_at.type.timezone is True
    ddl = str(CreateTable(table).compile(dialect=DIALECT))
    assert "id BIGINT GENERATED ALWAYS AS IDENTITY" in ddl
    assert "created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL" in ddl
    if table_name == "matches":
        assert str(table.c.status.server_default.arg) == "'finished'"
        assert "status VARCHAR(20) DEFAULT 'finished' NOT NULL" in ddl


def test_checks_preserve_expressions_and_explicit_name() -> None:
    """Compara os checks com as regras do SQL, incluindo nomes propostos."""
    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in Match.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert checks == {
        "matches_home_goals_check": "home_goals >= 0",
        "matches_away_goals_check": "away_goals >= 0",
        "matches_status_check": "status = 'finished'",
        "chk_matches_teams_different": "home_team_id <> away_team_id",
    }
    for expression in checks.values():
        assert f"CHECK ({expression})" in REFERENCE_SQL
    assert "CONSTRAINT chk_matches_teams_different" in REFERENCE_SQL
    for model in (Competition, Team):
        assert not any(
            isinstance(constraint, CheckConstraint)
            for constraint in model.__table__.constraints
        )


def test_only_business_key_has_a_unique_constraint() -> None:
    """Não introduz unicidade nos nomes de equipas nem nos slugs."""
    uniques = {
        (table.name, constraint.name, tuple(constraint.columns.keys()))
        for table in Base.metadata.tables.values()
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert uniques == {
        ("matches", "uq_matches_source_match_id", ("source", "source_match_id"))
    }
    assert "UNIQUE (source, source_match_id)" in REFERENCE_SQL
    for table in Base.metadata.tables.values():
        assert not table.indexes
        assert all(not column.unique for column in table.c)


def test_foreign_keys_keep_names_targets_and_default_actions() -> None:
    """Preserva referências e não acrescenta ações de eliminação ou atualização."""
    foreign_keys = Match.__table__.foreign_key_constraints
    assert {
        (
            constraint.name,
            tuple(constraint.columns.keys()),
            constraint.elements[0].target_fullname,
        )
        for constraint in foreign_keys
    } == {
        ("fk_matches_competition", ("competition_id",), "competitions.id"),
        ("fk_matches_home_team", ("home_team_id",), "teams.id"),
        ("fk_matches_away_team", ("away_team_id",), "teams.id"),
    }
    ddl = str(CreateTable(Match.__table__).compile(dialect=DIALECT))
    for constraint in foreign_keys:
        assert constraint.ondelete is None
        assert constraint.onupdate is None
        assert len(constraint.elements) == 1
        assert f"CONSTRAINT {constraint.name}" in REFERENCE_SQL
        assert f"CONSTRAINT {constraint.name}" in ddl


def test_mappers_and_relationships_are_unambiguous_and_viewonly() -> None:
    """Configura os mappers e confirma o join de cada papel das equipas."""
    configure_mappers()
    assert all(inspect(model).configured for model in (Competition, Team, Match))
    mapper = inspect(Match)
    assert set(mapper.relationships.keys()) == {"competition", "home_team", "away_team"}
    for name, target, local_column in (
        ("competition", Competition, "competition_id"),
        ("home_team", Team, "home_team_id"),
        ("away_team", Team, "away_team_id"),
    ):
        relation = mapper.relationships[name]
        assert relation.mapper.class_ is target
        assert relation.local_remote_pairs == [
            (Match.__table__.c[local_column], target.__table__.c.id)
        ]
        assert relation.viewonly is True
        assert relation.uselist is False
        assert "delete" not in relation.cascade
        assert "delete-orphan" not in relation.cascade
    assert not inspect(Competition).relationships
    assert not inspect(Team).relationships


def test_fresh_import_has_no_connection_or_schema_side_effects() -> None:
    """Usa um processo novo para não esconder efeitos pelo cache de imports."""
    script = """
from unittest.mock import patch
import socket
import psycopg
import sqlalchemy
from sqlalchemy import MetaData
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

def forbidden(*args, **kwargs):
    raise AssertionError("Importing models must not connect, execute SQL or create schema")

with (
    patch.object(socket, "create_connection", forbidden),
    patch.object(socket.socket, "connect", forbidden),
    patch.object(psycopg, "connect", forbidden),
    patch.object(sqlalchemy, "create_engine", forbidden),
    patch.object(sqlalchemy.engine, "create_engine", forbidden),
    patch.object(Engine, "connect", forbidden),
    patch.object(Connection, "execute", forbidden),
    patch.object(Connection, "exec_driver_sql", forbidden),
    patch.object(MetaData, "create_all", forbidden),
    patch.object(MetaData, "drop_all", forbidden),
    patch.object(Session, "__init__", forbidden),
):
    from footballiq.db.models import Competition, Team, Match
    assert len(Match.metadata.tables) == 3
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
