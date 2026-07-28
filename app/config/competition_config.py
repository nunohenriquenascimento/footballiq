import json
from pathlib import Path
from typing import Any


CONFIG_DIRECTORY = Path("data/raw/config")


def load_competition_config(filename: str) -> dict[str, Any]:
    """
    Carrega a configuração de uma competição a partir de um ficheiro JSON.
    """

    config_path = CONFIG_DIRECTORY / filename

    if not config_path.exists():
        raise FileNotFoundError(
            f"Ficheiro de configuração não encontrado: {config_path}"
        )

    with config_path.open(
        mode="r",
        encoding="utf-8",
    ) as file:
        return json.load(file)