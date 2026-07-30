from typing import Any

from sqlalchemy import select

from app.database.session import SessionLocal
from app.models import Competition, CompetitionGroup, Phase


class CompetitionStructureImportError(RuntimeError):
    """Erro ao validar ou persistir a estrutura competitiva."""


def _positive_integer(value: Any, field: str) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value <= 0
    ):
        raise ValueError(f"O campo {field!r} deve ser um inteiro positivo.")
    return value


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"O campo {field!r} deve ser uma string não vazia."
        )
    return value.strip()


def _validate_structure(data: dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise ValueError("A estrutura deve ser um dicionário.")

    _required_text(data.get("internal_id"), "internal_id")
    phases = data.get("phases")
    if not isinstance(phases, list):
        raise ValueError("O campo 'phases' deve ser uma lista.")

    phase_orders: set[int] = set()
    for phase_index, phase_data in enumerate(phases):
        if not isinstance(phase_data, dict):
            raise ValueError(
                f"A fase na posição {phase_index} deve ser um objeto."
            )
        phase_order = _positive_integer(
            phase_data.get("phase_order"),
            "phase_order",
        )
        if phase_order in phase_orders:
            raise ValueError(
                f"phase_order duplicado na estrutura: {phase_order}."
            )
        phase_orders.add(phase_order)
        _required_text(phase_data.get("phase_name"), "phase_name")

        groups = phase_data.get("groups")
        if not isinstance(groups, list):
            raise ValueError("O campo 'groups' deve ser uma lista.")
        group_names: set[str] = set()
        for group_index, group_data in enumerate(groups):
            if not isinstance(group_data, dict):
                raise ValueError(
                    "O grupo na posição "
                    f"{group_index} da fase {phase_order} "
                    "deve ser um objeto."
                )
            group_name = _required_text(
                group_data.get("group_name"),
                "group_name",
            )
            if group_name in group_names:
                raise ValueError(
                    f"group_name duplicado na fase {phase_order}: "
                    f"{group_name!r}."
                )
            group_names.add(group_name)
            _positive_integer(
                group_data.get("competition_level"),
                "competition_level",
            )
            _positive_integer(
                group_data.get("fpf_competition_id"),
                "fpf_competition_id",
            )


def import_competition_structure(
    data: dict[str, Any],
) -> dict[str, int]:
    """Cria ou atualiza fases e grupos sem remover dados existentes."""

    database = SessionLocal()
    summary = {
        "phases_created": 0,
        "phases_updated": 0,
        "groups_created": 0,
        "groups_updated": 0,
    }

    try:
        _validate_structure(data)
        internal_id = data["internal_id"].strip()
        competition = database.execute(
            select(Competition).where(
                Competition.internal_id == internal_id
            )
        ).scalar_one_or_none()
        if competition is None:
            raise ValueError(
                "Competition não encontrada para internal_id "
                f"{internal_id!r}."
            )

        for phase_data in data["phases"]:
            phase_order = phase_data["phase_order"]
            phase = database.execute(
                select(Phase).where(
                    Phase.competition_id == competition.id,
                    Phase.phase_order == phase_order,
                )
            ).scalar_one_or_none()

            if phase is None:
                phase = Phase(
                    competition_id=competition.id,
                    phase_order=phase_order,
                    phase_name=phase_data["phase_name"].strip(),
                )
                database.add(phase)
                database.flush()
                summary["phases_created"] += 1
            else:
                phase.phase_name = phase_data["phase_name"].strip()
                summary["phases_updated"] += 1

            for group_data in phase_data["groups"]:
                group_name = group_data["group_name"].strip()
                group = database.execute(
                    select(CompetitionGroup).where(
                        CompetitionGroup.phase_id == phase.id,
                        CompetitionGroup.group_name == group_name,
                    )
                ).scalar_one_or_none()

                if group is None:
                    group = CompetitionGroup(
                        phase_id=phase.id,
                        group_name=group_name,
                        competition_level=group_data[
                            "competition_level"
                        ],
                        fpf_competition_id=group_data[
                            "fpf_competition_id"
                        ],
                    )
                    database.add(group)
                    summary["groups_created"] += 1
                else:
                    group.competition_level = group_data[
                        "competition_level"
                    ]
                    group.fpf_competition_id = group_data[
                        "fpf_competition_id"
                    ]
                    summary["groups_updated"] += 1

        database.commit()
        return summary
    except Exception as exc:
        database.rollback()
        if isinstance(exc, CompetitionStructureImportError):
            raise
        raise CompetitionStructureImportError(
            "Não foi possível importar a estrutura da competição: "
            f"{exc}"
        ) from exc
    finally:
        database.close()
