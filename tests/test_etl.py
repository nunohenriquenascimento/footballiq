"""Testes para o pipeline ETL inicial do FootballIQ."""

import json

import pytest

from footballiq.etl import (
    extract_matches,
    load_results,
    main,
    run_etl,
    transform_match,
    validate_match,
)

VALID_MATCH = {
    "match_id": 101,
    "home_team": "Benfica",
    "away_team": "Porto",
    "home_goals": 2,
    "away_goals": 1,
    "status": "finished",
}


def test_extract_matches_reads_valid_json(tmp_path) -> None:
    """Lê um ficheiro JSON de jogos e devolve a lista correspondente."""
    input_path = tmp_path / "matches.json"
    payload = [
        VALID_MATCH,
        {
            **VALID_MATCH,
            "match_id": 102,
            "home_team": "Sporting",
            "away_team": "Braga",
            "home_goals": 0,
            "away_goals": 0,
        },
    ]
    input_path.write_text(json.dumps(payload), encoding="utf-8")

    matches = extract_matches(input_path)

    assert matches == payload


def test_validate_match_rejects_boolean_integers() -> None:
    """Não aceita booleanos no lugar de inteiros."""
    invalid_match = {**VALID_MATCH, "match_id": True, "home_goals": True}

    with pytest.raises(ValueError, match="match_id|home_goals"):
        validate_match(invalid_match)


def test_validate_match_rejects_negative_goals() -> None:
    """Rejeita golos negativos mesmo quando os campos são do tipo correto."""
    invalid_match = {**VALID_MATCH, "home_goals": -1}

    with pytest.raises(ValueError, match="home_goals"):
        validate_match(invalid_match)


def test_validate_match_rejects_missing_required_field() -> None:
    """Rejeita campos obrigatórios em falta."""
    invalid_match = {
        key: value for key, value in VALID_MATCH.items() if key != "home_team"
    }

    with pytest.raises(ValueError, match="home_team"):
        validate_match(invalid_match)


def test_validate_match_rejects_equal_team_names() -> None:
    """Rejeita equipas com o mesmo nome."""
    invalid_match = {**VALID_MATCH, "away_team": "Benfica"}

    with pytest.raises(ValueError, match="home_team and away_team"):
        validate_match(invalid_match)


def test_validate_match_rejects_invalid_status() -> None:
    """Rejeita partidas cujo estado não é finalizado."""
    invalid_match = {**VALID_MATCH, "status": "scheduled"}

    with pytest.raises(ValueError, match="status"):
        validate_match(invalid_match)


def test_transform_match_calculates_draw_result() -> None:
    """Calcula golos, diferença e vencedor para um empate."""
    original = {**VALID_MATCH, "home_goals": 2, "away_goals": 2}

    transformed = transform_match(original)

    assert transformed["total_goals"] == 4
    assert transformed["goal_difference"] == 0
    assert transformed["winner"] == "draw"
    assert original == {
        "match_id": 101,
        "home_team": "Benfica",
        "away_team": "Porto",
        "home_goals": 2,
        "away_goals": 2,
        "status": "finished",
    }


def test_transform_match_returns_home_away_and_draw_results() -> None:
    """Confirma os três estados possíveis de vencedor."""
    home_result = transform_match({**VALID_MATCH, "home_goals": 3, "away_goals": 1})
    away_result = transform_match({**VALID_MATCH, "home_goals": 1, "away_goals": 3})
    draw_result = transform_match({**VALID_MATCH, "home_goals": 2, "away_goals": 2})

    assert home_result["winner"] == "home"
    assert away_result["winner"] == "away"
    assert draw_result["winner"] == "draw"


def test_run_etl_writes_summary_output(tmp_path) -> None:
    """Executa o pipeline completo e grava um ficheiro de resultado."""
    input_path = tmp_path / "matches.json"
    output_path = tmp_path / "results" / "matches_summary.json"
    payload = [
        VALID_MATCH,
        {
            **VALID_MATCH,
            "match_id": 102,
            "home_team": "Sporting",
            "away_team": "Braga",
            "home_goals": 1,
            "away_goals": 1,
        },
    ]
    input_path.write_text(json.dumps(payload), encoding="utf-8")

    result = run_etl(input_path, output_path)

    assert len(result) == 2
    assert output_path.exists()
    assert json.loads(output_path.read_text(encoding="utf-8"))[0]["winner"] == "home"


def test_extract_matches_rejects_invalid_json(tmp_path) -> None:
    """Levanta erro para JSON malformado."""
    input_path = tmp_path / "broken.json"
    input_path.write_text("{invalid json", encoding="utf-8")

    with pytest.raises(ValueError, match="JSON"):
        extract_matches(input_path)


def test_extract_matches_rejects_non_list_json(tmp_path) -> None:
    """Rejeita uma estrutura de JSON que não seja uma lista."""
    input_path = tmp_path / "matches.json"
    input_path.write_text(json.dumps({"match_id": 1}), encoding="utf-8")

    with pytest.raises(ValueError, match="list of matches"):
        extract_matches(input_path)


def test_extract_matches_rejects_non_object_items(tmp_path) -> None:
    """Rejeita elementos de lista que não são dicionários."""
    input_path = tmp_path / "matches.json"
    input_path.write_text(json.dumps(["not a match", VALID_MATCH]), encoding="utf-8")

    with pytest.raises(ValueError, match="object"):
        extract_matches(input_path)


def test_extract_matches_rejects_missing_file(tmp_path) -> None:
    """Rejeita um ficheiro de entrada inexistente."""
    input_path = tmp_path / "missing.json"

    with pytest.raises(FileNotFoundError):
        extract_matches(input_path)


def test_extract_matches_rejects_duplicate_match_id(tmp_path) -> None:
    """Rejeita IDs duplicados no mesmo ficheiro."""
    input_path = tmp_path / "matches.json"
    payload = [VALID_MATCH, {**VALID_MATCH, "match_id": 101, "home_goals": 0}]
    input_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate match_id"):
        extract_matches(input_path)


def test_run_etl_does_not_create_output_for_invalid_input(tmp_path) -> None:
    """Não produz ficheiro parcial quando a entrada é inválida."""
    input_path = tmp_path / "broken.json"
    input_path.write_text("{invalid json", encoding="utf-8")
    output_path = tmp_path / "results" / "summary.json"

    with pytest.raises(ValueError, match="JSON"):
        run_etl(input_path, output_path)

    assert not output_path.exists()


def test_load_results_rejects_invalid_output_path(tmp_path) -> None:
    """Rejeita caminhos de saída que apontam para um ficheiro em vez de diretório."""
    invalid_parent = tmp_path / "not_a_dir"
    invalid_parent.write_text("x", encoding="utf-8")
    output_path = invalid_parent / "summary.json"

    with pytest.raises(OSError):
        load_results([VALID_MATCH], output_path)


def test_main_exits_on_invalid_input(tmp_path, capsys) -> None:
    """O CLI termina com erro quando a entrada não é válida."""
    invalid_path = tmp_path / "broken.json"
    invalid_path.write_text("{invalid json", encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        main(["--input", str(invalid_path)])

    assert exc.value.code == 1
    assert "Erro no pipeline ETL" in capsys.readouterr().err


def test_match_id_invalid_value() -> None:
    """Rejeita um match_id inválido mesmo que seja positivo em aparência."""
    invalid_match = {**VALID_MATCH, "match_id": 0}

    with pytest.raises(ValueError, match="match_id"):
        validate_match(invalid_match)
