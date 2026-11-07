"""Testes de integração opcionais para o PostgreSQL local.

A intenção é manter a validação explícita e segura: apenas um ambiente que
aponta para `footballiq_dev` pode executar estes testes. A role e a password devem
ser configuradas por variáveis de ambiente e não por valores fixos no código.
"""

from __future__ import annotations

import os

import pytest

from footballiq.db.connection import connect
from footballiq.db.persistence import persist_matches

pytestmark = pytest.mark.integration


SAMPLE_MATCHES = [
    {
        "match_id": 101,
        "home_team": "Benfica",
        "away_team": "Porto",
        "home_goals": 2,
        "away_goals": 1,
        "status": "finished",
    },
    {
        "match_id": 102,
        "home_team": "Sporting",
        "away_team": "Braga",
        "home_goals": 1,
        "away_goals": 1,
        "status": "finished",
    },
    {
        "match_id": 103,
        "home_team": "Ajax",
        "away_team": "PSV",
        "home_goals": 0,
        "away_goals": 3,
        "status": "finished",
    },
    {
        "match_id": 104,
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "home_goals": 2,
        "away_goals": 0,
        "status": "finished",
    },
    {
        "match_id": 105,
        "home_team": "Real Madrid",
        "away_team": "Barcelona",
        "home_goals": 1,
        "away_goals": 1,
        "status": "finished",
    },
]


def _assert_empty_database(connection) -> None:
    """Confirma que as tabelas relevantes ainda estão vazias no início e no fim dos testes."""
    with connection.cursor() as cursor:
        for table_name in ("competitions", "teams", "matches"):
            cursor.execute(f"SELECT COUNT(*) FROM public.{table_name};")
            assert cursor.fetchone()[0] == 0


@pytest.mark.skipif(
    os.getenv("FOOTBALLIQ_DB_RUN_INTEGRATION", "").lower() not in {"1", "true", "yes"},
    reason="integração PostgreSQL desativada por defeito; ativar FOOTBALLIQ_DB_RUN_INTEGRATION=1",
)
def test_connection_reads_current_database() -> None:
    """Valida a ligação apenas para a database autorizada `footballiq_dev`."""
    db_name = os.getenv("FOOTBALLIQ_DB_NAME", "footballiq_dev")
    db_user = os.getenv("FOOTBALLIQ_DB_USER", "")

    if db_name != "footballiq_dev":
        pytest.skip("a integração só pode apontar para footballiq_dev")
    if not db_user:
        pytest.skip("a integração exige FOOTBALLIQ_DB_USER explícito")

    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), current_user;")
            result = cursor.fetchone()

    assert result is not None
    assert result[0] == "footballiq_dev"
    assert result[1] == db_user


@pytest.mark.skipif(
    os.getenv("FOOTBALLIQ_DB_RUN_INTEGRATION", "").lower() not in {"1", "true", "yes"},
    reason="integração PostgreSQL desativada por defeito; ativar FOOTBALLIQ_DB_RUN_INTEGRATION=1",
)
def test_persist_matches_is_idempotent_and_rollback_safe() -> None:
    """A persistência real deve escrever, atualizar e reverter dentro de uma transação controlada pelo chamador."""
    db_name = os.getenv("FOOTBALLIQ_DB_NAME", "footballiq_dev")
    db_user = os.getenv("FOOTBALLIQ_DB_USER", "")

    if db_name != "footballiq_dev":
        pytest.skip("a integração só pode apontar para footballiq_dev")
    if not db_user:
        pytest.skip("a integração exige FOOTBALLIQ_DB_USER explícito")

    with connect() as connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute("BEGIN;")

            _assert_empty_database(connection)

            first_count = persist_matches(
                SAMPLE_MATCHES, source="sample", connection=connection
            )
            assert first_count == 5

            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM public.teams;")
                assert cursor.fetchone()[0] == 10
                cursor.execute(
                    "SELECT COUNT(*) FROM public.matches WHERE source = 'sample';"
                )
                assert cursor.fetchone()[0] == 5

            second_count = persist_matches(
                SAMPLE_MATCHES, source="sample", connection=connection
            )
            assert second_count == 5

            updated_match = {
                "match_id": 101,
                "home_team": "Benfica",
                "away_team": "Porto",
                "home_goals": 1,
                "away_goals": 0,
                "status": "finished",
            }
            update_count = persist_matches(
                [updated_match], source="sample", connection=connection
            )
            assert update_count == 1

            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT home_goals, away_goals FROM public.matches WHERE source = 'sample' AND source_match_id = 101;"
                )
                assert cursor.fetchone() == (1, 0)
                cursor.execute(
                    "SELECT COUNT(*) FROM public.matches WHERE source <> 'sample';"
                )
                assert cursor.fetchone()[0] == 0

            with connection.cursor() as cursor:
                cursor.execute("SAVEPOINT invalid_payload;")

            try:
                persist_matches(
                    [
                        {
                            "match_id": 999,
                            "home_team": "Benfica",
                            "away_team": "Benfica",
                            "home_goals": 1,
                            "away_goals": 0,
                            "status": "finished",
                        }
                    ],
                    source="sample",
                    connection=connection,
                )
            except ValueError:
                with connection.cursor() as cursor:
                    cursor.execute("ROLLBACK TO SAVEPOINT invalid_payload;")
            else:
                raise AssertionError("assinatura inválida deveria ser rejeitada")

            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) FROM public.matches WHERE source = 'sample';"
                )
                assert cursor.fetchone()[0] == 5
                cursor.execute("SELECT COUNT(*) FROM public.teams;")
                assert cursor.fetchone()[0] == 10

            raise RuntimeError("rollback explícito do teste")
        except RuntimeError:
            connection.rollback()
        except Exception:
            connection.rollback()
            raise
        else:
            connection.rollback()

    with connect() as verification_connection:
        _assert_empty_database(verification_connection)
