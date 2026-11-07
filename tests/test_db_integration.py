"""Testes de integração opcionais para o PostgreSQL local.

A intenção é manter a validação explícita e segura: apenas um ambiente que
aponta para `footballiq_dev` pode executar este teste. A role e a password devem
ser configuradas por variáveis de ambiente e não por valores fixos no código.
"""

from __future__ import annotations

import os

import pytest

from footballiq.db.connection import connect

pytestmark = pytest.mark.integration


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
