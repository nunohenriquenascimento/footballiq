import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup, Tag


DEFAULT_HTML_PATH = Path("data/raw/matches/2484514.html")
ID_PATTERN = re.compile(r"/(?:Player|Club)/Logo/(\d+)", re.IGNORECASE)
SCORE_PATTERN = re.compile(r"(\d+)\s*-\s*(\d+)")
MINUTE_PATTERN = re.compile(r"(\d+)'")
ADDED_TIME_PATTERN = re.compile(r"\+\s*(\d+)'")


def _text(element: Tag | None) -> str | None:
    if element is None:
        return None
    value = element.get_text(" ", strip=True)
    return value or None


def _id_from_url(url: str | None) -> int | None:
    if not url:
        return None
    match = ID_PATTERN.search(url)
    return int(match.group(1)) if match else None


def _normalise_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    ).casefold().strip()


def _find_section(soup: BeautifulSoup, title: str) -> Tag | None:
    for title_element in soup.select(".title-bar > div"):
        if _text(title_element) == title:
            return title_element.find_parent("section")
    return None


def _parse_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%d-%m-%Y").date().isoformat()
    except ValueError:
        return None


def _parse_time(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%H:%M").strftime("%H:%M")
    except ValueError:
        return None


def _parse_minute(value: str | None) -> tuple[int | None, int | None]:
    if not value:
        return None, None
    minute_match = MINUTE_PATTERN.search(value)
    added_time_match = ADDED_TIME_PATTERN.search(value)
    minute = int(minute_match.group(1)) if minute_match else None
    added_time = (
        int(added_time_match.group(1)) if added_time_match else None
    )
    return minute, added_time


def _normalise_event_phase(section_title: str | None) -> str | None:
    if not section_title:
        return None

    normalised = _normalise_name(section_title)
    if re.search(r"\b1[ao]?\s*parte\b", normalised):
        return "first_half"
    if "intervalo" in normalised:
        return "half_time"
    if re.search(r"\b2[ao]?\s*parte\b", normalised):
        return "second_half"
    if "depois do jogo" in normalised:
        return "post_match"
    return None


def _timeline_context(item: Tag) -> tuple[str | None, str | None]:
    title_element = item.find_previous(
        "div",
        class_=lambda value: value and "timeline-title" in value,
    )
    source_section = _text(title_element)
    return _normalise_event_phase(source_section), source_section


def _match_ids_from_url(value: str | None) -> list[int]:
    if not value:
        return []

    query = parse_qs(urlsplit(value).query)
    match_ids = []
    for key, values in query.items():
        if key.casefold() != "matchid":
            continue
        for candidate in values:
            try:
                match_id = int(candidate)
            except (TypeError, ValueError):
                continue
            if match_id > 0:
                match_ids.append(match_id)
    return match_ids


def extract_match_id(soup: BeautifulSoup) -> int | None:
    candidates: list[tuple[str, int]] = []

    def resolve_candidates() -> int | None:
        unique_ids = {match_id for _, match_id in candidates}
        if len(unique_ids) > 1:
            evidence = ", ".join(
                f"{source}={match_id}"
                for source, match_id in candidates
            )
            raise ValueError(
                "Foram encontrados match_id inconsistentes no HTML: "
                f"{evidence}"
            )
        return next(iter(unique_ids), None)

    for element in soup.select("#Request_MatchId[value]"):
        try:
            match_id = int(element.get("value"))
        except (TypeError, ValueError):
            continue
        if match_id > 0:
            candidates.append(("#Request_MatchId", match_id))

    for element in soup.select('meta[property="og:url"][content]'):
        for match_id in _match_ids_from_url(element.get("content")):
            candidates.append(("meta[property='og:url']", match_id))

    prioritised_match_id = resolve_candidates()
    if prioritised_match_id is not None:
        return prioritised_match_id

    for element in soup.find_all(True):
        for attribute, raw_value in element.attrs.items():
            values = (
                raw_value
                if isinstance(raw_value, list)
                else [raw_value]
            )
            for value in values:
                if not isinstance(value, str):
                    continue
                if not re.search(r"(?:^|[?&])matchId=", value, re.I):
                    continue
                for match_id in _match_ids_from_url(value):
                    candidates.append(
                        (
                            f"{element.name}[{attribute}]",
                            match_id,
                        )
                    )

    return resolve_candidates()


def parse_match_header(soup: BeautifulSoup) -> dict:
    match_id = extract_match_id(soup)

    competition_link = soup.select_one("#competitionDetails[href]")
    competition_id = None
    season_id = None
    competition_name = None
    if competition_link is not None:
        query = parse_qs(
            urlsplit(competition_link.get("href", "")).query
        )
        try:
            competition_id = int(query["competitionId"][0])
        except (KeyError, TypeError, ValueError):
            competition_id = None
        try:
            season_id = int(query["seasonId"][0])
        except (KeyError, TypeError, ValueError):
            season_id = None

        competition_row = competition_link.find_parent(
            "div",
            class_="row",
        )
        if competition_row is not None:
            columns = competition_row.find_all("div", recursive=False)
            if columns:
                competition_name = _text(columns[0])

    resume = soup.select_one(".game-resume")
    home_name = None
    away_name = None
    home_score = None
    away_score = None
    home_club_id = None
    away_club_id = None
    if resume is not None:
        strong_values = [
            value
            for element in resume.select("strong")
            if (value := _text(element)) is not None
        ]
        if len(strong_values) >= 3:
            home_name = strong_values[0]
            score_match = SCORE_PATTERN.search(strong_values[1])
            away_name = strong_values[2]
            if score_match:
                home_score = int(score_match.group(1))
                away_score = int(score_match.group(2))

        logos = resume.select("img[src]")
        if logos:
            home_club_id = _id_from_url(logos[0].get("src"))
        if len(logos) > 1:
            away_club_id = _id_from_url(logos[-1].get("src"))

    date_value = None
    time_value = None
    venue_name = None
    time_place = _text(soup.select_one(".info-time-place"))
    if time_place:
        details_match = re.search(
            r"Data:\s*(\S+)\s+Hora:\s*(\S+)\s+"
            r"Est[áa]dio:\s*(.+)$",
            time_place,
            re.IGNORECASE,
        )
        if details_match:
            date_value = _parse_date(details_match.group(1))
            time_value = _parse_time(details_match.group(2))
            venue_name = details_match.group(3).strip() or None

    return {
        "match_id": match_id,
        "competition": {
            "competition_id": competition_id,
            "season_id": season_id,
            "name": competition_name,
        },
        "scheduled_at": {
            "date": date_value,
            "time": time_value,
            "timezone": "Europe/Lisbon",
        },
        "venue": {
            "name": venue_name,
        },
        "teams": {
            "home": {
                "club_id": home_club_id,
                "name": home_name,
                "score": home_score,
            },
            "away": {
                "club_id": away_club_id,
                "name": away_name,
                "score": away_score,
            },
        },
    }


def _parse_player(player: Tag) -> dict:
    number_element = player.find("strong", recursive=False)
    shirt_number = None
    if number_element is not None:
        try:
            shirt_number = int(_text(number_element))
        except (TypeError, ValueError):
            shirt_number = None

    direct_text = [
        str(node).strip()
        for node in player.find_all(string=True, recursive=False)
        if str(node).strip()
    ]
    name = " ".join(direct_text) or None
    is_goalkeeper = bool(name and "(GR)" in name)
    if name:
        name = re.sub(r"\s*\(GR\)\s*$", "", name).strip()

    image = player.select_one("img[src]")
    player_id = _id_from_url(image.get("src") if image else None)

    return {
        "player_id": player_id,
        "shirt_number": shirt_number,
        "name": name,
        "is_goalkeeper": is_goalkeeper,
    }


def _parse_lineup_section(
    soup: BeautifulSoup,
    title: str,
) -> dict[str, list[dict]]:
    section = _find_section(soup, title)
    result = {"home": [], "away": []}
    if section is None:
        return result

    team_blocks = section.select(".lineup-team")
    for index, side in enumerate(("home", "away")):
        if index >= len(team_blocks):
            break
        result[side] = [
            _parse_player(player)
            for player in team_blocks[index].select(".player")
        ]
    return result


def parse_lineups(soup: BeautifulSoup) -> dict:
    starters = _parse_lineup_section(soup, "Equipas Iniciais")
    substitutes = _parse_lineup_section(soup, "Suplentes")
    return {
        "home": {
            "starters": starters["home"],
            "substitutes": substitutes["home"],
            "staff": [],
        },
        "away": {
            "starters": starters["away"],
            "substitutes": substitutes["away"],
            "staff": [],
        },
    }


def _normalise_staff_role(role: str | None) -> str | None:
    if not role:
        return None
    normalised = _normalise_name(role)
    if "treinador principal" in normalised:
        return "head_coach"
    if "treinador adjunto" in normalised:
        return "assistant_coach"
    if "1º delegado" in normalised or "1o delegado" in normalised:
        return "delegate"
    if "2º delegado" in normalised or "2o delegado" in normalised:
        return "second_delegate"
    if "enfermeiro" in normalised:
        return "nurse"
    return normalised.replace(" ", "_")


def _parse_staff_section(
    soup: BeautifulSoup,
    title: str,
) -> dict[str, list[dict]]:
    section = _find_section(soup, title)
    result = {"home": [], "away": []}
    if section is None:
        return result

    team_blocks = section.select(".lineup-team")
    for index, side in enumerate(("home", "away")):
        if index >= len(team_blocks):
            break
        for person in team_blocks[index].select(".player"):
            spans = person.find_all("span", recursive=False)
            role_label = _text(spans[0]) if spans else None
            name = _text(spans[1]) if len(spans) > 1 else None
            image = person.select_one("img[src]")
            result[side].append(
                {
                    "person_id": _id_from_url(
                        image.get("src") if image else None
                    ),
                    "role": _normalise_staff_role(role_label),
                    "role_label": role_label,
                    "name": name,
                }
            )
    return result


def parse_staff(soup: BeautifulSoup) -> dict[str, list[dict]]:
    coaches = _parse_staff_section(soup, "Treinadores")
    directors = _parse_staff_section(soup, "Dirigentes")
    return {
        side: coaches[side] + directors[side]
        for side in ("home", "away")
    }


def _normalise_official_role(role: str | None) -> str | None:
    if not role:
        return None
    normalised = _normalise_name(role)
    if normalised == "arbitro":
        return "referee"
    if "assistente 1" in normalised:
        return "assistant_referee_1"
    if "assistente 2" in normalised:
        return "assistant_referee_2"
    if "quarto" in normalised or "4" in normalised:
        return "fourth_official"
    return normalised.replace(" ", "_")


def parse_officials(soup: BeautifulSoup) -> list[dict]:
    section = _find_section(soup, "Equipa de arbitragem")
    if section is None:
        return []

    officials = []
    for person in section.select(".player"):
        role_label = _text(person.find("strong"))
        name_element = person.find(
            "span",
            style=lambda value: value and "font-weight: normal" in value,
        )
        officials.append(
            {
                "role": _normalise_official_role(role_label),
                "role_label": role_label,
                "name": _text(name_element),
            }
        )
    return officials


def _player_index(lineups: dict) -> dict[str, dict]:
    index = {}
    for side in ("home", "away"):
        players = (
            lineups[side]["starters"]
            + lineups[side]["substitutes"]
        )
        for player in players:
            name = player.get("name")
            if name:
                index[_normalise_name(name)] = {
                    "side": side,
                    "player_id": player.get("player_id"),
                }
    return index


def _player_reference(
    name: str | None,
    players: dict[str, dict],
) -> dict:
    reference = players.get(_normalise_name(name or ""), {})
    return {
        "player_id": reference.get("player_id"),
        "name": name,
    }


def parse_events(soup: BeautifulSoup, lineups: dict) -> list[dict]:
    players = _player_index(lineups)
    events = []

    for item in soup.select(".timeline-item"):
        icon = item.select_one("img[src]")
        minute_element = item.select_one(".top-tag")
        if icon is None or minute_element is None:
            continue

        icon_url = icon.get("src", "").lower()
        display_minute = _text(minute_element)
        minute, added_time = _parse_minute(display_minute)
        phase, source_section = _timeline_context(item)
        event: dict = {
            "type": None,
            "minute": minute,
            "added_time": added_time,
            "phase": phase,
            "display_minute": display_minute,
            "source_section": source_section,
            "team_side": None,
        }

        if "icon-start" in icon_url:
            event["type"] = "period_start"
        elif "icon-end" in icon_url:
            event["type"] = "period_end"
        elif "icon-goal" in icon_url:
            event["type"] = "goal"
            scorer_element = item.select_one(".bottom-tag strong")
            scorer_text = _text(scorer_element)
            is_penalty = bool(
                scorer_text and re.search(r"\(p\)", scorer_text, re.I)
            )
            scorer_name = (
                re.sub(r"\s*\(p\)\s*$", "", scorer_text, flags=re.I)
                if scorer_text
                else None
            )
            player = _player_reference(scorer_name, players)
            event["player_id"] = player["player_id"]
            event["player_name"] = player["name"]
            event["team_side"] = players.get(
                _normalise_name(scorer_name or ""),
                {},
            ).get("side")
            event["detail"] = "penalty" if is_penalty else None

            score_text = _text(item.select_one(".bottom-tag"))
            score_match = SCORE_PATTERN.search(score_text or "")
            event["score"] = (
                {
                    "home": int(score_match.group(1)),
                    "away": int(score_match.group(2)),
                }
                if score_match
                else None
            )
        elif "yellow-card" in icon_url or "yellowcard" in icon_url:
            event["type"] = "yellow_card"
            player_name = _text(item.select_one(".bottom-tag strong"))
            player = _player_reference(player_name, players)
            event["player_id"] = player["player_id"]
            event["player_name"] = player["name"]
            event["team_side"] = players.get(
                _normalise_name(player_name or ""),
                {},
            ).get("side")
        elif "red-card" in icon_url or "redcard" in icon_url:
            event["type"] = "red_card"
            player_name = _text(item.select_one(".bottom-tag strong"))
            player = _player_reference(player_name, players)
            event["player_id"] = player["player_id"]
            event["player_name"] = player["name"]
            event["team_side"] = players.get(
                _normalise_name(player_name or ""),
                {},
            ).get("side")
        elif "substitution" in icon_url:
            event["type"] = "substitution"
            player_in_name = _text(item.select_one(".in"))
            player_out_name = _text(item.select_one(".out"))
            player_in = _player_reference(player_in_name, players)
            player_out = _player_reference(player_out_name, players)
            event["player_in"] = player_in
            event["player_out"] = player_out
            event["team_side"] = players.get(
                _normalise_name(player_in_name or ""),
                players.get(
                    _normalise_name(player_out_name or ""),
                    {},
                ),
            ).get("side")

        if event["type"] is not None:
            events.append(event)

    for goals_row in soup.select(".info-goals"):
        title = _text(goals_row.select_one(".info-goals-title"))
        if _normalise_name(title or "") != "penaltis":
            continue

        team_columns = [
            column
            for column in goals_row.find_all("div", recursive=False)
            if "info-goals-title" not in column.get("class", [])
        ]
        for column_index, column in enumerate(team_columns[:2]):
            side = ("home", "away")[column_index]
            for scorer in column.select("span"):
                scorer_text = _text(scorer)
                if not scorer_text:
                    continue
                minute, added_time = _parse_minute(scorer_text)
                scorer_name = re.sub(
                    r"^\s*\d+'\s*(?:\+\s*\d+'\s*)?",
                    "",
                    scorer_text,
                ).strip() or None
                player = _player_reference(scorer_name, players)
                events.append(
                    {
                        "type": "goal",
                        "minute": minute,
                        "added_time": added_time,
                        "phase": None,
                        "display_minute": (
                            scorer_text[: scorer_text.find("'") + 1]
                            if "'" in scorer_text
                            else None
                        ),
                        "source_section": title,
                        "team_side": side,
                        "player_id": player["player_id"],
                        "player_name": player["name"],
                        "detail": "penalty",
                        "score": None,
                    }
                )

    return events


def parse_periods(soup: BeautifulSoup) -> list[dict]:
    periods = []
    current_start = None

    for item in soup.select(".timeline-item"):
        icon = item.select_one("img[src]")
        if icon is None:
            continue
        icon_url = icon.get("src", "").lower()
        minute, added_time = _parse_minute(
            _text(item.select_one(".top-tag"))
        )

        if "icon-start" in icon_url:
            current_start = minute
        elif "icon-end" in icon_url:
            periods.append(
                {
                    "period": len(periods) + 1,
                    "start_minute": current_start,
                    "end_minute": minute,
                    "added_time": added_time,
                }
            )
            current_start = None

    return periods


def parse_match_details(
    html: str,
    *,
    fixture_id: int | None = None,
    serie_id: int | None = None,
    round_name: str | None = None,
) -> dict:
    if not html or not html.strip():
        raise ValueError("Não é possível analisar HTML vazio.")

    soup = BeautifulSoup(html, "html.parser")
    header = parse_match_header(soup)
    lineups = parse_lineups(soup)
    staff = parse_staff(soup)
    for side in ("home", "away"):
        lineups[side]["staff"] = staff[side]

    match_id = header["match_id"]
    return {
        "match_id": match_id,
        "fixture_id": fixture_id,
        "serie_id": serie_id,
        "competition": header["competition"],
        "round": round_name,
        "status": None,
        "scheduled_at": header["scheduled_at"],
        "venue": header["venue"],
        "teams": header["teams"],
        "lineups": lineups,
        "officials": parse_officials(soup),
        "events": parse_events(soup, lineups),
        "periods": parse_periods(soup),
        "source": {
            "provider": "FPF",
            "url": (
                "https://resultados.fpf.pt/"
                f"Match/GetMatchInformation?matchId={match_id}"
                if match_id is not None
                else None
            ),
        },
    }


def main() -> None:
    html = DEFAULT_HTML_PATH.read_text(encoding="utf-8")
    match = parse_match_details(
        html,
        fixture_id=626607,
        serie_id=93565,
        round_name="3",
    )
    print(json.dumps(match, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
