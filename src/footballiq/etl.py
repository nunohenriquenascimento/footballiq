"""Pipeline ETL simples para dados fictícios de partidas de futebol."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any


def _validate_int_field(
    value: Any,
    field_name: str,
    *,
    minimum: int = 0,
    allow_zero: bool = True,
) -> int:
    """Valida inteiros simples, rejeitando booleanos e valores fora do intervalo."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")
    if value < minimum or (not allow_zero and value == 0):
        raise ValueError(f"{field_name} must be greater than or equal to {minimum}.")
    return value


def validate_match(raw_match: dict[str, Any]) -> dict[str, Any]:
    """Valida uma partida, garantindo que os campos essenciais estão corretos."""
    if not isinstance(raw_match, dict):
        raise ValueError("Match must be an object.")

    match_id = _validate_int_field(raw_match.get("match_id"), "match_id", minimum=1)
    home_team = raw_match.get("home_team")
    if not isinstance(home_team, str) or not home_team.strip():
        raise ValueError("home_team must be a non-empty string.")

    away_team = raw_match.get("away_team")
    if not isinstance(away_team, str) or not away_team.strip():
        raise ValueError("away_team must be a non-empty string.")
    if home_team.strip() == away_team.strip():
        raise ValueError("home_team and away_team must be different.")

    home_goals = _validate_int_field(
        raw_match.get("home_goals"), "home_goals", minimum=0
    )
    away_goals = _validate_int_field(
        raw_match.get("away_goals"), "away_goals", minimum=0
    )
    status = raw_match.get("status")
    if status != "finished":
        raise ValueError("status must be 'finished'.")

    normalized = dict(raw_match)
    normalized["match_id"] = match_id
    normalized["home_team"] = home_team.strip()
    normalized["away_team"] = away_team.strip()
    normalized["home_goals"] = home_goals
    normalized["away_goals"] = away_goals
    normalized["status"] = "finished"
    return normalized


def extract_matches(input_path: str | Path) -> list[dict[str, Any]]:
    """Lê uma lista de jogos a partir de um JSON de entrada."""
    path = Path(input_path)
    try:
        raw_text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Input file not found: {path}") from exc

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc.msg}") from exc

    if not isinstance(payload, list):
        raise ValueError("JSON content must be a list of matches.")

    validated_matches: list[dict[str, Any]] = []
    seen_match_ids: set[int] = set()

    for index, match in enumerate(payload):
        if not isinstance(match, dict):
            raise ValueError(f"Match at index {index} must be an object.")

        validated = validate_match(match)
        match_id = validated["match_id"]
        if match_id in seen_match_ids:
            raise ValueError(f"Duplicate match_id detected: {match_id}.")
        seen_match_ids.add(match_id)
        validated_matches.append(validated)

    return validated_matches


def transform_match(match: dict[str, Any]) -> dict[str, Any]:
    """Calcula métricas derivadas para uma partida válida."""
    home_goals = match["home_goals"]
    away_goals = match["away_goals"]
    total_goals = home_goals + away_goals
    goal_difference = home_goals - away_goals

    if home_goals > away_goals:
        winner = "home"
    elif away_goals > home_goals:
        winner = "away"
    else:
        winner = "draw"

    transformed = dict(match)
    transformed["total_goals"] = total_goals
    transformed["goal_difference"] = goal_difference
    transformed["winner"] = winner
    return transformed


def load_results(
    transformed_matches: Sequence[dict[str, Any]], output_path: str | Path
) -> Path:
    """Escreve os dados transformados para um ficheiro JSON de saída."""
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    with destination.open("w", encoding="utf-8") as file_handle:
        json.dump(list(transformed_matches), file_handle, ensure_ascii=False, indent=2)
        file_handle.write("\n")

    return destination


def run_etl(input_path: str | Path, output_path: str | Path) -> list[dict[str, Any]]:
    """Executa a cadeia completa ETL: extração, validação, transformação e carga."""
    validated_matches = extract_matches(input_path)
    transformed_matches = [transform_match(match) for match in validated_matches]
    load_results(transformed_matches, output_path)
    return transformed_matches


def build_parser() -> argparse.ArgumentParser:
    """Cria a interface de linha de comandos do pipeline."""
    parser = argparse.ArgumentParser(
        description="ETL simples para dados fictícios de futebol."
    )
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=Path("data/sample/matches.json"),
        help="Caminho do ficheiro JSON com as partidas de entrada.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("results/matches_summary.json"),
        help="Caminho do ficheiro JSON de saída do pipeline.",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    """Ponto de entrada da CLI para executar o ETL.

    O programa lê um JSON de partidas e grava um resumo em JSON no diretório de
    resultados. O comportamento é simples para ser fácil de depurar e testar.
    """
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        matches = run_etl(args.input, args.output)
    except (FileNotFoundError, ValueError, OSError) as exc:
        parser.exit(1, f"Erro no pipeline ETL: {exc}\n")

    print(f"Processados {len(matches)} jogos.")
    print(f"Resumo guardado em {args.output}")
    for match in matches:
        print(
            f"{match['match_id']}: {match['home_team']} {match['home_goals']} - "
            f"{match['away_goals']} {match['away_team']} ({match['winner']})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
