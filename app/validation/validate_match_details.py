import json
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any


INPUT_PATH = Path(
    "data/processed/match_details_sub16_fdm_2025_2026.json"
)
REPORT_PATH = Path("reports/match_details_validation_report.md")
EXPECTED_MATCHES = 92
SIDES = ("home", "away")
PHASE_ORDER = {
    "first_half": 0,
    "half_time": 1,
    "second_half": 2,
    "post_match": 3,
}
TECHNICAL_CLASSIFICATIONS = {"parser_error", "structural_error"}
ISSUE_CLASSIFICATIONS = (
    "parser_error",
    "structural_error",
    "source_inconsistency",
    "data_quality_warning",
)

COMPLETENESS_FIELDS = {
    "match_id": ("match_id",),
    "fixture_id": ("fixture_id",),
    "serie_id": ("serie_id",),
    "round": ("round",),
    "competition.competition_id": (
        "competition",
        "competition_id",
    ),
    "competition.season_id": ("competition", "season_id"),
    "competition.name": ("competition", "name"),
    "scheduled_at.date": ("scheduled_at", "date"),
    "scheduled_at.time": ("scheduled_at", "time"),
    "venue.name": ("venue", "name"),
    "teams.home.name": ("teams", "home", "name"),
    "teams.home.score": ("teams", "home", "score"),
    "teams.away.name": ("teams", "away", "name"),
    "teams.away.score": ("teams", "away", "score"),
    "lineups.home.starters": ("lineups", "home", "starters"),
    "lineups.home.substitutes": (
        "lineups",
        "home",
        "substitutes",
    ),
    "lineups.home.staff": ("lineups", "home", "staff"),
    "lineups.away.starters": ("lineups", "away", "starters"),
    "lineups.away.substitutes": (
        "lineups",
        "away",
        "substitutes",
    ),
    "lineups.away.staff": ("lineups", "away", "staff"),
    "officials": ("officials",),
    "events": ("events",),
    "periods": ("periods",),
    "source.url": ("source", "url"),
}


def load_match_details(path: Path = INPUT_PATH) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(
            f"O ficheiro de detalhes não existe: {path}"
        )
    if path.stat().st_size == 0:
        raise ValueError(
            f"O ficheiro de detalhes está vazio: {path}"
        )

    try:
        records = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"O ficheiro contém JSON inválido: {path}"
        ) from exc

    if not isinstance(records, list):
        raise ValueError("O JSON de detalhes deve conter uma lista.")
    return records


def _normalise_name(value: str | None) -> str:
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    ).casefold().strip()


