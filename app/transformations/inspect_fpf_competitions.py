from pathlib import Path

from bs4 import BeautifulSoup


HTML_PATH = Path(
    "data/raw/competitions_af_guarda_2025_2026.html"
)


def inspect_competition_links() -> None:
    html = HTML_PATH.read_text(encoding="utf-8")

    soup = BeautifulSoup(html, "html.parser")

    links = soup.find_all("a")

    print(f"Total de links encontrados: {len(links)}")
    print("-" * 80)

    for link in links:
        text = link.get_text(
            separator=" ",
            strip=True,
        )

        href = link.get("href")

        if not href:
            continue

        if (
            "competition" in href.lower()
            or "competition" in text.lower()
        ):
            print("Nome:", text)
            print("Link:", href)
            print("-" * 80)


if __name__ == "__main__":
    inspect_competition_links()