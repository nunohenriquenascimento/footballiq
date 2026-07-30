import unittest
from unittest.mock import MagicMock, patch

from app.loaders.competition_importer import (
    CompetitionImportError,
    get_import_action,
    import_competition,
)
from app.models import Competition


COMPETITION_DATA = {
    "internal_id": "liga-sub16-fdm-2025-2026",
    "name": "Liga Futebol Sub-16 FDM",
    "association_id": 226,
    "season_id": 105,
    "season_name": "2025/2026",
}


def _session_with_result(result: Competition | None) -> MagicMock:
    database = MagicMock()
    database.execute.return_value.scalar_one_or_none.return_value = result

    def assign_id(competition: Competition) -> None:
        if competition.id is None:
            competition.id = 1

    database.refresh.side_effect = assign_id
    return database


class CompetitionImporterTests(unittest.TestCase):
    def test_creates_new_competition(self) -> None:
        database = _session_with_result(None)
        with patch(
            "app.loaders.competition_importer.SessionLocal",
            return_value=database,
        ):
            competition = import_competition(COMPETITION_DATA)

        database.add.assert_called_once_with(competition)
        database.commit.assert_called_once_with()
        database.rollback.assert_not_called()
        database.close.assert_called_once_with()
        self.assertEqual(get_import_action(competition), "created")
        self.assertEqual(competition.internal_id, COMPETITION_DATA["internal_id"])

    def test_updates_existing_competition(self) -> None:
        existing = Competition(
            id=7,
            internal_id=COMPETITION_DATA["internal_id"],
            name="Nome anterior",
            association_id=1,
            season_id=1,
            season_name=None,
        )
        database = _session_with_result(existing)
        with patch(
            "app.loaders.competition_importer.SessionLocal",
            return_value=database,
        ):
            competition = import_competition(COMPETITION_DATA)

        database.add.assert_not_called()
        database.commit.assert_called_once_with()
        self.assertIs(competition, existing)
        self.assertEqual(get_import_action(competition), "updated")
        self.assertEqual(competition.name, COMPETITION_DATA["name"])
        self.assertEqual(
            competition.association_id,
            COMPETITION_DATA["association_id"],
        )
        self.assertEqual(competition.season_id, COMPETITION_DATA["season_id"])
        self.assertEqual(competition.season_name, "2025/2026")

    def test_repeated_execution_does_not_duplicate(self) -> None:
        database = _session_with_result(None)
        with patch(
            "app.loaders.competition_importer.SessionLocal",
            return_value=database,
        ):
            first = import_competition(COMPETITION_DATA)

        database.reset_mock()
        database.execute.return_value.scalar_one_or_none.return_value = first
        with patch(
            "app.loaders.competition_importer.SessionLocal",
            return_value=database,
        ):
            second = import_competition(COMPETITION_DATA)

        database.add.assert_not_called()
        database.commit.assert_called_once_with()
        self.assertIs(second, first)
        self.assertEqual(get_import_action(second), "updated")

    def test_rolls_back_when_commit_fails(self) -> None:
        database = _session_with_result(None)
        database.commit.side_effect = RuntimeError("falha simulada")

        with patch(
            "app.loaders.competition_importer.SessionLocal",
            return_value=database,
        ):
            with self.assertRaisesRegex(
                CompetitionImportError,
                "falha simulada",
            ):
                import_competition(COMPETITION_DATA)

        database.rollback.assert_called_once_with()
        database.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
