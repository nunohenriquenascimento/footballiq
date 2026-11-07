"""Funções de leitura e conexão ao PostgreSQL do FootballIQ.

A tarefa atual limita-se a leitura segura da base `footballiq_dev`. Não existem
operações de escrita, atualização ou eliminação neste módulo.
"""

from __future__ import annotations

from typing import Any

import psycopg

from footballiq.db.config import DatabaseSettings


def connect(settings: DatabaseSettings | None = None) -> psycopg.Connection[Any]:
    """Abre uma ligação PostgreSQL usando as variáveis de ambiente.

    A construção do objeto é simples e fica isolada para facilitar testes e manter
    o tratamento de erros centrado num único ponto.
    """
    resolved_settings = settings or DatabaseSettings.from_env()
    try:
        return psycopg.connect(**resolved_settings.as_connect_kwargs())
    except psycopg.Error as exc:
        raise RuntimeError(
            "Não foi possível abrir a ligação ao PostgreSQL. "
            "Verifique as variáveis FOOTBALLIQ_DB_* e o estado do servidor."
        ) from exc


def fetch_match_counts(
    source: str | None = None,
    settings: DatabaseSettings | None = None,
) -> list[dict[str, int | str]]:
    """Lê o número de jogos por origem.

    A query usa parâmetros SQL para evitar concatenação com valores externos e
    manter a leitura segura. O resultado é devolvido como uma lista de dicionários
    para facilitar testes e análise no Python.
    """
    if source is None:
        sql = "SELECT source, COUNT(*) AS match_count FROM matches GROUP BY source ORDER BY source"
        params: tuple[Any, ...] = ()
    else:
        sql = (
            "SELECT source, COUNT(*) AS match_count "
            "FROM matches WHERE source = %s GROUP BY source ORDER BY source"
        )
        params = (source,)

    with connect(settings=settings) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()

    return [
        {"source": source_name, "match_count": int(match_count)}
        for source_name, match_count in rows
    ]
