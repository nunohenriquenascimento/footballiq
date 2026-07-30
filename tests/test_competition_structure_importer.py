import copy
import unittest
from unittest.mock import MagicMock, patch

from app.loaders.competition_structure_importer import (
    CompetitionStructureImportError,
    import_competition_structure,
)
from app.models import Competition, CompetitionGroup, Phase


STRUCTURE = {
    "internal_id": "liga-sub16-fdm-2025-2026",
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


def _result(value: object) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _competition() -> Competition:
    return Competition(
        id=1,
        internal_id=STRUCTURE["internal_id"],
        name="Liga Futebol Sub-16 FDM",
        association_id=226,
        season_id=105,
        season_name="2025/2026",
    )


def _new_structure_session() -> MagicMock:
    database = MagicMock()
    database.execute.side_effect = [
        _result(_competition()),
        _result(None),
        _result(None),
        _result(None),
        _result(None),
        _result(None),
        _result(None),
        _result(None),
    ]
    next_phase_id = iter((10, 20))

    def assign_phase_id() -> None:
        phase = database.add.call_args.args[0]
        if isinstance(phase, Phase) and phase.id is None:
            phase.id = next(next_phase_id)

    database.flush.side_effect = assign_phase_id
    return database


def _existing_structure() -> tuple[list[object], list[Phase], list[CompetitionGroup]]:
    phases = [
        Phase(
            id=10,
            competition_id=1,
            phase_order=1,
            phase_name="Nome antigo 1",
        ),
        Phase(
            id=20,
            competition_id=1,
            phase_order=2,
            phase_name="Nome antigo 2",
        ),
    ]
    groups = [
        CompetitionGroup(
            id=index,
            phase_id=phase_id,
            group_name=group_data["group_name"],
            competition_level=99,
            fpf_competition_id=99999,
        )
        for index, (phase_id, group_data) in enumerate(
            [
                (10, STRUCTURE["phases"][0]["groups"][0]),
                (10, STRUCTURE["phases"][0]["groups"][1]),
                (10, STRUCTURE["phases"][0]["groups"][2]),
                (20, STRUCTURE["phases"][1]["groups"][0]),
                (20, STRUCTURE["phases"][1]["groups"][1]),
            ],
            start=1,
        )
    ]
    results: list[object] = [
        _competition(),
        phases[0],
        groups[0],
        groups[1],
        groups[2],
        phases[1],
        groups[3],
        groups[4],
    ]
    return results, phases, groups


def _session_with_results(values: list[object]) -> MagicMock:
    database = MagicMock()
    database.execute.side_effect = [_result(value) for value in values]
    return database


class CompetitionStructureImporterTests(unittest.TestCase):
    def _import_with(self, database: MagicMock) -> dict[str, int]:
        with patch(
            "app.loaders.competition_structure_importer.SessionLocal",
            return_value=database,
        ):
            return import_competition_structure(copy.deepcopy(STRUCTURE))

    def test_creates_two_phases(self) -> None:
        database = _new_structure_session()
        summary = self._import_with(database)
        phases = [
            call.args[0]
            for call in database.add.call_args_list
            if isinstance(call.args[0], Phase)
        ]
        self.assertEqual(summary["phases_created"], 2)
        self.assertEqual(len(phases), 2)

    def test_creates_five_groups(self) -> None:
        database = _new_structure_session()
        summary = self._import_with(database)
        groups = [
            call.args[0]
            for call in database.add.call_args_list
            if isinstance(call.args[0], CompetitionGroup)
        ]
        self.assertEqual(summary["groups_created"], 5)
        self.assertEqual(len(groups), 5)

    def test_updates_phase_name(self) -> None:
        values, phases, _ = _existing_structure()
        summary = self._import_with(_session_with_results(values))
        self.assertEqual(summary["phases_updated"], 2)
        self.assertEqual(phases[0].phase_name, "1.ª Fase")
        self.assertEqual(phases[1].phase_name, "2.ª Fase")

    def test_updates_competition_level(self) -> None:
        values, _, groups = _existing_structure()
        self._import_with(_session_with_results(values))
        self.assertEqual(
            [group.competition_level for group in groups],
            [1, 1, 1, 2, 1],
        )

    def test_updates_fpf_competition_id(self) -> None:
        values, _, groups = _existing_structure()
        self._import_with(_session_with_results(values))
        self.assertEqual(
            [group.fpf_competition_id for group in groups],
            [28712, 28707, 28712, 28707, 28712],
        )

    def test_repeated_import_does_not_add_duplicates(self) -> None:
        values, _, _ = _existing_structure()
        database = _session_with_results(values)
        summary = self._import_with(database)
        database.add.assert_not_called()
        self.assertEqual(summary["phases_created"], 0)
        self.assertEqual(summary["groups_created"], 0)
        self.assertEqual(summary["phases_updated"], 2)
        self.assertEqual(summary["groups_updated"], 5)

    def test_fails_when_competition_does_not_exist(self) -> None:
        database = _session_with_results([None])
        with self.assertRaisesRegex(
            CompetitionStructureImportError,
            "Competition não encontrada",
        ):
            self._import_with(database)
        database.commit.assert_not_called()
        database.rollback.assert_called_once_with()

    def test_rolls_back_on_error(self) -> None:
        database = _new_structure_session()
        database.commit.side_effect = RuntimeError("falha simulada")
        with self.assertRaisesRegex(
            CompetitionStructureImportError,
            "falha simulada",
        ):
            self._import_with(database)
        database.rollback.assert_called_once_with()

    def test_closes_session_on_success(self) -> None:
        database = _new_structure_session()
        self._import_with(database)
        database.commit.assert_called_once_with()
        database.rollback.assert_not_called()
        database.close.assert_called_once_with()

    def test_closes_session_on_error(self) -> None:
        database = _session_with_results([None])
        with self.assertRaises(CompetitionStructureImportError):
            self._import_with(database)
        database.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
