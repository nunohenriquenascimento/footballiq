from pathlib import Path

import requests


FPF_URL = (
    "https://resultados.fpf.pt/"
    "Competition/GetCompetitionsByAssociation"
)

RAW_DATA_PATH = Path(
    "data/raw/competitions_af_guarda_2025_2026.html"
)


def fetch_competitions(
    association_id: int,
    season_id: int,
) -> str:
    params = {
        "associationId": association_id,
        "seasonId": season_id,
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/149.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
        "Referer": "https://resultados.fpf.pt/",
    }

    response = requests.get(
        FPF_URL,
        params=params,
        headers=headers,
        timeout=30,
    )

    print("URL final:", response.url)
    print("Status:", response.status_code)
    print(
        "Content-Type:",
        response.headers.get("Content-Type"),
    )
    print("Tamanho:", len(response.text))
    print("Primeiros 500 caracteres:")
    print(response.text[:500])

    response.raise_for_status()

    return response.text


def save_raw_data(data: str) -> None:
    RAW_DATA_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    RAW_DATA_PATH.write_text(
        data,
        encoding="utf-8",
    )


def main() -> None:
    competitions_html = fetch_competitions(
        association_id=226,
        season_id=105,
    )

    save_raw_data(competitions_html)

    print(
        f"Dados guardados com sucesso em: "
        f"{RAW_DATA_PATH}"
    )


if __name__ == "__main__":
    main()