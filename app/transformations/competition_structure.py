from typing import Any


def normalize_competition_structure(
    config: dict[str, Any],
) -> dict[str, Any]:
    """
    Junta várias páginas da FPF numa única competição interna.
    """

    competition = config["competition"]
    phases: dict[int, dict[str, Any]] = {}

    for external_competition in config["external_competitions"]:
        fpf_competition_id = external_competition["competition_id"]

        for section in external_competition["sections"]:
            phase_order = section["phase_order"]

            if phase_order not in phases:
                phases[phase_order] = {
                    "phase_order": phase_order,
                    "phase_name": section["phase_name"],
                    "groups": [],
                }

            phases[phase_order]["groups"].append(
                {
                    "group_name": section["group_name"],
                    "competition_level": section["competition_level"],
                    "fpf_competition_id": fpf_competition_id,
                }
            )

    ordered_phases = sorted(
        phases.values(),
        key=lambda phase: phase["phase_order"],
    )

    for phase in ordered_phases:
        phase["groups"] = sorted(
            phase["groups"],
            key=lambda group: (
                group["competition_level"],
                group["group_name"],
            ),
        )

    return {
        "internal_id": competition["internal_id"],
        "name": competition["name"],
        "association_id": competition["association_id"],
        "season_id": competition["season_id"],
        "season_name": competition["season_name"],
        "phases": ordered_phases,
    }