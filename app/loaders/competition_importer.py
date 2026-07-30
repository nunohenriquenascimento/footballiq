from typing import Any

from sqlalchemy import select

from app.database.session import SessionLocal
from app.models import Competition


REQUIRED_FIELDS = (
    "internal_id",
    "name",
    "association_id",
    "season_id",
)
IMPORT_ACTION_ATTRIBUTE = "_competition_import_action"


class CompetitionImportError(RuntimeError):
    """Erro ao validar ou persistir uma competição."""


def _validate_competition_data(data: dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise ValueError("Os dados da competição devem ser um dicionário.")

    missing_fields = [
        field
        for field in REQUIRED_FIELDS
        if field not in data or data[field] is None
    ]
    if missing_fields:
        raise ValueError(
            "Campos obrigatórios em falta: "
            + ", ".join(missing_fields)
            + "."
        )

    for field in ("internal_id", "name"):
        value = data[field]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"O campo {field!r} deve ser uma string não vazia."
            )

    for field in ("association_id", "season_id"):
        value = data[field]
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or value <= 0
        ):
            raise ValueError(
                f"O campo {field!r} deve ser um inteiro positivo."
            )

    season_name = data.get("season_name")
    if season_name is not None and (
        not isinstance(season_name, str) or not season_name.strip()
    ):
        raise ValueError(
            "O campo 'season_name' deve ser uma string não vazia "
            "ou null."
        )


def import_competition(data: dict[str, Any]) -> Competition:
    """Cria ou atualiza uma competição identificada por internal_id."""

    database = SessionLocal()
    try:
        _validate_competition_data(data)

        internal_id = data["internal_id"].strip()
        competition = database.execute(
            select(Competition).where(
                Competition.internal_id == internal_id
            )
        ).scalar_one_or_none()

        if competition is None:
            competition = Competition(internal_id=internal_id)
            database.add(competition)
            import_action = "created"
        else:
            import_action = "updated"

        competition.name = data["name"].strip()
        competition.association_id = data["association_id"]
        competition.season_id = data["season_id"]
        season_name = data.get("season_name")
        competition.season_name = (
            season_name.strip()
            if isinstance(season_name, str)
            else None
        )

        database.commit()
        database.refresh(competition)
        setattr(
            competition,
            IMPORT_ACTION_ATTRIBUTE,
            import_action,
        )
        return competition
    except Exception as exc:
        database.rollback()
        if isinstance(exc, CompetitionImportError):
            raise
        raise CompetitionImportError(
            f"Não foi possível importar a competição: {exc}"
        ) from exc
    finally:
        database.close()


def get_import_action(competition: Competition) -> str:
    """Devolve a ação realizada na importação atual."""

    action = getattr(competition, IMPORT_ACTION_ATTRIBUTE, None)
    if action not in {"created", "updated"}:
        raise ValueError(
            "O objeto não contém informação sobre a importação."
        )
    return action
