"""Testes de persistência idempotente para jogos de futebol.

Os testes unitários usam um ``FakeConnection`` em memória para verificar a lógica
real de persistência sem depender do servidor PostgreSQL. Isso mantém a suíte
rápida e evita escrita persistente em ambientes locais.
"""

from __future__ import annotations

import pytest

from footballiq.db.persistence import persist_matches


class FakeCursor:
    """Cursor em memória que simula o comportamento essencial do psycopg."""

    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection
        self._results: list[tuple] = []

    def execute(self, sql: str, params: tuple | None = None) -> None:
        params = params or ()
        sql_text = sql.strip()

        if "SELECT id, name FROM teams WHERE name = ANY" in sql_text:
            team_names = set(params[0])
            self._results = [
                (team_id, name)
                for name, team_ids in self.connection.teams.items()
                for team_id in team_ids
                if name in team_names
            ]
            return

        if sql_text.startswith("INSERT INTO teams"):
            team_name = params[0]
            new_id = self.connection.next_team_id
            self.connection.teams.setdefault(team_name, []).append(new_id)
            self.connection.next_team_id += 1
            self._results = [(new_id,)]
            return

        if sql_text.startswith("INSERT INTO matches"):
            (
                source,
                source_match_id,
                home_team_id,
                away_team_id,
                home_goals,
                away_goals,
                status,
                competition_id,
            ) = params
            key = (source, int(source_match_id))
            self.connection.matches[key] = {
                "source": source,
                "source_match_id": int(source_match_id),
                "home_team_id": int(home_team_id),
                "away_team_id": int(away_team_id),
                "home_goals": int(home_goals),
                "away_goals": int(away_goals),
                "status": status,
                "competition_id": competition_id,
            }
            self._results = []
            return

        raise AssertionError(f"SQL não suportado no FakeCursor: {sql_text}")

    def fetchone(self):
        if not self._results:
            return None
        return self._results[0]

    def fetchall(self):
        return self._results

    def close(self) -> None:
        self._results = []


class FakeConnection:
    """Conexão em memória apenas para validar a lógica de persistência."""

    def __init__(self) -> None:
        self.teams: dict[str, list[int]] = {}
        self.matches: dict[tuple[str, int], dict[str, object]] = {}
        self.next_team_id = 1

    def __enter__(self) -> FakeConnection:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def transaction(self) -> FakeTransaction:
        return FakeTransaction(self)

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)


class FakeTransaction:
    """Context manager que simula uma transação do psycopg."""

    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def __enter__(self) -> FakeTransaction:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


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


def test_persist_matches_inserts_five_games() -> None:
    """A primeira carga deve inserir os cinco jogos do sample sem duplicações."""
    connection = FakeConnection()

    count = persist_matches(SAMPLE_MATCHES, source="sample", connection=connection)

    assert count == 5
    assert len(connection.matches) == 5
    assert connection.matches[("sample", 101)]["home_goals"] == 2
    assert len(connection.teams["Benfica"]) == 1


def test_persist_matches_is_idempotent_on_repeat() -> None:
    """A segunda carga do mesmo dataset deve manter o mesmo número de registos."""
    connection = FakeConnection()

    first_count = persist_matches(
        SAMPLE_MATCHES, source="sample", connection=connection
    )
    second_count = persist_matches(
        SAMPLE_MATCHES, source="sample", connection=connection
    )

    assert first_count == 5
    assert second_count == 5
    assert len(connection.matches) == 5


def test_persist_matches_updates_existing_game() -> None:
    """Uma atualização do resultado de um jogo deve trocar os golos com ON CONFLICT."""
    connection = FakeConnection()
    persist_matches(SAMPLE_MATCHES, source="sample", connection=connection)

    updated_match = {
        "match_id": 101,
        "home_team": "Benfica",
        "away_team": "Porto",
        "home_goals": 1,
        "away_goals": 0,
        "status": "finished",
    }
    count = persist_matches([updated_match], source="sample", connection=connection)

    assert count == 1
    assert connection.matches[("sample", 101)]["home_goals"] == 1
    assert connection.matches[("sample", 101)]["away_goals"] == 0
    assert len(connection.matches) == 5


def test_persist_matches_rejects_ambiguous_team_identity() -> None:
    """Se o mesmo nome de equipa aparecer em múltiplas linhas, não deve escolher arbitrariamente."""
    connection = FakeConnection()
    connection.teams["Benfica"] = [11, 22]

    match = {
        "match_id": 201,
        "home_team": "Benfica",
        "away_team": "Porto",
        "home_goals": 1,
        "away_goals": 0,
        "status": "finished",
    }

    with pytest.raises(ValueError, match="Ambiguous team identity"):
        persist_matches([match], source="sample", connection=connection)


def test_persist_matches_rejects_invalid_data() -> None:
    """Dados inválidos devem falhar antes da escrita e não gravar nada."""
    connection = FakeConnection()
    bad_match = {
        "match_id": 999,
        "home_team": "Benfica",
        "away_team": "Benfica",
        "home_goals": 1,
        "away_goals": 0,
        "status": "finished",
    }

    with pytest.raises(ValueError, match="different"):
        persist_matches([bad_match], source="sample", connection=connection)

    assert len(connection.matches) == 0
