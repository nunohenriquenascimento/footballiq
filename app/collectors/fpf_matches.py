import argparse
import json
import math
import os
import random
import re
import tempfile
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import requests
from bs4 import BeautifulSoup, Tag
from requests import Response, Session


FPF_FIXTURE_URL = (
    "https://resultados.fpf.pt/"
    "Competition/GetClassificationAndMatchesByFixture"
)
FIXTURES_PATH = Path(
    "data/processed/fixtures_sub16_fdm_2025_2026.json"
)
OUTPUT_PATH = Path(
    "data/processed/matches_sub16_fdm_2025_2026.json"
)
CACHE_DIR = Path("data/raw/fixtures")
REQUEST_TIMEOUT = 30
REQUEST_DELAY_SECONDS = 5.0
REQUEST_JITTER_SECONDS = 1.0
MAX_RETRIES = 3
SCORE_PATTERN = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*$")
TIME_PATTERN = re.compile(r"\b([01]?\d|2[0-3]):[0-5]\d\b")


class RateLimitError(RuntimeError):
    """Raised when the FPF keeps returning HTTP 429."""


def _request_headers() -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/149.0.0.0 Safari/537.36"
        ),
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "text/html, */*; q=0.01",
        "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
        "Referer": (
            "https://resultados.fpf.pt/Competition/Details"
            "?competitionId=28712&seasonId=105"
        ),
    }


def _validate_html_response(response: Response, fixture_id: int) -> str:
    content_type = response.headers.get("Content-Type", "").lower()
    if "html" not in content_type:
        raise ValueError(
            f"A jornada {fixture_id} não devolveu HTML "
            f"(Content-Type: {content_type or 'em falta'})."
        )

    html = response.text.strip()
    if not html:
        raise ValueError(
            f"A jornada {fixture_id} devolveu HTML vazio."
        )

    if BeautifulSoup(html, "html.parser").find() is None:
        raise ValueError(
            f"A jornada {fixture_id} não contém HTML válido."
        )

    return html


def load_fixtures(path: Path = FIXTURES_PATH) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(
            f"O ficheiro de fixtures não existe: {path}"
        )

    try:
        fixtures = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"O ficheiro de fixtures contém JSON inválido: {path}"
        ) from exc

    if not isinstance(fixtures, list) or not fixtures:
        raise ValueError(
            "O ficheiro de fixtures deve conter uma lista não vazia."
        )

    for fixture in fixtures:
        if not isinstance(fixture, dict):
            raise ValueError("Foi encontrada uma fixture inválida.")

        fixture_id = fixture.get("fixture_id")
        if not isinstance(fixture_id, int) or fixture_id <= 0:
            raise ValueError(
                f"fixture_id inválido no ficheiro: {fixture_id!r}"
            )

    return fixtures


def _useful_retry_after_seconds(response: Response) -> float | None:
    retry_after = response.headers.get("Retry-After")
    if retry_after is None:
        return None

    try:
        retry_delay = float(retry_after)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(retry_after)
        except (TypeError, ValueError, OverflowError):
            return None

        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)

        retry_delay = (
            retry_at - datetime.now(timezone.utc)
        ).total_seconds()

    if math.isfinite(retry_delay) and retry_delay > 0:
        return retry_delay
    return None


def fetch_fixture_html(
    fixture_id: int,
    session: Session | None = None,
    is_first_request: bool = False,
) -> str:
    if not isinstance(fixture_id, int) or fixture_id <= 0:
        raise ValueError(f"fixture_id inválido: {fixture_id!r}")

    client = session or requests.Session()

    try:
        for attempt in range(MAX_RETRIES + 1):
            response = client.get(
                FPF_FIXTURE_URL,
                params={"fixtureId": fixture_id},
                headers=_request_headers(),
                timeout=REQUEST_TIMEOUT,
            )

            if response.status_code != 429:
                break

            retry_delay = _useful_retry_after_seconds(response)
            if is_first_request and attempt == 0 and retry_delay is None:
                raise RateLimitError(
                    "O primeiro pedido recebeu HTTP 429 sem um "
                    "Retry-After útil; a execução foi interrompida "
                    "sem novas tentativas."
                )

            if attempt == MAX_RETRIES:
                raise RateLimitError(
                    f"A jornada {fixture_id} continuou a devolver "
                    f"HTTP 429 após {MAX_RETRIES} tentativas."
                )

            if retry_delay is None:
                retry_delay = float(2**attempt)
            print(
                f"HTTP 429 na jornada {fixture_id}; nova tentativa "
                f"dentro de {retry_delay:.1f} segundos."
            )
            time.sleep(retry_delay)

        response.raise_for_status()
    except RateLimitError:
        raise
    except requests.Timeout as exc:
        raise RuntimeError(
            f"O pedido da jornada {fixture_id} excedeu "
            f"{REQUEST_TIMEOUT} segundos."
        ) from exc
    except requests.HTTPError as exc:
        status_code = (
            exc.response.status_code if exc.response is not None else "?"
        )
        raise RuntimeError(
            f"A jornada {fixture_id} devolveu erro HTTP "
            f"({status_code})."
        ) from exc
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Não foi possível obter a jornada {fixture_id}: {exc}"
        ) from exc

    return _validate_html_response(response, fixture_id)


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
            temporary_path = Path(temporary_file.name)

        temporary_path.replace(path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def fixture_cache_path(
    fixture_id: int,
    cache_dir: Path = CACHE_DIR,
) -> Path:
    return cache_dir / f"{fixture_id}.html"


def load_cached_fixture_html(
    fixture_id: int,
    cache_dir: Path = CACHE_DIR,
) -> str | None:
    path = fixture_cache_path(fixture_id, cache_dir)
    if not path.exists() or path.stat().st_size == 0:
        return None

    html = path.read_text(encoding="utf-8").strip()
    return html or None


def save_fixture_html(
    fixture_id: int,
    html: str,
    cache_dir: Path = CACHE_DIR,
) -> None:
    if not html or not html.strip():
        raise ValueError(
            f"Não é possível guardar HTML vazio da jornada {fixture_id}."
        )

    _atomic_write_text(
        fixture_cache_path(fixture_id, cache_dir),
        html.strip() + "\n",
    )


def _extract_match_id(link: Tag) -> int:
    href = link.get("href", "")
    values = parse_qs(urlsplit(href).query).get("matchId")
    if not values:
        raise ValueError(f"Link de jogo sem matchId: {href}")

    try:
        match_id = int(values[0])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"matchId inválido no link: {href}") from exc

    if match_id <= 0:
        raise ValueError(f"matchId inválido no link: {href}")

    return match_id


