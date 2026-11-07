"""Configuração da ligação PostgreSQL para o FootballIQ.

As credenciais e os detalhes do servidor devem ser lidos a partir de variáveis de
ambiente. Isto evita guardar dados sensíveis no código e permite reutilizar a
mesma aplicação em desenvolvimento, testes e produção sem alterar o código.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DatabaseSettings:
    """Representa as opções mínimas de conexão ao PostgreSQL.

    O utilizador (`user`) não tem um default rígido porque a máquina local pode
    usar nomes de role diferentes. A configuração explícita por variáveis de
    ambiente é a forma segura de evitar conexões acidentais a outra base.
    """

    host: str = "127.0.0.1"
    port: int = 5432
    dbname: str = "footballiq_dev"
    user: str = ""
    password: str = ""
    sslmode: str = "prefer"

    @classmethod
    def from_env(cls) -> DatabaseSettings:
        """Carrega os valores de ambiente com defaults seguros para o projeto."""
        return cls(
            host=os.getenv("FOOTBALLIQ_DB_HOST", "127.0.0.1"),
            port=int(os.getenv("FOOTBALLIQ_DB_PORT", "5432")),
            dbname=os.getenv("FOOTBALLIQ_DB_NAME", "footballiq_dev"),
            user=os.getenv("FOOTBALLIQ_DB_USER", ""),
            password=os.getenv("FOOTBALLIQ_DB_PASSWORD", ""),
            sslmode=os.getenv("FOOTBALLIQ_DB_SSLMODE", "prefer"),
        )

    @property
    def dsn(self) -> str:
        """Cria uma representação segura da conexão sem expor segredos."""
        connection_parts = [
            f"host={self.host}",
            f"port={self.port}",
            f"dbname={self.dbname}",
            f"sslmode={self.sslmode}",
        ]
        if self.user:
            connection_parts.append(f"user={self.user}")
        if self.password:
            connection_parts.append(f"password={self.password}")
        return " ".join(connection_parts)

    def as_connect_kwargs(self) -> dict[str, str | int]:
        """Converte as opções num dicionário para o `psycopg.connect`.

        A role não pode ficar vazia porque isso poderia levar a uma ligação
        implícita ao utilizador do sistema e, em algumas máquinas, a uma base
        diferente da de desenvolvimento. A mesma regra aplica para o teste de
        integração, que só pode apontar para `footballiq_dev`.
        """
        if not self.user:
            raise ValueError(
                "FOOTBALLIQ_DB_USER deve ser definido explicitamente antes de abrir "
                "uma ligação PostgreSQL."
            )

        kwargs: dict[str, str | int] = {
            "host": self.host,
            "port": self.port,
            "dbname": self.dbname,
            "user": self.user,
            "sslmode": self.sslmode,
        }
        if self.password:
            kwargs["password"] = self.password
        return kwargs
