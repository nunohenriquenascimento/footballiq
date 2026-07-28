import json

from app.config.competition_config import load_competition_config
from app.transformations.competition_structure import (
    normalize_competition_structure,
)


def main() -> None:
    config = load_competition_config(
        "sub16_fdm_2025_2026.json"
    )

    normalized_competition = normalize_competition_structure(
        config
    )

    print(
        json.dumps(
            normalized_competition,
            ensure_ascii=False,
            indent=4,
        )
    )


if __name__ == "__main__":
    main()