def _text_or_none(element: Tag | None) -> str | None:
    if element is None:
        return None

    text = element.get_text(" ", strip=True)
    return text or None


def _extract_schedule(
    score_element: Tag | None,
) -> tuple[str | None, str | None]:
    if score_element is None:
        return None, None

    schedule = score_element.select_one(".game-schedule")
    schedule_text = _text_or_none(schedule)
    if not schedule_text:
        return None, None

    time_match = TIME_PATTERN.search(schedule_text)
    match_time = time_match.group(0) if time_match else None

    match_date = TIME_PATTERN.sub("", schedule_text)
    match_date = re.sub(r"\s*[|,-]\s*$", "", match_date).strip()

    return match_date or None, match_time


def _extract_score(
    score_element: Tag | None,
) -> tuple[int | None, int | None]:
    if score_element is None:
        return None, None

    for span in score_element.find_all("span", recursive=False):
        if "game-schedule" in span.get("class", []):
            continue

        score_match = SCORE_PATTERN.match(span.get_text(" ", strip=True))
        if score_match:
            return int(score_match.group(1)), int(score_match.group(2))

    score_match = SCORE_PATTERN.search(
        score_element.get_text(" ", strip=True)
    )
    if score_match:
        return int(score_match.group(1)), int(score_match.group(2))

    return None, None


def _extract_status(link: Tag) -> str | None:
    status_element = link.select_one(
        ".match-status, .game-status, .status"
    )
    if status_element is not None:
        return _text_or_none(status_element)

    game = link.select_one(".game")
    if game is not None:
        status = game.get("data-status")
        if status:
            return status.strip() or None

    return None


def extract_matches(html: str, fixture: dict) -> list[dict]:
    if not html or not html.strip():
        raise ValueError("Não é possível extrair jogos de HTML vazio.")

    fixture_id = fixture.get("fixture_id")
    if not isinstance(fixture_id, int) or fixture_id <= 0:
        raise ValueError(f"fixture_id inválido: {fixture_id!r}")

    soup = BeautifulSoup(html, "html.parser")
    matches: list[dict] = []

    for link in soup.select("#matches a.game-link[href*='matchId=']"):
        score_element = link.select_one(".score")
        match_date, match_time = _extract_schedule(score_element)
        home_score, away_score = _extract_score(score_element)

        matches.append(
            {
                "fixture_id": fixture_id,
                "serie_id": fixture.get("serie_id"),
                "round": fixture.get("journey"),
                "match_id": _extract_match_id(link),
                "home_team": _text_or_none(
                    link.select_one(".home-team")
                ),
                "away_team": _text_or_none(
                    link.select_one(".away-team")
                ),
                "match_date": match_date,
                "match_time": match_time,
                "venue": _text_or_none(
                    link.select_one(".game-list-stadium small")
                ),
                "home_score": home_score,
                "away_score": away_score,
                "status": _extract_status(link),
            }
        )

    return matches


def load_existing_matches(path: Path = OUTPUT_PATH) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []

    try:
        matches = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"O ficheiro de jogos contém JSON inválido: {path}"
        ) from exc

    if not isinstance(matches, list):
        raise ValueError(
            f"O ficheiro de jogos deve conter uma lista: {path}"
        )

    for match in matches:
        if not isinstance(match, dict):
            raise ValueError(
                "Foi encontrado um jogo inválido no JSON existente."
            )

        match_id = match.get("match_id")
        if not isinstance(match_id, int) or match_id <= 0:
            raise ValueError(
                f"match_id inválido no JSON existente: {match_id!r}"
            )

    return matches


