"""Camada de acesso a dados do FootballIQ.

Este pacote é a fronteira entre a aplicação Python e o PostgreSQL. Mantém a
lógica de configuração e conexão isolada dos outros módulos para facilitar
manutenção, testes e futura integração com a CLI ou o ETL.
"""

from footballiq.db.config import DatabaseSettings
from footballiq.db.connection import connect, fetch_match_counts
from footballiq.db.persistence import persist_matches

__all__ = [
    "DatabaseSettings",
    "connect",
    "fetch_match_counts",
    "persist_matches",
]
