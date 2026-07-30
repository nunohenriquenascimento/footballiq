import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.loaders.competition_importer import (  # noqa: E402
    get_import_action,
    import_competition,
)


COMPETITION_DATA = {
    "internal_id": "liga-sub16-fdm-2025-2026",
    "name": "Liga Futebol Sub-16 FDM",
    "association_id": 226,
    "season_id": 105,
    "season_name": "2025/2026",
}


def main() -> int:
    try:
        competition = import_competition(COMPETITION_DATA)
        action = get_import_action(competition)
    except Exception as exc:
        print(
            f"Erro ao importar a competição: {exc}",
            file=sys.stderr,
        )
        return 1

    action_label = "criado" if action == "created" else "atualizado"
    print(f"Registo {action_label} com sucesso.")
    print(f"id: {competition.id}")
    print(f"internal_id: {competition.internal_id}")
    print(f"name: {competition.name}")
    print(f"season_name: {competition.season_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
