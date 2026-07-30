import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database.session import SessionLocal  # noqa: E402
from app.loaders.competition_structure_importer import (  # noqa: E402
    import_competition_structure,
)
from app.models import Competition, Phase  # noqa: E402


COMPETITION_STRUCTURE = {
    "internal_id": "liga-sub16-fdm-2025-2026",
    "name": "Liga Futebol Sub-16 FDM",
    "association_id": 226,
    "season_id": 105,
    "season_name": "2025/2026",
    "phases": [
        {
            "phase_order": 1,
            "phase_name": "1.ª Fase",
            "groups": [
                {
                    "group_name": "Grupo A",
                    "competition_level": 1,
                    "fpf_competition_id": 28712,
                },
                {
                    "group_name": "Grupo B",
                    "competition_level": 1,
                    "fpf_competition_id": 28707,
                },
                {
                    "group_name": "Grupo C",
                    "competition_level": 1,
                    "fpf_competition_id": 28712,
                },
            ],
        },
        {
            "phase_order": 2,
            "phase_name": "2.ª Fase",
            "groups": [
                {
                    "group_name": "2.ª Divisão",
                    "competition_level": 2,
                    "fpf_competition_id": 28707,
                },
                {
                    "group_name": "Fase de Campeão",
                    "competition_level": 1,
                    "fpf_competition_id": 28712,
                },
            ],
        },
    ],
}


def _print_persisted_structure(internal_id: str) -> None:
    database = SessionLocal()
    try:
        competition = database.execute(
            select(Competition)
            .where(Competition.internal_id == internal_id)
            .options(
                selectinload(Competition.phases).selectinload(
                    Phase.groups
                )
            )
        ).scalar_one()

        print(
            f"Competition: {competition.internal_id} — "
            f"{competition.name}"
        )
        for phase in sorted(
            competition.phases,
            key=lambda item: item.phase_order,
        ):
            print(
                f"- Fase {phase.phase_order}: {phase.phase_name}"
            )
            for group in sorted(
                phase.groups,
                key=lambda item: item.group_name,
            ):
                print(
                    f"  - {group.group_name}: "
                    f"nível={group.competition_level}, "
                    f"fpf_competition_id={group.fpf_competition_id}"
                )
    finally:
        database.close()


def main() -> int:
    try:
        summary = import_competition_structure(
            COMPETITION_STRUCTURE
        )
        print("Resumo:")
        for field, value in summary.items():
            print(f"- {field}: {value}")
        print("Estrutura persistida:")
        _print_persisted_structure(
            COMPETITION_STRUCTURE["internal_id"]
        )
        return 0
    except Exception as exc:
        print(
            f"Erro ao importar a estrutura da competição: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