def _nested_value(record: dict, path: tuple[str, ...]) -> Any:
    value: Any = record
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def _is_complete(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _player_key(player: dict) -> tuple[str, Any] | None:
    player_id = player.get("player_id")
    if isinstance(player_id, int):
        return "id", player_id
    name = _normalise_name(player.get("name"))
    return ("name", name) if name else None


def _team_players(match: dict, side: str) -> list[dict]:
    team = _nested_value(match, ("lineups", side))
    if not isinstance(team, dict):
        return []
    starters = team.get("starters", [])
    substitutes = team.get("substitutes", [])
    return [
        player
        for player in starters + substitutes
        if isinstance(player, dict)
    ]


def _player_indexes(match: dict) -> dict[str, dict]:
    indexes = {
        "home": {"keys": set(), "names": set()},
        "away": {"keys": set(), "names": set()},
    }
    for side in SIDES:
        for player in _team_players(match, side):
            key = _player_key(player)
            if key is not None:
                indexes[side]["keys"].add(key)
            name = _normalise_name(player.get("name"))
            if name:
                indexes[side]["names"].add(name)
    return indexes


def _event_player_exists(
    event: dict,
    indexes: dict[str, dict],
) -> bool:
    side = event.get("team_side")
    sides = (side,) if side in SIDES else SIDES
    player_id = event.get("player_id")
    player_name = _normalise_name(event.get("player_name"))

    for candidate_side in sides:
        if (
            isinstance(player_id, int)
            and ("id", player_id)
            in indexes[candidate_side]["keys"]
        ):
            return True
        if (
            player_name
            and player_name in indexes[candidate_side]["names"]
        ):
            return True
    return False


def _add_issue(
    issues: list[dict],
    classification: str,
    match_id: Any,
    check: str,
    message: str,
    *,
    evidence: str | None = None,
    source_value_preserved: bool = False,
) -> None:
    if classification not in ISSUE_CLASSIFICATIONS:
        raise ValueError(
            f"Classificação de validação inválida: {classification}"
        )
    issues.append(
        {
            "classification": classification,
            "match_id": match_id,
            "check": check,
            "message": message,
            "evidence": evidence,
            "source_value_preserved": source_value_preserved,
        }
    )


def _validate_score(
    match: dict,
    match_id: Any,
    issues: list[dict],
) -> None:
    home_score = _nested_value(match, ("teams", "home", "score"))
    away_score = _nested_value(match, ("teams", "away", "score"))
    scores = (home_score, away_score)

    if (home_score is None) != (away_score is None):
        _add_issue(
            issues,
            "structural_error",
            match_id,
            "score",
            "Só uma das equipas tem resultado.",
        )
        return
    if home_score is None:
        _add_issue(
            issues,
            "data_quality_warning",
            match_id,
            "score",
            "Resultado não disponível.",
        )
        return
    if any(
        not isinstance(score, int) or score < 0 for score in scores
    ):
        _add_issue(
            issues,
            "structural_error",
            match_id,
            "score",
            f"Resultado inválido: {home_score}-{away_score}.",
        )
        return

    goal_events = [
        event
        for event in match.get("events", [])
        if isinstance(event, dict) and event.get("type") == "goal"
    ]
    last_scored_goal_index = next(
        (
            index
            for index in range(len(goal_events) - 1, -1, -1)
            if isinstance(goal_events[index].get("score"), dict)
        ),
        None,
    )
    if last_scored_goal_index is None:
        reconciled_score = {"home": 0, "away": 0}
        supplemental_goals = goal_events
    else:
        reconciled_score = dict(
            goal_events[last_scored_goal_index]["score"]
        )
        supplemental_goals = goal_events[last_scored_goal_index + 1 :]

    unresolved_goals = [
        event
        for event in supplemental_goals
        if event.get("team_side") not in SIDES
    ]
    if unresolved_goals:
        _add_issue(
            issues,
            "data_quality_warning",
            match_id,
            "score",
            f"{len(unresolved_goals)} golo(s) sem equipa determinável; "
            "a reconciliação do resultado não é segura.",
            evidence=(
                "Os eventos não contêm team_side=home/away; "
                "nenhuma associação foi inventada."
            ),
        )
        return

    for event in supplemental_goals:
        side = event["team_side"]
        reconciled_score[side] = reconciled_score.get(side, 0) + 1

    if (
        reconciled_score.get("home") != home_score
        or reconciled_score.get("away") != away_score
    ):
        _add_issue(
            issues,
            "source_inconsistency",
            match_id,
            "score",
            "O resultado publicado não coincide com a contagem de "
            "todos os eventos de golo.",
            evidence=(
                f"Resultado FPF: {home_score}-{away_score}; "
                "resultado reconstruído pelos eventos: "
                f"{reconciled_score.get('home')}-"
                f"{reconciled_score.get('away')}; "
                f"eventos de golo publicados: {len(goal_events)}."
            ),
            source_value_preserved=True,
        )


def _validate_lineups(
    match: dict,
    match_id: Any,
    issues: list[dict],
) -> None:
    for side in SIDES:
        starters = _nested_value(
            match,
            ("lineups", side, "starters"),
        )
        if not isinstance(starters, list):
            _add_issue(
                issues,
                "structural_error",
                match_id,
                "lineup",
                f"Titulares de {side} não são uma lista.",
            )
            continue
        if len(starters) != 11:
            _add_issue(
                issues,
                "source_inconsistency",
                match_id,
                "lineup",
                f"{side} tem {len(starters)} titulares; ideal: 11.",
                evidence=(
                    "A secção Equipas Iniciais da FPF contém "
                    f"{len(starters)} jogadores para {side}."
                ),
                source_value_preserved=True,
            )

        seen: dict[tuple[str, Any], int] = defaultdict(int)
        for player in _team_players(match, side):
            key = _player_key(player)
            if key is not None:
                seen[key] += 1
        duplicates = [
            f"{kind}:{value}"
            for (kind, value), count in seen.items()
            if count > 1
        ]
        if duplicates:
            _add_issue(
                issues,
                "structural_error",
                match_id,
                "duplicate_player",
                f"Jogadores repetidos em {side}: "
                + ", ".join(duplicates),
            )


def _validate_substitutions(
    match: dict,
    match_id: Any,
    indexes: dict[str, dict],
    issues: list[dict],
) -> None:
    for event in match.get("events", []):
        if (
            not isinstance(event, dict)
            or event.get("type") != "substitution"
        ):
            continue

        side = event.get("team_side")
        player_in = event.get("player_in")
        player_out = event.get("player_out")
        if side not in SIDES:
            _add_issue(
                issues,
                "parser_error",
                match_id,
                "substitution",
                "Substituição sem equipa válida.",
            )
            continue
        if not isinstance(player_in, dict) or not isinstance(
            player_out,
            dict,
        ):
            _add_issue(
                issues,
                "structural_error",
                match_id,
                "substitution",
                "Substituição sem jogador de entrada ou saída.",
            )
            continue

        in_key = _player_key(player_in)
        out_key = _player_key(player_out)
        if in_key is None or out_key is None:
            _add_issue(
                issues,
                "parser_error",
                match_id,
                "substitution",
                "Substituição contém jogador sem identificação.",
            )
        elif in_key == out_key:
            _add_issue(
                issues,
                "source_inconsistency",
                match_id,
                "substitution",
                "O mesmo jogador entra e sai.",
                evidence=(
                    "O evento publicado contém a mesma identificação "
                    "nos campos de entrada e saída."
                ),
                source_value_preserved=True,
            )

        for direction, player in (
            ("entrada", player_in),
            ("saída", player_out),
        ):
            key = _player_key(player)
            name = _normalise_name(player.get("name"))
            if (
                key not in indexes[side]["keys"]
                and name not in indexes[side]["names"]
            ):
                opposite_side = "away" if side == "home" else "home"
                exists_on_opposite_side = (
                    key in indexes[opposite_side]["keys"]
                    or name in indexes[opposite_side]["names"]
                )
                _add_issue(
                    issues,
                    (
                        "source_inconsistency"
                        if exists_on_opposite_side
                        else "parser_error"
                    ),
                    match_id,
                    "substitution",
                    f"Jogador de {direction} não existe no plantel "
                    f"de {side}: {player.get('name')!r}.",
                    evidence=(
                        f"O jogador está publicado no plantel de "
                        f"{opposite_side}, mas a substituição está "
                        f"associada a {side}."
                        if exists_on_opposite_side
                        else "O jogador não foi encontrado em nenhum "
                        "dos dois plantéis normalizados."
                    ),
                    source_value_preserved=exists_on_opposite_side,
                )


def _validate_events(
    match: dict,
    match_id: Any,
    indexes: dict[str, dict],
    issues: list[dict],
) -> None:
    events = match.get("events")
    if not isinstance(events, list):
        _add_issue(
            issues,
            "structural_error",
            match_id,
            "events",
            "Eventos não são uma lista.",
        )
        return

    previous_phase_rank: int | None = None
    previous_timed_key: tuple[int, int, int] | None = None
    previous_timed_phase: str | None = None

    for position, event in enumerate(events):
        if not isinstance(event, dict):
            _add_issue(
                issues,
                "structural_error",
                match_id,
                "events",
                "Evento com estrutura inválida.",
            )
            continue

        minute = event.get("minute")
        added_time = event.get("added_time")
        event_type = event.get("type")
        phase = event.get("phase")
        penalty_without_minute = (
            event_type == "goal"
            and event.get("detail") == "penalty"
            and minute is None
        )
        phase_allows_null_minute = phase in {"half_time", "post_match"}
        minute_is_valid = (
            isinstance(minute, int)
            and not isinstance(minute, bool)
            and minute >= 0
        )

        if (
            minute is None
            and (penalty_without_minute or phase_allows_null_minute)
        ):
            pass
        elif not minute_is_valid:
            _add_issue(
                issues,
                "parser_error",
                match_id,
                "chronology",
                f"Evento {event_type!r} sem minuto válido.",
                evidence=(
                    f"phase={phase!r}, minute={minute!r}, "
                    f"detail={event.get('detail')!r}."
                ),
            )

        if added_time is not None and (
            not isinstance(added_time, int)
            or isinstance(added_time, bool)
            or added_time < 0
        ):
            _add_issue(
                issues,
                "parser_error",
                match_id,
                "chronology",
                f"Evento {event_type!r} com tempo adicional inválido.",
                evidence=f"added_time={added_time!r}.",
            )

        source_section = _normalise_name(event.get("source_section"))
        is_extra_time_section = "prolongamento" in source_section
        phase_rank = (
            PHASE_ORDER["second_half"]
            if is_extra_time_section
            else PHASE_ORDER.get(phase)
        )
        if phase is not None and phase_rank is None:
            _add_issue(
                issues,
                "parser_error",
                match_id,
                "chronology",
                f"Evento {event_type!r} com fase desconhecida.",
                evidence=f"phase={phase!r}.",
            )
        elif phase_rank is not None:
            if (
                previous_phase_rank is not None
                and phase_rank < previous_phase_rank
            ):
                _add_issue(
                    issues,
                    "parser_error",
                    match_id,
                    "chronology",
                    "As fases dos eventos não respeitam a ordem "
                    "first_half, half_time, second_half, post_match.",
                    evidence=(
                        f"Evento na posição {position}: phase={phase!r}."
                    ),
                )
            previous_phase_rank = max(
                phase_rank,
                previous_phase_rank
                if previous_phase_rank is not None
                else phase_rank,
            )

        if phase in {"first_half", "second_half"} and minute_is_valid:
            timed_key = (
                minute,
                added_time if isinstance(added_time, int) else 0,
                position,
            )
            if (
                previous_timed_phase == phase
                and previous_timed_key is not None
                and timed_key < previous_timed_key
                and event_type != "period_end"
            ):
                _add_issue(
                    issues,
                    "parser_error",
                    match_id,
                    "chronology",
                    f"Evento {event_type!r} fora de ordem em {phase}.",
                    evidence=(
                        f"Chave temporal atual "
                        f"({minute}, {added_time or 0}, {position}) "
                        f"é anterior à precedente "
                        f"{previous_timed_key}."
                    ),
                )
            previous_timed_key = timed_key
            previous_timed_phase = phase
        elif phase in {"half_time", "post_match"}:
            previous_timed_key = None
            previous_timed_phase = None

        if event_type in {
            "goal",
            "yellow_card",
            "red_card",
        } and not _event_player_exists(event, indexes):
            _add_issue(
                issues,
                "parser_error",
                match_id,
                "event_player",
                f"{event_type} associado a jogador inexistente: "
                f"{event.get('player_name')!r}.",
            )

    _validate_substitutions(match, match_id, indexes, issues)


def _validate_officials(
    match: dict,
    match_id: Any,
    issues: list[dict],
) -> None:
    officials = match.get("officials")
    if not isinstance(officials, list):
        _add_issue(
            issues,
            "structural_error",
            match_id,
            "officials",
            "Equipa de arbitragem não é uma lista.",
        )
        return

    referees = [
        official
        for official in officials
        if isinstance(official, dict)
        and official.get("role") == "referee"
        and official.get("name")
    ]
    if officials and not referees:
        _add_issue(
            issues,
            "parser_error",
            match_id,
            "referee",
            "Há oficiais, mas não existe árbitro principal.",
        )
    elif not officials:
        _add_issue(
            issues,
            "data_quality_warning",
            match_id,
            "referee",
            "Equipa de arbitragem não disponível.",
        )


def _validate_schedule(
    match: dict,
    match_id: Any,
    issues: list[dict],
) -> None:
    date_value = _nested_value(match, ("scheduled_at", "date"))
    time_value = _nested_value(match, ("scheduled_at", "time"))

    if date_value is None:
        _add_issue(
            issues,
            "parser_error",
            match_id,
            "date",
            "Data inesperadamente nula.",
        )
    else:
        try:
            date.fromisoformat(date_value)
        except (TypeError, ValueError):
            _add_issue(
                issues,
                "parser_error",
                match_id,
                "date",
                f"Data inválida: {date_value!r}.",
            )

    if time_value is None:
        _add_issue(
            issues,
            "data_quality_warning",
            match_id,
            "time",
            "Hora não disponível.",
        )
    else:
        try:
            datetime.strptime(time_value, "%H:%M")
        except (TypeError, ValueError):
            _add_issue(
                issues,
                "parser_error",
                match_id,
                "time",
                f"Hora inválida: {time_value!r}.",
            )


def validate_match_details(matches: list[dict]) -> dict:
    issues: list[dict] = []
    completeness_counts = Counter()
    match_ids = []

    if len(matches) != EXPECTED_MATCHES:
        _add_issue(
            issues,
            "structural_error",
            None,
            "total_matches",
            f"Esperados {EXPECTED_MATCHES} jogos; encontrados "
            f"{len(matches)}.",
        )

    for index, match in enumerate(matches):
        if not isinstance(match, dict):
            _add_issue(
                issues,
                "structural_error",
                None,
                "structure",
                f"Registo {index} não é um objeto.",
            )
            continue

        match_id = match.get("match_id")
        match_ids.append(match_id)
        if not isinstance(match_id, int) or match_id <= 0:
            _add_issue(
                issues,
                "structural_error",
                match_id,
                "match_id",
                "match_id ausente ou inválido.",
            )

        for field, path in COMPLETENESS_FIELDS.items():
            if _is_complete(_nested_value(match, path)):
                completeness_counts[field] += 1

        for side in SIDES:
            team_name = _nested_value(
                match,
                ("teams", side, "name"),
            )
            if not isinstance(team_name, str) or not team_name.strip():
                _add_issue(
                    issues,
                    "structural_error",
                    match_id,
                    "team",
                    f"Equipa {side} ausente.",
                )

        for field, path in (
            ("competition.name", ("competition", "name")),
            ("source.url", ("source", "url")),
        ):
            if not _is_complete(_nested_value(match, path)):
                _add_issue(
                    issues,
                    "structural_error",
                    match_id,
                    "unexpected_null",
                    f"Campo obrigatório nulo: {field}.",
                )

        indexes = _player_indexes(match)
        _validate_score(match, match_id, issues)
        _validate_lineups(match, match_id, issues)
        _validate_events(match, match_id, indexes, issues)
        _validate_officials(match, match_id, issues)
        _validate_schedule(match, match_id, issues)

    duplicate_ids = [
        match_id
        for match_id, count in Counter(match_ids).items()
        if match_id is not None and count > 1
    ]
    for match_id in duplicate_ids:
        _add_issue(
            issues,
            "structural_error",
            match_id,
            "duplicate_match",
            "match_id duplicado no JSON final.",
        )

    total = len(matches)
    completeness = {
        field: {
            "complete": completeness_counts[field],
            "total": total,
            "percentage": (
                round(completeness_counts[field] * 100 / total, 2)
                if total
                else 0.0
            ),
        }
        for field in COMPLETENESS_FIELDS
    }
    problem_matches = sorted(
        {
            issue["match_id"]
            for issue in issues
            if issue["match_id"] is not None
        }
    )
    issues_by_classification = {
        classification: [
            issue
            for issue in issues
            if issue["classification"] == classification
        ]
        for classification in ISSUE_CLASSIFICATIONS
    }
    technical_errors = [
        issue
        for issue in issues
        if issue["classification"] in TECHNICAL_CLASSIFICATIONS
    ]

    return {
        "statistics": {
            "expected_matches": EXPECTED_MATCHES,
            "total_matches": total,
            "unique_match_ids": len(
                {
                    match_id
                    for match_id in match_ids
                    if isinstance(match_id, int)
                }
            ),
            "technical_errors": len(technical_errors),
            **{
                classification: len(classified_issues)
                for classification, classified_issues
                in issues_by_classification.items()
            },
            "problem_matches": len(problem_matches),
        },
        "completeness": completeness,
        "issues": issues,
        **issues_by_classification,
        "problem_matches": problem_matches,
    }


def _escape_markdown(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _issues_table(issues: list[dict]) -> list[str]:
    if not issues:
        return ["Nenhum."]
    lines = [
        "| Jogo | Validação | Problema | Evidência | Valor FPF |",
        "|---:|---|---|---|---|",
    ]
    for issue in issues:
        match_id = issue["match_id"]
        preservation = (
            "Preservado"
            if issue["source_value_preserved"]
            else "Não aplicável"
        )
        lines.append(
            f"| {_escape_markdown(match_id or 'Global')} "
            f"| {_escape_markdown(issue['check'])} "
            f"| {_escape_markdown(issue['message'])} "
            f"| {_escape_markdown(issue['evidence'] or '—')} "
            f"| {preservation} |"
        )
    return lines


def render_report(validation: dict) -> str:
    statistics = validation["statistics"]
    lines = [
        "# Relatório de validação dos detalhes dos jogos",
        "",
        "## Estatísticas gerais",
        "",
        "| Métrica | Valor |",
        "|---|---:|",
        f"| Jogos esperados | {statistics['expected_matches']} |",
        f"| Jogos encontrados | {statistics['total_matches']} |",
        f"| `match_id` únicos | {statistics['unique_match_ids']} |",
        f"| Erros técnicos | {statistics['technical_errors']} |",
        f"| `parser_error` | {statistics['parser_error']} |",
        f"| `structural_error` | {statistics['structural_error']} |",
        "| `source_inconsistency` "
        f"| {statistics['source_inconsistency']} |",
        "| `data_quality_warning` "
        f"| {statistics['data_quality_warning']} |",
        f"| Jogos problemáticos | {statistics['problem_matches']} |",
        "",
        "## Completude dos campos",
        "",
        "| Campo | Preenchidos | Total | Completude |",
        "|---|---:|---:|---:|",
    ]

    for field, values in validation["completeness"].items():
        lines.append(
            f"| `{field}` | {values['complete']} | "
            f"{values['total']} | {values['percentage']:.2f}% |"
        )

    section_titles = {
        "parser_error": "Erros do parser",
        "structural_error": "Erros estruturais",
        "source_inconsistency": "Inconsistências da fonte FPF",
        "data_quality_warning": "Avisos de qualidade dos dados",
    }
    for classification in ISSUE_CLASSIFICATIONS:
        lines.extend(
            ["", f"## {section_titles[classification]}", ""]
        )
        lines.extend(_issues_table(validation[classification]))

    lines.extend(
        [
            "",
            "Os valores publicados pela FPF são preservados nas "
            "inconsistências da fonte; o validador apenas as assinala.",
        ]
    )
    lines.extend(["", "## Jogos problemáticos", ""])

    if validation["problem_matches"]:
        lines.extend(
            f"- `{match_id}`"
            for match_id in validation["problem_matches"]
        )
    else:
        lines.append("Nenhum.")

    return "\n".join(lines) + "\n"


def save_report(
    validation: dict,
    path: Path = REPORT_PATH,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_report(validation),
        encoding="utf-8",
    )


def main() -> int:
    matches = load_match_details()
    validation = validate_match_details(matches)
    save_report(validation)

    statistics = validation["statistics"]
    print(f"Jogos validados: {statistics['total_matches']}")
    print(f"Erros técnicos: {statistics['technical_errors']}")
    print(
        "Inconsistências da fonte: "
        f"{statistics['source_inconsistency']}"
    )
    print(
        "Avisos de qualidade: "
        f"{statistics['data_quality_warning']}"
    )
    print(f"Relatório: {REPORT_PATH}")
    return validation_exit_code(validation)


def validation_exit_code(validation: dict) -> int:
    return 1 if validation["statistics"]["technical_errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
