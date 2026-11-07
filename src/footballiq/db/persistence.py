"""Persistência idempotente de partidas para o PostgreSQL do FootballIQ."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from footballiq.db.config import DatabaseSettings
from footballiq.db.connection import connect
from footballiq.etl import validate_match


def _resolve_team_mapping(cursor: Any, team_names: set[str]) -> dict[str, int]:
    """Resolve nomes de equipas para IDs internos, criando linhas vagas quando necessário.

    A lógica mantém a regra do projeto: nomes de equipa não têm unicidade global,
    mas um mesmo nome em contexto de uma carga não pode ser ambíguo. Quando o
    mesmo nome existir em diversas linhas da tabela, levantamos um erro explícito
    em vez de escolher uma linha arbitrariamente.
    """
    if not team_names:
        return {}

    ordered_names = sorted(team_names)
    cursor.execute(
        "SELECT id, name FROM teams WHERE name = ANY(%s)",
        (ordered_names,),
    )
    database_rows = cursor.fetchall()
    team_ids_by_name: defaultdict[str, list[int]] = defaultdict(list)

    for team_id, team_name in database_rows:
        team_ids_by_name[str(team_name)].append(int(team_id))

    for team_name in ordered_names:
        current_ids = team_ids_by_name.get(team_name, [])
        if len(current_ids) > 1:
            raise ValueError(
                f"Ambiguous team identity for {team_name!r}: {len(current_ids)} IDs found."
            )
        if not current_ids:
            cursor.execute(
                "INSERT INTO teams (name) VALUES (%s) RETURNING id",
                (team_name,),
            )
            inserted_row = cursor.fetchone()
            if inserted_row is None:
                raise RuntimeError(f"Failed to create team row for {team_name!r}.")
            team_ids_by_name[team_name] = [int(inserted_row[0])]

    return {team_name: team_ids_by_name[team_name][0] for team_name in ordered_names}


def _prepare_matches(matches: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Valida cada partida antes de escrever qualquer registo na base de dados."""
    validated_matches: list[dict[str, Any]] = []
    for raw_match in matches:
        validated_matches.append(validate_match(dict(raw_match)))
    return validated_matches


def persist_matches(
    matches: Sequence[Mapping[str, Any]],
    source: str,
    *,
    connection: Any | None = None,
    settings: DatabaseSettings | None = None,
) -> int:
    """Persiste partidas de futebol numa base PostgreSQL de forma idempotente.

    A função aceita uma sequência de dicionários já em formato de negócio, valida
    os dados através do mesmo modelo ETL e grava em `matches` usando a chave
    natural `(source, source_match_id)`. Quando o mesmo jogo for submetido duas
    vezes, a instrução `ON CONFLICT DO UPDATE` mantém a mesma linha e apenas
    altera os campos relevantes.
    """
    if not isinstance(source, str) or not source.strip():
        raise ValueError("source must be a non-empty string.")

    validated_matches = _prepare_matches(matches)
    if not validated_matches:
        return 0

    team_names = {
        team_name
        for match in validated_matches
        for team_name in (match["home_team"], match["away_team"])
    }

    if connection is None:
        with connect(settings=settings) as opened_connection:
            return _persist_matches_in_connection(
                opened_connection, source, validated_matches, team_names
            )

    return _persist_matches_in_connection(
        connection, source, validated_matches, team_names
    )


def _persist_matches_in_connection(
    connection: Any,
    source: str,
    validated_matches: list[dict[str, Any]],
    team_names: set[str],
) -> int:
    """Executa a gravação real no contexto de transação."""
    with connection.transaction():
        cursor = connection.cursor()
        try:
            team_lookup = _resolve_team_mapping(cursor, team_names)
            processed_count = 0

            for match in validated_matches:
                home_id = team_lookup[match["home_team"]]
                away_id = team_lookup[match["away_team"]]
                if home_id == away_id:
                    raise ValueError("home_team and away_team must be different.")

                cursor.execute(
                    """
                    INSERT INTO matches (
                        source,
                        source_match_id,
                        home_team_id,
                        away_team_id,
                        home_goals,
                        away_goals,
                        status,
                        competition_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source, source_match_id)
                    DO UPDATE SET
                        home_team_id = EXCLUDED.home_team_id,
                        away_team_id = EXCLUDED.away_team_id,
                        home_goals = EXCLUDED.home_goals,
                        away_goals = EXCLUDED.away_goals,
                        status = EXCLUDED.status,
                        competition_id = EXCLUDED.competition_id
                    """,
                    (
                        source,
                        int(match["match_id"]),
                        home_id,
                        away_id,
                        int(match["home_goals"]),
                        int(match["away_goals"]),
                        match["status"],
                        None,
                    ),
                )
                processed_count += 1
        finally:
            cursor.close()

    return processed_count


__all__ = ["persist_matches"]
