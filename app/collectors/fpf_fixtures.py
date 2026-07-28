import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import requests
from bs4 import BeautifulSoup
from requests import Response


FPF_COMPETITION_URL = (
    "https://resultados.fpf.pt/Competition/GetCompetition"
)
OUTPUT_PATH = Path(
    "data/processed/fixtures_sub16_fdm_2025_2026.json"
)
REQUEST_TIMEOUT = 30
FIXTURE_ENDPOINT = "GetClassificationAndMatchesByFixture"
SERIE_ID_PATTERN = re.compile(
    r"(?:htmlSerieId_|classificationMatchSection_)(\d+)"
)


def _validate_html_response(response: Response) -> str:
    content_type = response.headers.get("Content-Type", "").lower()
    if "html" not in content_type:
        raise ValueError(
            "A resposta da FPF não contém HTML "
            f"(Content-Type: {content_type or 'em falta'})."
        )

    html = response.text.strip()
    if not html:
        raise ValueError("A resposta da FPF contém HTML vazio.")

    if BeautifulSoup(html, "html.parser").find() is None:
        raise ValueError(
            "A resposta da FPF não contém elementos HTML válidos."
        )

    return html


def fetch_competition_html(
    competition_id: int,
    season_id: int,
) -> str:
    params = {
        "Competition.Id": competition_id,
        "SeasonId": season_id,
    }
    headers = {
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
            f"?competitionId={competition_id}&seasonId={season_id}"
        ),
    }

    try:
        response = requests.get(
            FPF_COMPETITION_URL,
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.Timeout as exc:
        raise RuntimeError(
            "O pedido à FPF excedeu o limite de "
            f"{REQUEST_TIMEOUT} segundos."
        ) from exc
    except requests.HTTPError as exc:
        status_code = (
            exc.response.status_code if exc.response is not None else "?"
        )
        raise RuntimeError(
            f"A FPF devolveu um erro HTTP ({status_code})."
        ) from exc
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Não foi possível contactar a FPF: {exc}"
        ) from exc

    return _validate_html_response(response)


def _extract_serie_id(link: object) -> int | None:
    for parent in link.parents:
        element_id = parent.get("id")
        if not element_id:
            continue

        match = SERIE_ID_PATTERN.search(element_id)
        if match:
            return int(match.group(1))

    return None


def _relative_url(href: str) -> str:
    parsed = urlsplit(href)
    relative = parsed.path
    if parsed.query:
        relative = f"{relative}?{parsed.query}"
    return relative


def extract_fixtures(html: str) -> list[dict]:
    if not html or not html.strip():
        raise ValueError("Não é possível extrair fixtures de HTML vazio.")

    soup = BeautifulSoup(html, "html.parser")
    fixtures_by_id: dict[int, dict] = {}

    for link in soup.find_all("a", href=True):
        href = link["href"].strip()
        if FIXTURE_ENDPOINT not in href:
            continue

        query = parse_qs(urlsplit(href).query)
        fixture_values = query.get("fixtureId")
        if not fixture_values:
            raise ValueError(
                f"Link de fixture sem fixtureId: {href}"
            )

        raw_fixture_id = fixture_values[0]
        try:
            fixture_id = int(raw_fixture_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"fixtureId inválido no link: {href}"
            ) from exc

        if fixture_id <= 0:
            raise ValueError(
                f"fixtureId inválido no link: {href}"
            )

        fixture = {
            "fixture_id": fixture_id,
            "journey": link.get_text(" ", strip=True),
            "url": _relative_url(href),
            "serie_id": _extract_serie_id(link),
        }

        existing = fixtures_by_id.get(fixture_id)
        if existing is None:
            fixtures_by_id[fixture_id] = fixture
        elif existing["serie_id"] is None:
            existing["serie_id"] = fixture["serie_id"]

    if not fixtures_by_id:
        raise ValueError(
            "Nenhum fixtureId foi encontrado no HTML da competição."
        )

    return sorted(
        fixtures_by_id.values(),
        key=lambda fixture: fixture["fixture_id"],
    )


def collect_fixtures(
    competition_id: int,
    season_id: int,
) -> list[dict]:
    html = fetch_competition_html(
        competition_id=competition_id,
        season_id=season_id,
    )
    return extract_fixtures(html)


def save_fixtures(fixtures: list[dict], path: Path = OUTPUT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(fixtures, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    competition_id = 28712
    season_id = 105

    fixtures = collect_fixtures(
        competition_id=competition_id,
        season_id=season_id,
    )
    save_fixtures(fixtures)

    print(json.dumps(fixtures, ensure_ascii=False, indent=2))
    print(f"\nResultados guardados em: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