def save_matches(
    matches: list[dict],
    path: Path = OUTPUT_PATH,
) -> None:
    content = json.dumps(
        matches,
        ensure_ascii=False,
        indent=2,
    ) + "\n"
    _atomic_write_text(path, content)


def collect_matches(
    fixtures_path: Path = FIXTURES_PATH,
    output_path: Path = OUTPUT_PATH,
    cache_dir: Path = CACHE_DIR,
    offline: bool = False,
    limit: int | None = None,
    stats: dict[str, int] | None = None,
) -> list[dict]:
    fixtures = load_fixtures(fixtures_path)
    if limit is not None:
        if limit <= 0:
            raise ValueError("O limite deve ser superior a zero.")
        fixtures = fixtures[:limit]

    run_stats = stats if stats is not None else {}
    run_stats.update(
        {
            "cached_fixtures": 0,
            "downloaded_fixtures": 0,
            "failed_fixtures": 0,
            "extracted_matches": 0,
            "duplicate_matches": 0,
            "rate_limited": 0,
        }
    )

    existing_matches = load_existing_matches(output_path)
    matches_by_id = {
        match["match_id"]: match for match in existing_matches
    }
    network_requests = 0

    with requests.Session() as session:
        for fixture in fixtures:
            fixture_id = fixture["fixture_id"]
            html = load_cached_fixture_html(
                fixture_id=fixture_id,
                cache_dir=cache_dir,
            )

            if html is not None:
                run_stats["cached_fixtures"] += 1
            elif offline:
                run_stats["failed_fixtures"] += 1
                print(
                    f"Cache em falta para a jornada {fixture_id}; "
                    "pedido ignorado em modo offline."
                )
                continue
            else:
                if network_requests:
                    delay = (
                        REQUEST_DELAY_SECONDS
                        + random.uniform(0, REQUEST_JITTER_SECONDS)
                    )
                    time.sleep(delay)

                try:
                    html = fetch_fixture_html(
                        fixture_id=fixture_id,
                        session=session,
                        is_first_request=(network_requests == 0),
                    )
                except RateLimitError as exc:
                    run_stats["failed_fixtures"] += 1
                    run_stats["rate_limited"] = 1
                    print(exc)
                    print(
                        "Recolha interrompida para preservar o "
                        "progresso e evitar novos pedidos."
                    )
                    break
                except (RuntimeError, ValueError) as exc:
                    run_stats["failed_fixtures"] += 1
                    network_requests += 1
                    print(
                        f"Falha na jornada {fixture_id}: {exc}"
                    )
                    continue

                network_requests += 1
                save_fixture_html(
                    fixture_id=fixture_id,
                    html=html,
                    cache_dir=cache_dir,
                )
                run_stats["downloaded_fixtures"] += 1

            try:
                fixture_matches = extract_matches(html, fixture)
            except ValueError as exc:
                run_stats["failed_fixtures"] += 1
                print(
                    f"Falha ao processar a jornada {fixture_id}: {exc}"
                )
                continue

            run_stats["extracted_matches"] += len(fixture_matches)
            for match in fixture_matches:
                match_id = match["match_id"]
                if match_id in matches_by_id:
                    run_stats["duplicate_matches"] += 1
                    continue
                matches_by_id[match_id] = match

            current_matches = sorted(
                matches_by_id.values(),
                key=lambda match: match["match_id"],
            )
            save_matches(current_matches, output_path)

    return sorted(
        matches_by_id.values(),
        key=lambda match: match["match_id"],
    )


def _positive_limit(value: str) -> int:
    try:
        limit = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "O limite deve ser um número inteiro."
        ) from exc

    if limit <= 0:
        raise argparse.ArgumentTypeError(
            "O limite deve ser superior a zero."
        )
    return limit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recolhe jogos das jornadas da FPF."
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Processa apenas HTML já existente na cache.",
    )
    parser.add_argument(
        "--limit",
        type=_positive_limit,
        help="Limita o número de fixtures a processar.",
    )
    return parser.parse_args()


def _print_summary(stats: dict[str, int]) -> None:
    print("\nResumo:")
    print(f"Fixtures lidos da cache: {stats['cached_fixtures']}")
    print(f"Fixtures descarregados: {stats['downloaded_fixtures']}")
    print(f"Fixtures falhados: {stats['failed_fixtures']}")
    print(f"Jogos extraídos: {stats['extracted_matches']}")
    print(
        "Jogos duplicados ignorados: "
        f"{stats['duplicate_matches']}"
    )
    print(f"JSON final: {OUTPUT_PATH}")


def main() -> int:
    try:
        args = parse_args()
        stats: dict[str, int] = {}
        collect_matches(
            offline=args.offline,
            limit=args.limit,
            stats=stats,
        )
        _print_summary(stats)
        return 1 if stats["rate_limited"] else 0
    except KeyboardInterrupt:
        print(
            "\nExecução interrompida pelo utilizador. "
            "O progresso já guardado foi preservado."
        )
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
